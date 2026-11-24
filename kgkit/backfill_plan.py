"""Staged backfill that runs itself: each stage starts when the previous review has been merged.

Stages (days back, oldest edge to newest edge): 183-30 (the pilot), 365-183, 730-365. A stage's review pull request
is titled "Nightly proposals backfill <since>-<until> days ...". The next stage starts only when:
- every earlier stage's review was merged (a closed, unmerged one stops the chain: the owner said no), and
- no "Nightly proposals" pull request is open (one review at a time).

Usage (from the workflow): python3 -m kgkit.backfill_plan  -> prints "since=..", "until=.." or "none=<reason>".
Set the repository variable BACKFILL_AUTO to "off" to stop the chain.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

STAGES = [(183, 30), (365, 183), (730, 365)]


def tag(since: int, until: int) -> str:
    return f"backfill {since}-{until} days"


def next_stage(prs: list[dict]) -> tuple[int, int] | str:
    """prs: [{"title", "state" (OPEN/CLOSED/MERGED)}]. Returns (since, until) or the reason nothing runs."""
    if any(p["state"] == "OPEN" and p["title"].startswith("Nightly proposals") for p in prs):
        return "a review is open"
    for since, until in STAGES:
        mine = [p for p in prs if tag(since, until) in p["title"]]
        if not mine:
            return since, until
        if any(p["state"] == "MERGED" for p in mine):
            continue
        return f"stage {since}-{until} was closed without merging"
    return "all stages done"


def main() -> int:
    if (os.environ.get("BACKFILL_AUTO") or "").lower() == "off":
        print("none=switched off")
        return 0
    out = subprocess.run(["gh", "pr", "list", "--state", "all", "--search", "Nightly proposals in:title",
                          "--limit", "200", "--json", "title,state"], capture_output=True, text=True, check=True)
    result = next_stage(json.loads(out.stdout or "[]"))
    print(f"since={result[0]}\nuntil={result[1]}" if isinstance(result, tuple) else f"none={result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
