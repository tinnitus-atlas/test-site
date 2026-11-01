"""Proposals: turn fact-check mismatches and feed findings into changes a non-specialist can judge.

Each proposal says what it claims, why it surfaced, the evidence and its source, when it would be wrong,
a confidence band, and exactly what to change. Proposals are regenerated every run against the current
records, so a change already applied is never proposed again. Nothing is applied unless the configuration
lists the source in proposals.auto_apply_sources (default: none).
"""
from __future__ import annotations

from .common import fact_value, read_report, write_report

CONFIDENCE = {"high": "high", "medium": "medium", "low": "medium"}


def current_value(record: dict, field: str):
    if field.startswith("facts."):
        return fact_value(record, field.split(".", 1)[1])
    return record.get(field)


def from_factcheck(fc: dict, records_by_id: dict) -> list[dict]:
    out = []
    for p in (fc or {}).get("patches") or []:
        rec = records_by_id.get(p["record"])
        if rec is None or current_value(rec, p["field"]) == p["proposed"]:
            continue  # record gone, or the change has already been applied
        out.append({
            "type": "update",
            "record": p["record"],
            "claim": f"{rec.get('name')}: {p['field']} should be '{p['proposed']}' (currently '{p['current']}')",
            "why": "The nightly fact-check found the registry disagrees with the record",
            "evidence": p["reason"],
            "source": p["source"],
            "wrong_if": "the registry entry is outdated or the record intentionally uses a different, sourced value",
            "confidence": CONFIDENCE.get(p.get("severity"), "medium"),
            "apply": {"record": p["record"], "field": p["field"], "from": p["current"], "to": p["proposed"]},
            "origin": "clinicaltrials_gov_v2",
        })
    return out


def from_feeds(feeds: dict) -> list[dict]:
    out = []
    for t in ((feeds or {}).get("trials") or {}).get("candidates") or []:
        out.append({
            "type": "new_record", "record": None,
            "claim": f"Add trial {t['nct']}: {t.get('title')}",
            "why": "A registered study for this condition is not in the knowledge graph yet",
            "evidence": f"Status {t.get('status')}, phase {t.get('phase') or 'not given'}, sponsor {t.get('sponsor') or 'not given'}, last updated {t.get('last_update')}",
            "source": t["url"],
            "wrong_if": "the study is only loosely related to the condition (for example it lists it as one of many)",
            "confidence": "medium",
            "apply": {"new_record": {"kind": "trial", "name": t.get("title"), "xrefs": [f"CLINICALTRIALS:{t['nct']}"],
                                     "status": t.get("status")}},
            "origin": "clinicaltrials_gov_v2",
        })
    for d in ((feeds or {}).get("devices") or {}).get("candidates") or []:
        date = d.get("decision_date")
        out.append({
            "type": "new_record", "record": None,
            "claim": f"Add device {d['number']}: {d.get('device_name')} ({d.get('applicant')})",
            "why": "An FDA device decision under a tinnitus-related product code is not in the knowledge graph yet",
            "evidence": f"FDA decision '{d.get('decision')}' on {date}, product code {d.get('product_code')}",
            "source": d["url"],
            "wrong_if": "the device only lists tinnitus among many uses, or the record duplicates an existing device under another name",
            "confidence": "medium",
            "apply": {"new_record": {
                "kind": "device", "name": d.get("device_name"), "key": d["number"], "key_fact": "fda_submission_number",
                "link_predicate": "related_to",
                "facts": {"fda_submission_number": {"value": d["number"], "source": d["url"]},
                          "fda_decision": {"value": d.get("decision"), "source": d["url"]},
                          "fda_decision_date": {"value": date, "source": d["url"]},
                          "fda_product_code": {"value": d.get("product_code"), "source": d["url"]}}}},
            "origin": "openfda_device",
        })
    for p in ((feeds or {}).get("papers") or {}).get("candidates") or []:
        ident = f"doi:{p['doi']}" if p.get("doi") else f"PMID:{p['pmid']}"
        out.append({
            "type": "review_paper", "record": None,
            "claim": f"Review new paper for relevant claims: {p.get('title')}",
            "why": "A new paper matching the condition query was published and is not cited yet",
            "evidence": f"{p.get('journal') or 'Journal not given'}, first published {p.get('published')}",
            "source": p["url"],
            "wrong_if": "the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter",
            "confidence": "low",
            "apply": {"cite": ident},
            "origin": "europe_pmc",
        })
    return out


def to_markdown(props: list[dict]) -> str:
    lines = ["# Proposed changes", "", f"{len(props)} proposals. Approve by merging; reject by deleting the line.", ""]
    for i, p in enumerate(props, 1):
        lines += [f"## {i}. {p['claim']}", "",
                  f"- **Why it surfaced:** {p['why']}",
                  f"- **Evidence:** {p['evidence']} ([source]({p['source']}))",
                  f"- **Wrong if:** {p['wrong_if']}",
                  f"- **Confidence:** {p['confidence']}",
                  f"- **To apply:** `{p['apply']}`",
                  f"- [ ] Approved", ""]
    return "\n".join(lines)


def run(records: list[dict], cfg: dict, reports_dir) -> dict:
    by_id = {r["id"]: r for r in records if r.get("id")}
    props = from_factcheck(read_report(reports_dir, "factcheck"), by_id) + from_feeds(read_report(reports_dir, "feeds"))
    order = {"high": 0, "medium": 1, "low": 2}
    props.sort(key=lambda p: (order.get(p["confidence"], 3), p["type"], p["claim"]))
    auto = set((cfg.get("proposals") or {}).get("auto_apply_sources") or [])
    for p in props:
        p["auto_apply"] = p["origin"] in auto and p["type"] == "update"
    report = {"check": "proposals", "count": len(props), "auto_apply": sum(p["auto_apply"] for p in props),
              "proposals": props}
    write_report(reports_dir, "proposals", report)
    from pathlib import Path
    (Path(reports_dir) / "proposals.md").write_text(to_markdown(props), encoding="utf-8")
    return report
