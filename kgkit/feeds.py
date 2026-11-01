"""Feeds: look for new material the records do not cover yet. Drafts nothing itself; proposals reads this.

trials  ClinicalTrials.gov API v2: studies for the configured condition, most recently updated first;
        any NCT number not already in a record's xrefs becomes a candidate new trial record.
papers  Europe PMC: papers matching the configured query first published in the last `since_days` days;
        any DOI or PMID not already cited anywhere becomes a candidate paper.
"""
from __future__ import annotations

import datetime as dt

from .common import FetchError, Http, qs, today, write_report
from .doi_check import EPMC, norm_id

CTGOV = "https://clinicaltrials.gov/api/v2/studies"


def known_ncts(records: list[dict]) -> set[str]:
    return {x.split(":", 1)[1].upper() for r in records for x in r.get("xrefs") or []
            if x.upper().startswith("CLINICALTRIALS:")}


def known_papers(records: list[dict]) -> set[tuple]:
    out = set()
    for r in records:
        for x in r.get("xrefs") or []:
            n = norm_id(x)
            if n:
                out.add(n)
        for s in r.get("sources") or []:
            for f in ("doi", "pmid"):
                if s.get(f):
                    out.add(norm_id(f"{f}:{s[f]}"))
        for rel in r.get("relations") or []:
            for p in rel.get("publications") or []:
                n = norm_id(p)
                if n:
                    out.add(n)
    return out


def trials(records: list[dict], conf: dict, http: Http) -> dict:
    params = {"query.cond": conf["condition"], "sort": "LastUpdatePostDate:desc",
              "pageSize": min(int(conf.get("max_results", 50)), 100),
              "fields": "NCTId,BriefTitle,OverallStatus,Phase,LastUpdatePostDate,LeadSponsorName"}
    try:
        data = http.get_json(f"{CTGOV}?{qs(params)}")
    except FetchError as exc:
        return {"status": "unreachable", "error": str(exc), "candidates": []}
    have = known_ncts(records)
    out = []
    for s in (data or {}).get("studies") or []:
        p = s.get("protocolSection") or {}
        ident, st, des = p.get("identificationModule") or {}, p.get("statusModule") or {}, p.get("designModule") or {}
        nct = str(ident.get("nctId") or "").upper()
        if not nct or nct in have:
            continue
        out.append({"nct": nct, "title": ident.get("briefTitle"), "status": (st.get("overallStatus") or "").lower(),
                    "phase": "/".join(x.lower() for x in des.get("phases") or []) or None,
                    "sponsor": ((p.get("sponsorCollaboratorsModule") or {}).get("leadSponsor") or {}).get("name"),
                    "last_update": (st.get("lastUpdatePostDateStruct") or {}).get("date"),
                    "url": f"https://clinicaltrials.gov/study/{nct}"})
    return {"status": "ok", "candidates": out}


def papers(records: list[dict], conf: dict, http: Http) -> dict:
    since = (today() - dt.timedelta(days=int(conf.get("since_days", 30)))).isoformat()
    query = f"({conf['query']}) AND FIRST_PDATE:[{since} TO {today().isoformat()}]"
    params = {"query": query, "format": "json", "resultType": "lite",
              "pageSize": min(int(conf.get("max_results", 50)), 100), "sort": "P_PDATE_D desc"}
    try:
        data = http.get_json(f"{EPMC}?{qs(params)}")
    except FetchError as exc:
        return {"status": "unreachable", "error": str(exc), "candidates": []}
    have = known_papers(records)
    out = []
    for r in ((data or {}).get("resultList") or {}).get("result") or []:
        ids = {norm_id(f"doi:{r['doi']}") if r.get("doi") else None, norm_id(f"pmid:{r['pmid']}") if r.get("pmid") else None}
        ids.discard(None)
        if not ids or ids & have:
            continue
        out.append({"title": (r.get("title") or "").rstrip("."), "doi": r.get("doi"), "pmid": r.get("pmid"),
                    "journal": r.get("journalTitle"), "published": r.get("firstPublicationDate"),
                    "url": f"https://doi.org/{r['doi']}" if r.get("doi") else f"https://europepmc.org/article/MED/{r.get('pmid')}"})
    return {"status": "ok", "since": since, "candidates": out}


OPENFDA = "https://api.fda.gov/device"


def _openfda(http: Http, path: str, params: dict) -> list[dict]:
    """openFDA answers 404 when a search has no matches; treat that as an empty result, not an outage."""
    try:
        return (http.get_json(f"{OPENFDA}/{path}.json?{qs(params)}") or {}).get("results") or []
    except FetchError as exc:
        if "404" in str(exc):
            return []
        raise


def known_device_numbers(records: list[dict]) -> set[str]:
    out = set()
    for r in records:
        fact = (r.get("facts") or {}).get("fda_submission_number")
        value = fact.get("value") if isinstance(fact, dict) else fact
        if value:
            out.add(str(value).upper())
    return out


def devices(records: list[dict], conf: dict, http: Http) -> dict:
    """FDA device decisions (510(k) clearances, and De Novo grants where openFDA lists them) for the
    condition's product codes. Product codes come from the configuration plus a search of the FDA device
    classification list for the condition name."""
    codes = {c.upper() for c in conf.get("product_codes") or []}
    try:
        if conf.get("classification_query"):
            for row in _openfda(http, "classification", {"search": f"device_name:{conf['classification_query']}", "limit": 100}):
                if row.get("product_code"):
                    codes.add(row["product_code"].upper())
        if not codes:
            return {"status": "ok", "product_codes": [], "candidates": []}
        search = " ".join(f"product_code:{c}" for c in sorted(codes))
        rows = _openfda(http, "510k", {"search": search, "sort": "decision_date:desc",
                                       "limit": min(int(conf.get("max_results", 50)), 100)})
    except FetchError as exc:
        return {"status": "unreachable", "error": str(exc), "candidates": []}
    have = known_device_numbers(records)
    out = []
    for row in rows:
        number = str(row.get("k_number") or "").upper()
        if not number or number in have:
            continue
        query = f"{OPENFDA}/510k.json?{qs({'search': f'k_number:{number}'})}"
        out.append({"number": number, "device_name": row.get("device_name"), "applicant": row.get("applicant"),
                    "decision_date": row.get("decision_date"), "decision": row.get("decision_description") or row.get("decision_code"),
                    "product_code": row.get("product_code"), "url": query})
    return {"status": "ok", "product_codes": sorted(codes), "candidates": out}


def run(records: list[dict], cfg: dict, http: Http, reports_dir) -> dict:
    conf = cfg.get("feeds") or {}
    report = {"check": "feeds"}
    if conf.get("trials"):
        report["trials"] = trials(records, conf["trials"], http)
    if conf.get("papers"):
        report["papers"] = papers(records, conf["papers"], http)
    if conf.get("devices"):
        report["devices"] = devices(records, conf["devices"], http)
    write_report(reports_dir, "feeds", report)
    return report
