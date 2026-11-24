"""Re-review: send the items of an earlier proposals pull request through the screener again, in a fresh pull request.

Use it for a pull request that was merged with nothing ticked, or to look again at items that were skipped. Items
that are already in the graph (a trial or device with the same identifier, a registry value already applied) are
left out, and so are items already listed in an open proposals pull request. The new list carries "replaces": [<old number>], so merging it settles the old pull request for the apply
step. Nothing is changed until a person ticks and merges, as with every proposals pull request.

Usage:
  python3 -m kgkit.rereview --config kit.yaml --records records/x.json --reports reports --pr 12 [--only-skipped]
Exit codes: 0 written (also with zero items); 2 bad input or the pull request could not be read.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import proposals
from .apply import get_field, report_at, run_cmd
from .common import KitError, load_config, load_records, write_report
from .decisions import key_of, load_history
from .screener import screen


def already_in_graph(p: dict, records: list[dict]) -> bool:
    a = p.get("apply") or {}
    if p.get("type") == "update":
        rec = next((r for r in records if r.get("id") == a.get("record")), None)
        return rec is None or get_field(rec, a.get("field", "")) == a.get("to")
    if p.get("type") == "new_record":
        new = a.get("new_record") or {}
        xrefs = set(new.get("xrefs") or [])
        if xrefs & {x for r in records for x in r.get("xrefs") or []}:
            return True
        key = new.get("key")
        fact = new.get("key_fact")
        return bool(key and fact and any(str(((r.get("facts") or {}).get(fact) or {}).get("value")) == str(key) for r in records))
    return False


def build(records: list[dict], cfg: dict, number: int, runner, reports_dir, only_skipped: bool, history: list[dict],
          open_keys: set[str] | None = None) -> dict:
    info = json.loads(runner(["gh", "pr", "view", str(number), "--json", "number,title,state,mergeCommit,headRefOid"]))
    commit = (info.get("mergeCommit") or {}).get("oid") or info.get("headRefOid")
    if not commit:
        raise KitError(f"pull request #{number} has no commit to read")
    if not str(info.get("title") or "").startswith("Nightly proposals"):
        raise KitError(f"pull request #{number} is not a proposals pull request")
    runner(["git", "fetch", "-q", "origin", commit])
    old = report_at(runner, commit).get("proposals", [])
    decided = {h["key"]: h["decision"] for h in history if h.get("pull_request") == number}
    keep, dropped = [], {"in_graph": 0, "not_skipped": 0, "in_open_pull_request": 0}
    for p in old:
        p = {k: v for k, v in p.items() if k not in ("screen", "auto_apply")}
        if already_in_graph(p, records):
            dropped["in_graph"] += 1
            continue
        if open_keys and key_of(p) in open_keys:
            dropped["in_open_pull_request"] += 1
            continue
        if only_skipped and decided.get(key_of(p)) not in (None, "skipped"):
            dropped["not_skipped"] += 1
            continue
        p["why"] = f"Sent again from pull request #{number} for a second look. " + p.get("why", "")
        p["auto_apply"] = False
        keep.append(p)
    screen(keep, cfg, history)
    reports = Path(reports_dir)
    reports.mkdir(parents=True, exist_ok=True)
    write_report(reports, "proposals", {"check": "proposals", "mode": "re-review", "replaces": [number],
                                        "count": len(keep), "auto_apply": 0, "already_reviewed_skipped": 0,
                                        "proposals": keep})
    (reports / "proposals.md").write_text(proposals.to_markdown(keep), encoding="utf-8")
    return {"count": len(keep), "dropped": dropped, "replaces": number}


def main(argv: list[str] | None = None, runner=None) -> int:
    ap = argparse.ArgumentParser(prog="kgkit.rereview", description="Send an earlier proposals pull request through the screener again")
    ap.add_argument("--config", required=True)
    ap.add_argument("--records", required=True)
    ap.add_argument("--reports", default="reports")
    ap.add_argument("--pr", type=int, required=True)
    ap.add_argument("--only-skipped", action="store_true", help="only items that were skipped (or never decided)")
    args = ap.parse_args(argv)
    try:
        cfg = load_config(args.config)
        records = load_records(args.records)
        from .backfill import open_proposal_keys
        run = runner or run_cmd
        res = build(records, cfg, args.pr, run, args.reports, args.only_skipped, load_history(args.records),
                    open_proposal_keys(run))
    except KitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"error: could not read pull request #{args.pr}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
