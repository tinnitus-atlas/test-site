"""Apply approved proposals to the records. Closes the approval loop.

How approval works: the nightly pull request carries proposals.md as its description. Each proposal has a
"- [ ] Approved" box. A person ticks the boxes they accept (GitHub lets you tick them directly in the pull
request description) and merges. This script then reads the merged pull request's description, finds the
ticked proposals, and applies only those.

Rules:
  update        sets the field only if the record still holds the value the proposal expected ("from");
                otherwise it is reported as a conflict and skipped. The record's asOf becomes today and the
                evidence URL is added to its sources.
  new_record    adds a draft record (for example a new trial) linked to the configured condition record;
                skipped if a record with the same id or registry identifier already exists.
  review_paper  adds the paper to records/review_queue.json for a person or agent to read; it never edits
                the records directly.
Each pull request is applied once; its number is stored in records/applied_prs.json.
Every feed proposal (new record or paper) in a merged pull request, ticked or not, is added to
records/seen_proposals.json so that ignored items are not proposed again.

Usage:
  python3 -m kgkit.apply --config kit.yaml --records records/x.json --from-github
  python3 -m kgkit.apply --config kit.yaml --records records/x.json --body pr_body.md --proposals proposals.json --label manual-1
Exit codes: 0 applied or nothing to do; 1 applied changes broke the audit (nothing written); 2 bad input.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

from . import audit
from .common import KitError, load_config, load_records
from .proposals import SEEN_TYPES, proposal_key

HEADING = re.compile(r"^## (\d+)\. (.+)$")
TICK = re.compile(r"^- \[([ xX])\] Approved\s*$")


def approved_numbers(body: str) -> dict[int, str]:
    """Map proposal number -> heading text for every section whose Approved box is ticked."""
    out, current = {}, None
    for line in (body or "").splitlines():
        h = HEADING.match(line.strip())
        if h:
            current = (int(h.group(1)), h.group(2).strip())
            continue
        t = TICK.match(line.strip())
        if t and current:
            if t.group(1).lower() == "x":
                out[current[0]] = current[1]
            current = None
    return out


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def set_field(record: dict, field: str, value, source: str | None):
    if field.startswith("facts."):
        key = field.split(".", 1)[1]
        record.setdefault("facts", {})[key] = {"value": value, "source": source}
    else:
        record[field] = value


def get_field(record: dict, field: str):
    if field.startswith("facts."):
        fact = (record.get("facts") or {}).get(field.split(".", 1)[1])
        return fact.get("value") if isinstance(fact, dict) else fact
    return record.get(field)


def apply_selected(records: list[dict], proposals: list[dict], approved: dict[int, str], cfg: dict,
                   review_queue: list[dict], today: str) -> dict:
    by_id = {r["id"]: r for r in records}
    prefix = cfg["project"].get("prefix", "kg")
    condition = ((cfg.get("feeds") or {}).get("trials") or {}).get("condition_record")
    result = {"applied": [], "skipped": [], "conflicts": []}
    for number, heading in sorted(approved.items()):
        if number < 1 or number > len(proposals):
            result["skipped"].append({"number": number, "reason": "no proposal with this number"})
            continue
        p = proposals[number - 1]
        if p.get("claim", "").strip() != heading:
            result["skipped"].append({"number": number, "reason": "heading does not match the proposal; list was edited or reordered"})
            continue
        a = p.get("apply") or {}
        if p["type"] == "update":
            rec = by_id.get(a.get("record"))
            if rec is None:
                result["skipped"].append({"number": number, "reason": f"record {a.get('record')} no longer exists"})
            elif get_field(rec, a["field"]) != a.get("from"):
                result["conflicts"].append({"number": number, "record": rec["id"], "field": a["field"],
                                            "expected": a.get("from"), "found": get_field(rec, a["field"])})
            else:
                set_field(rec, a["field"], a["to"], p.get("source"))
                rec["asOf"] = today
                if p.get("source") and all(s.get("url") != p["source"] for s in rec.get("sources") or []):
                    rec.setdefault("sources", []).append({"url": p["source"], "label": "Registry entry (applied proposal)"})
                result["applied"].append({"number": number, "record": rec["id"], "field": a["field"], "to": a["to"]})
        elif p["type"] == "new_record":
            draft = copy.deepcopy(a.get("new_record") or {})
            xrefs = draft.get("xrefs") or []
            kind = draft.get("kind", "trial")
            key = draft.get("key") or (xrefs[0].split(":", 1)[1] if xrefs else draft.get("name", "record"))
            new_id = f"{prefix}:{kind}-{slug(key)}"
            known = {x for r in records for x in r.get("xrefs") or []}
            known_keys = {str((r.get("facts") or {}).get(draft.get("key_fact"), {}).get("value"))
                          for r in records if draft.get("key_fact")}
            if new_id in by_id or any(x in known for x in xrefs) or (draft.get("key") and str(draft["key"]) in known_keys):
                result["skipped"].append({"number": number, "reason": f"{new_id} or its identifier already exists"})
                continue
            record = {"id": new_id, "kind": kind, "name": draft.get("name") or new_id,
                      "tldr": "Draft record from a registry feed; summary still to be written.", "asOf": today,
                      "sources": [{"url": p.get("source"), "label": "Registry entry"}]}
            if xrefs:
                record["xrefs"] = xrefs
            if draft.get("status"):
                record["status"] = draft["status"]
            if draft.get("facts"):
                record["facts"] = draft["facts"]
            if condition:
                record["relations"] = [{"predicate": draft.get("link_predicate", "studies_condition"), "object": condition,
                                        "knowledgeLevel": "not_provided",
                                        "agentType": "manual_validation_of_automated_agent"}]
            records.append(record)
            by_id[new_id] = record
            result["applied"].append({"number": number, "record": new_id, "created": True})
        elif p["type"] == "review_paper":
            cite = a.get("cite")
            if any(q.get("cite") == cite for q in review_queue):
                result["skipped"].append({"number": number, "reason": f"{cite} is already in the review queue"})
                continue
            review_queue.append({"cite": cite, "title": p.get("claim", "").replace("Review new paper for relevant claims: ", ""),
                                 "url": p.get("source"), "added": today, "status": "to_read"})
            result["applied"].append({"number": number, "queued": cite})
        else:
            result["skipped"].append({"number": number, "reason": f"unknown proposal type {p.get('type')}"})
    return result


# ---------------------------------------------------------------------------
# GitHub mode
# ---------------------------------------------------------------------------

Runner = Callable[[list[str]], str]


def run_cmd(args: list[str]) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def merged_proposal_prs(runner: Runner) -> list[dict]:
    out = runner(["gh", "pr", "list", "--state", "merged", "--search", "Nightly proposals in:title",
                  "--limit", "30", "--json", "number,title,body,mergeCommit"])
    return sorted(json.loads(out or "[]"), key=lambda p: p["number"])


def proposals_at(runner: Runner, commit: str) -> list[dict]:
    return json.loads(runner(["git", "show", f"{commit}:reports/proposals.json"])).get("proposals", [])


# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None, runner: Runner = run_cmd) -> int:
    ap = argparse.ArgumentParser(prog="kgkit.apply", description="Apply approved proposals to the records")
    ap.add_argument("--config", required=True)
    ap.add_argument("--records", required=True)
    ap.add_argument("--from-github", action="store_true", help="read merged nightly pull requests with the gh tool")
    ap.add_argument("--body", help="pull request description file (manual mode)")
    ap.add_argument("--proposals", help="proposals.json file (manual mode)")
    ap.add_argument("--label", default="manual", help="identifier stored in applied_prs.json for manual mode")
    args = ap.parse_args(argv)

    try:
        cfg = load_config(args.config)
        records = load_records(args.records)
    except KitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    folder = Path(args.records).parent
    applied_path, queue_path = folder / "applied_prs.json", folder / "review_queue.json"
    seen_path = folder / "seen_proposals.json"
    seen = json.loads(seen_path.read_text()) if seen_path.exists() else []
    applied_prs = json.loads(applied_path.read_text()) if applied_path.exists() else []
    queue = json.loads(queue_path.read_text()) if queue_path.exists() else []
    today = dt.date.today().isoformat()

    batches = []
    if args.from_github:
        try:
            for pr in merged_proposal_prs(runner):
                if pr["number"] in applied_prs:
                    continue
                commit = (pr.get("mergeCommit") or {}).get("oid")
                if not commit:
                    continue
                batches.append((pr["number"], pr.get("body") or "", proposals_at(runner, commit)))
        except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as exc:
            print(f"error: could not read merged pull requests: {exc}", file=sys.stderr)
            return 2
    else:
        if not (args.body and args.proposals):
            print("error: give --from-github, or both --body and --proposals", file=sys.stderr)
            return 2
        if args.label in applied_prs:
            print(f"Already applied: {args.label}")
            return 0
        try:
            body = Path(args.body).read_text(encoding="utf-8")
            props = json.loads(Path(args.proposals).read_text(encoding="utf-8")).get("proposals", [])
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        batches.append((args.label, body, props))

    if not batches:
        print("Nothing to apply")
        return 0

    work = copy.deepcopy(records)
    report = []
    for label, body, props in batches:
        res = apply_selected(work, props, approved_numbers(body), cfg, queue, today)
        report.append({"source": label, **res})

    with tempfile.TemporaryDirectory() as tmp:
        after = set(audit.run(work, cfg, tmp)["held_records"])
        before = set(audit.run(records, cfg, tmp)["held_records"])
    new_blocking = after - before
    if new_blocking:
        print(json.dumps({"error": "applied changes would break the audit; nothing written",
                          "records": sorted(new_blocking), "report": report}, indent=2))
        return 1

    data = json.loads(Path(args.records).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data["records"] = work
    else:
        data = work
    Path(args.records).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    queue_path.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    known = {e["key"] for e in seen}
    for _, _, props in batches:
        for pr_ in props:
            k = proposal_key(pr_) if pr_.get("type") in SEEN_TYPES else None
            if k and k not in known:
                seen.append({"key": k, "reviewed": today})
                known.add(k)
    seen_path.write_text(json.dumps(seen, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    applied_path.write_text(json.dumps(applied_prs + [b[0] for b in batches], indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
