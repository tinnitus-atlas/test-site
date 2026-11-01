"""DOI and quote check.

For every DOI and PMID cited in record sources and relationship publications, ask Europe PMC what the
identifier really is, compare its title with the claim that cites it, and check that each relationship's
quote appears verbatim in the abstract or title of one of its publications.

Classes per citation: confirmed, label_drift, suspect, not_indexed, unreachable.
Classes per quote:    quote_ok, quote_missing, quote_unverifiable (no indexed publication to check against).
Blocking:             suspect citations and missing quotes hold their record back from publishing.
"""
from __future__ import annotations

import re

from .common import FetchError, Http, normalise, overlap, qs, tokens, write_report

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def norm_id(raw: str) -> tuple[str, str] | None:
    """'doi:10.1/X', '10.1/X', 'https://doi.org/10.1/X' -> ('doi', '10.1/x'); 'PMID:123' or '123' -> ('pmid', '123')."""
    if not raw:
        return None
    s = str(raw).strip()
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s, flags=re.I)
    low = s.lower()
    if low.startswith("doi:"):
        return ("doi", s[4:].strip().lower())
    if low.startswith("pmid:"):
        return ("pmid", s[5:].strip())
    if s.startswith("10."):
        return ("doi", s.lower())
    if s.isdigit():
        return ("pmid", s)
    return None


def epmc_url(kind: str, value: str) -> str:
    query = f'DOI:"{value}"' if kind == "doi" else f"EXT_ID:{value} AND SRC:MED"
    return f"{EPMC}?{qs({'query': query, 'format': 'json', 'resultType': 'core', 'pageSize': 1})}"


def resolve(http: Http, kind: str, value: str) -> dict:
    """Return {'status': 'indexed'|'not_indexed'|'unreachable', ...metadata}."""
    try:
        data = http.get_json(epmc_url(kind, value))
    except FetchError as exc:
        return {"status": "unreachable", "error": str(exc)}
    results = ((data or {}).get("resultList") or {}).get("result") or []
    if not results:
        return {"status": "not_indexed"}
    r = results[0]
    journal = ((r.get("journalInfo") or {}).get("journal") or {}).get("title") or r.get("journalTitle")
    return {
        "status": "indexed",
        "title": (r.get("title") or "").rstrip("."),
        "journal": journal,
        "year": int(r["pubYear"]) if str(r.get("pubYear", "")).isdigit() else None,
        "authors": r.get("authorString"),
        "abstract": r.get("abstractText") or "",
        "doi": (r.get("doi") or "").lower() or None,
        "pmid": r.get("pmid"),
    }


def collect(records: list[dict]) -> list[dict]:
    """Every citation with the context that claims it."""
    cites = []
    for rec in records:
        context = " ".join(filter(None, [rec.get("name"), rec.get("tldr"), rec.get("summary")]))
        for src in rec.get("sources") or []:
            for field in ("doi", "pmid"):
                if src.get(field):
                    ident = norm_id(f"{field}:{src[field]}")
                    if ident:
                        cites.append({"record": rec["id"], "where": "source", "label": src.get("label", ""),
                                      "id": ident, "context": context})
        for i, rel in enumerate(rec.get("relations") or []):
            for pub in rel.get("publications") or []:
                ident = norm_id(pub)
                if ident:
                    cites.append({"record": rec["id"], "where": f"relation[{i}]", "label": rel.get("predicate", ""),
                                  "id": ident, "context": context})
    return cites


def classify(cite: dict, meta: dict) -> dict:
    if meta["status"] != "indexed":
        return {"class": meta["status"], "shared": []}
    claim = tokens(cite["label"] + " " + cite["context"])
    shared = overlap(tokens(meta["title"]), claim)
    if not shared:
        return {"class": "suspect", "shared": []}
    years = {int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", cite["label"])}
    if years and meta.get("year") and meta["year"] not in years:
        return {"class": "label_drift", "shared": shared}
    return {"class": "confirmed", "shared": shared}


def check_quotes(records: list[dict], resolved: dict) -> list[dict]:
    out = []
    for rec in records:
        for i, rel in enumerate(rec.get("relations") or []):
            quote = rel.get("quote")
            if not quote:
                continue
            ids = [norm_id(p) for p in rel.get("publications") or []]
            ids = [x for x in ids if x]
            texts = [normalise(resolved[x]["title"] + " " + resolved[x]["abstract"])
                     for x in ids if resolved.get(x, {}).get("status") == "indexed"]
            where = f"{rec['id']} relation[{i}] {rel.get('predicate')} -> {rel.get('object')}"
            if not texts:
                status = "quote_unverifiable"
            elif any(normalise(quote) in t for t in texts):
                status = "quote_ok"
            elif (rel.get("quoteVerified") or {}).get("by") and (rel.get("quoteVerified") or {}).get("on"):
                status = "quote_manual_ok"  # a person confirmed the quote against the full text
            else:
                status = "quote_missing"
            out.append({"record": rec["id"], "relation": where, "quote": quote, "class": status,
                        "source_url": rel.get("sourceUrl")})
    return out


def run(records: list[dict], http: Http, reports_dir) -> dict:
    cites = collect(records)
    resolved: dict = {}
    for c in cites:
        if c["id"] not in resolved:
            resolved[c["id"]] = resolve(http, *c["id"])
    items = []
    for c in cites:
        meta = resolved[c["id"]]
        verdict = classify(c, meta)
        items.append({"record": c["record"], "where": c["where"], "id": f"{c['id'][0]}:{c['id'][1]}",
                      "label": c["label"], "class": verdict["class"], "shared_words": verdict["shared"],
                      "indexed_title": meta.get("title"), "indexed_year": meta.get("year"),
                      "indexed_journal": meta.get("journal")})
    quotes = check_quotes(records, resolved)
    held = sorted({i["record"] for i in items if i["class"] == "suspect"} |
                  {q["record"] for q in quotes if q["class"] == "quote_missing"})
    counts: dict = {}
    for row in items + quotes:
        counts[row["class"]] = counts.get(row["class"], 0) + 1
    report = {"check": "doi", "counts": counts, "held_records": held, "citations": items, "quotes": quotes}
    write_report(reports_dir, "doi_check", report)
    return report
