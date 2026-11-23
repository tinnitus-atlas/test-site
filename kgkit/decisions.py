"""Decision history and "Maybe later" items.

records/decisions.jsonl   one line per reviewed proposal: what it was, its source link, the decision (approved,
                          skipped or maybe_later), the pull request and the date. Searchable later, never shown on
                          the website, and the history the screener learns from.
records/parked.json       proposals ticked "Maybe later": kept out of the seen list and proposed again when due
                          (default 90 days). An item parked a second time counts as skipped.

Rebuild the history from every merged proposals pull request (for example after this file was added):
  python3 -m kgkit.decisions --config kit.yaml --records records/x.json --rebuild-from-github
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

from .common import KitError, load_config, load_records
from .proposals import proposal_key
from .screener import bucket, title_of

HEADING = re.compile(r"^## (\d+)\. (.+)$")
MAYBE = re.compile(r"^- \[([ xX])\] Maybe later\s*$")
PARK_DAYS = 90


def maybe_numbers(body: str) -> set[int]:
    out, current = set(), None
    for line in (body or "").splitlines():
        h = HEADING.match(line.strip())
        if h:
            current = int(h.group(1))
            continue
        m = MAYBE.match(line.strip())
        if m and current is not None and m.group(1).lower() == "x":
            out.add(current)
    return out


def key_of(p: dict) -> str:
    k = proposal_key(p)
    if k:
        return k
    a = p.get("apply") or {}
    if p.get("type") == "update":
        return f"update:{a.get('record')}:{a.get('field')}:{a.get('to')}"
    if p.get("type") == "draft":
        return f"draft:{a.get('record')}"
    return f"{p.get('type')}:{p.get('claim')}"


def history_path(records_path: str | Path) -> Path:
    return Path(records_path).parent / "decisions.jsonl"


def parked_path(records_path: str | Path) -> Path:
    return Path(records_path).parent / "parked.json"


def load_history(records_path) -> list[dict]:
    p = history_path(records_path)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def load_parked(records_path) -> list[dict]:
    p = parked_path(records_path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def entries(label, props: list[dict], approved: set[int], maybe: set[int], day: str) -> list[dict]:
    out = []
    for i, p in enumerate(props, 1):
        decision = "approved" if i in approved else "maybe_later" if i in maybe else "skipped"
        out.append({"key": key_of(p), "type": p.get("type"), "title": title_of(p), "claim": p.get("claim"),
                    "source": p.get("source"), "decision": decision, "pull_request": label, "date": day,
                    "bucket": bucket(p), "screen": (p.get("screen") or {}).get("score"),
                    "pre_ticked": (p.get("screen") or {}).get("pre_ticked", False)})
    return out


def update_parked(parked: list[dict], props: list[dict], approved: set[int], maybe: set[int], day: str) -> tuple[list[dict], set[str]]:
    """Returns the new parked list and the keys that become final (approved, skipped, or parked twice)."""
    by_key = {x["key"]: x for x in parked}
    final: set[str] = set()
    due = (dt.date.fromisoformat(day) + dt.timedelta(days=PARK_DAYS)).isoformat()
    for i, p in enumerate(props, 1):
        k = key_of(p)
        if i in maybe and i not in approved:
            prev = by_key.get(k)
            if prev and prev.get("times", 1) >= 1 and prev.get("parked_on") != day:
                by_key.pop(k)
                final.add(k)  # parked a second time: treat as skipped
            else:
                clean = {kk: v for kk, v in p.items() if kk not in ("screen", "auto_apply")}
                by_key[k] = {"key": k, "proposal": clean, "parked_on": day, "due": due, "times": 1}
        else:
            by_key.pop(k, None)
            final.add(k)
    return list(by_key.values()), final


def write_history(records_path, new: list[dict]) -> None:
    if not new:
        return
    p = history_path(records_path)
    have = {(h["key"], str(h.get("pull_request"))) for h in load_history(records_path)}
    lines = [json.dumps(e, ensure_ascii=False) for e in new if (e["key"], str(e["pull_request"])) not in have]
    if lines:
        with p.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def write_parked(records_path, parked: list[dict]) -> None:
    parked_path(records_path).write_text(json.dumps(parked, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def due_parked(parked: list[dict], day: str) -> tuple[list[dict], set[str]]:
    """Proposals whose Maybe later time is up, and the keys still parked (not to be proposed yet)."""
    due, waiting = [], set()
    for x in parked:
        if x.get("due", "9999") <= day:
            p = dict(x["proposal"])
            p["why"] = f"Marked Maybe later on {x['parked_on']}; due again. " + p.get("why", "")
            due.append(p)
        else:
            waiting.add(x["key"])
    return due, waiting


def rebuild(records_path, runner, limit: int = 200) -> int:
    from .apply import approved_numbers, merged_proposal_prs, proposals_at
    new = []
    for pr in merged_proposal_prs(runner, limit=limit):
        commit = (pr.get("mergeCommit") or {}).get("oid")
        if not commit:
            continue
        try:
            props = proposals_at(runner, commit)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        body = pr.get("body") or ""
        day = (pr.get("mergedAt") or "")[:10] or dt.date.today().isoformat()
        new += entries(pr["number"], props, set(approved_numbers(body)), maybe_numbers(body), day)
    write_history(records_path, new)
    return len(new)


def main(argv: list[str] | None = None, runner=None) -> int:
    from .apply import run_cmd
    ap = argparse.ArgumentParser(prog="kgkit.decisions", description="Decision history of reviewed proposals")
    ap.add_argument("--config", required=True)
    ap.add_argument("--records", required=True)
    ap.add_argument("--rebuild-from-github", action="store_true")
    args = ap.parse_args(argv)
    try:
        load_config(args.config)
        load_records(args.records)
    except KitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not args.rebuild_from_github:
        h = load_history(args.records)
        counts = {d: sum(1 for x in h if x["decision"] == d) for d in ("approved", "skipped", "maybe_later")}
        print(json.dumps({"decisions": len(h), **counts, "parked": len(load_parked(args.records))}))
        return 0
    try:
        n = rebuild(args.records, runner or run_cmd)
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"error: could not read merged pull requests: {exc}", file=sys.stderr)
        return 2
    print(f"decision history: {n} entries read from merged pull requests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
