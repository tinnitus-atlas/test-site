"""Retraction check: is any paper the graph cites retracted, withdrawn or under an expression of concern?

Source: Crossref's REST API, which carries publisher notices and the Retraction Watch database (curated daily by
Retraction Watch). For each DOI cited in a record's sources or relations, the work's "updated-by" notices are read.
  retracted   a retraction, withdrawal or removal notice: the record that cites it is held back from the website
              (taking it down is the safe direction) and the digest names it; a person then decides whether to
              drop the citation or the whole entry
  flagged     an expression of concern or a correction: reported for a person, nothing is held back
Papers cited only by PubMed number are not checked here (no DOI) and are counted as unchecked.
"""
from __future__ import annotations

import urllib.parse

from .common import FetchError, Http, write_report
from .doi_check import norm_id

CROSSREF = "https://api.crossref.org/v1/works"
RETRACTED = {"retraction", "withdrawal", "removal", "partial_retraction"}
FLAGGED = {"expression_of_concern", "correction", "erratum", "corrigendum"}


def cited(records: list[dict]) -> dict[str, set[str]]:
    """DOI -> ids of the records that cite it."""
    out: dict[str, set[str]] = {}
    for r in records:
        ids = [f"doi:{s['doi']}" if not str(s["doi"]).lower().startswith(("doi:", "http")) else s["doi"]
               for s in r.get("sources") or [] if s.get("doi")]
        ids += [p for rel in r.get("relations") or [] for p in rel.get("publications") or []]
        for raw in ids:
            n = norm_id(raw)
            if n and n[0] == "doi":
                out.setdefault(n[1], set()).add(r["id"])
    return out


def notices(http: Http, doi: str) -> list[dict]:
    data = http.get_json(f"{CROSSREF}/{urllib.parse.quote(doi, safe='/')}") or {}
    return ((data.get("message") or {}).get("updated-by")) or []


def kind(n: dict) -> str:
    return str(n.get("type") or n.get("label") or "").strip().lower().replace(" ", "_").replace("-", "_")


def run(records: list[dict], http: Http, reports_dir) -> dict:
    papers = cited(records)
    found, unreachable = [], []
    for doi, recs in sorted(papers.items()):
        try:
            items = notices(http, doi)
        except FetchError as exc:
            if "404" in str(exc):
                continue  # not a Crossref DOI (for example a DataCite one): nothing to report
            unreachable.append(doi)
            continue
        for n in items:
            k = kind(n)
            if k in RETRACTED or k in FLAGGED:
                found.append({"doi": doi, "records": sorted(recs), "notice": k, "notice_doi": n.get("DOI"),
                              "source": n.get("source"), "status": "retracted" if k in RETRACTED else "flagged"})
    found.sort(key=lambda f: (f["status"] != "retracted", f["doi"]))
    held = sorted({r for f in found if f["status"] == "retracted" for r in f["records"]})
    report = {"check": "retractions", "papers": len(papers), "held_records": held,
              "counts": {"retracted": sum(f["status"] == "retracted" for f in found),
                         "flagged": sum(f["status"] == "flagged" for f in found), "unreachable": len(unreachable)},
              "found": found, "unreachable": unreachable}
    write_report(reports_dir, "retractions", report)
    return report
