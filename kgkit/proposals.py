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


SEEN_TYPES = {"new_record", "review_paper"}  # feed findings; registry updates track the records themselves


def proposal_key(p: dict) -> str | None:
    """Stable identity of a feed proposal across nights (a trial number, device number or paper id)."""
    a = p.get("apply") or {}
    if p["type"] == "review_paper" and a.get("cite"):
        return f"review_paper:{str(a['cite']).lower()}"
    if p["type"] == "new_record":
        rec = a.get("new_record") or {}
        ident = rec.get("key") or ((rec.get("xrefs") or [None])[0])
        if ident:
            return f"new_record:{rec.get('kind', 'trial')}:{str(ident).lower()}"
    return None


GROUPS = [("tick", "Recommended: tick", "Already ticked when the screener is sure. Scan the titles, untick any you disagree with."),
          ("fence", "On the fence", "Open only when you have time. Items left unticked here stay open and come back next week."),
          ("skip", "Recommended: skip", "Items left unticked here are saved in the decision history as skipped; Re-review can bring them back."),
          (None, "Not screened", "")]


def to_markdown(props: list[dict]) -> str:
    """One short block per item (title, recommendation, the two boxes) with the details folded away, grouped so the
    recommended items come first. Item headings stay "## <number>. <claim>": the apply step reads them."""
    counts = {g: sum(1 for p in props if (p.get("screen") or {}).get("recommendation") == g) for g, *_ in GROUPS}
    pre = sum(1 for p in props if (p.get("screen") or {}).get("pre_ticked"))
    lines = ["# Proposed changes", "",
             f"{len(props)} items: {counts['tick']} recommended ({pre} already ticked), {counts['fence']} on the fence, "
             f"{counts['skip']} recommended to skip.", "",
             "How to review: tick **Approved** to add an item, **Maybe later** to see it again in 90 days, or add a line "
             "starting `Reason:` under an item to tell the screener why. Then merge. Your merge is the approval.", ""]
    numbered = list(enumerate(props, 1))
    for key, title, hint in GROUPS:
        items = [(i, p) for i, p in numbered if (p.get("screen") or {}).get("recommendation") == key]
        if not items:
            continue
        if any(p.get("screen") for _, p in numbered):
            lines += [f"# {title} ({len(items)})", "", *([f"_{hint}_", ""] if hint else [])]
        for i, p in items:
            lines += item_lines(i, p)
    return "\n".join(lines)


def detail_lines(p: dict) -> list[str]:
    """The item's data as the reviewer sees it. The apply step checks these lines in the reviewed text against the
    data it is about to apply, so the data cannot differ from what was read."""
    return [f"- **Why it surfaced:** {p['why']}",
            f"- **Evidence:** {p['evidence']} ([source]({p['source']}))",
            f"- **Wrong if:** {p['wrong_if']}",
            f"- **Confidence:** {p['confidence']}",
            f"- **To apply:** `{p['apply']}`"]


def item_lines(i: int, p: dict) -> list[str]:
    from .screener import line as screen_line
    s = screen_line(p)
    ticked = "x" if (p.get("screen") or {}).get("pre_ticked") else " "
    return [f"## {i}. {p['claim']}", "",
            *([s] if s else []),
            f"- [{ticked}] Approved",
            "- [ ] Maybe later", "",
            "<details><summary>Details and source</summary>", "",
            *detail_lines(p), "",
            "</details>", ""]


def run(records: list[dict], cfg: dict, reports_dir, seen: set[str] | None = None,
        parked: list[dict] | None = None, history: list[dict] | None = None, today: str | None = None) -> dict:
    import datetime as dt
    from .decisions import due_parked
    from .screener import screen
    by_id = {r["id"]: r for r in records if r.get("id")}
    props = from_factcheck(read_report(reports_dir, "factcheck"), by_id) + from_feeds(read_report(reports_dir, "feeds"))
    due, waiting = due_parked(parked or [], today or dt.date.today().isoformat())
    suppressed, parked_waiting = 0, 0
    kept, keys = [], set()
    for p in props:
        k = proposal_key(p) if p["type"] in SEEN_TYPES else None
        if k and seen and k in seen:
            suppressed += 1
        elif k and k in waiting:
            parked_waiting += 1
        else:
            kept.append(p)
            if k:
                keys.add(k)
    for p in due:  # Maybe later items whose time is up come back even if the feeds no longer list them
        k = proposal_key(p)
        if not (k and (k in keys or (seen and k in seen))):
            kept.append(p)
    props = kept
    order = {"high": 0, "medium": 1, "low": 2}
    props.sort(key=lambda p: (order.get(p["confidence"], 3), p["type"], p["claim"]))
    screen(props, cfg, history)
    auto = set((cfg.get("proposals") or {}).get("auto_apply_sources") or [])
    for p in props:
        p["auto_apply"] = p["origin"] in auto and p["type"] == "update"
    report = {"check": "proposals", "count": len(props), "auto_apply": sum(p["auto_apply"] for p in props),
              "already_reviewed_skipped": suppressed, "parked_waiting": parked_waiting, "parked_due": len(due),
              "pre_ticked": sum(1 for p in props if (p.get("screen") or {}).get("pre_ticked")), "proposals": props}
    write_report(reports_dir, "proposals", report)
    from pathlib import Path
    (Path(reports_dir) / "proposals.md").write_text(to_markdown(props), encoding="utf-8")
    return report
