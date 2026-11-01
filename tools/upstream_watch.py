#!/usr/bin/env python3
"""
Report what changed in an upstream project's quality scripts since the last check.

The kit's checks were adapted from OnCo (MIT licence). This script lets a monthly scheduled job see
whether OnCo improved any of those scripts, so useful fixes can be carried over by hand.

Usage: python3 tools/upstream_watch.py [--since 2026-10-01] [--state .cache/upstream_watch.json] [--out reports/upstream_watch.md]
Needs git and read access to GitHub. Exit codes: 0 report written (changes or not); 2 git failed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

REPO = "https://github.com/judegomila/OnCo"
WATCHED = {
    "scripts/check-link-dois.ts": "DOI check",
    "scripts/factcheck.ts": "Fact-check",
    "scripts/audit.ts": "Audit",
    "scripts/freshness.ts": "Freshness",
    "src/lib/review-due.ts": "Freshness limits",
    "scripts/propose-updates.ts": "Proposals",
    "scripts/apply-proposals.ts": "Applying proposals",
    "AGENTS.md": "Agent rules",
    ".github/REVIEWERS.md": "Review tracks",
}


def git(args: list[str], cwd: Path | None = None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Watch upstream quality scripts for changes")
    ap.add_argument("--since", help="YYYY-MM-DD; default: date of the last run, or 31 days ago")
    ap.add_argument("--state", default=".cache/upstream_watch.json")
    ap.add_argument("--cache", default=".cache/upstream")
    ap.add_argument("--out", default="reports/upstream_watch.md")
    args = ap.parse_args(argv)

    state_path = Path(args.state)
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    since = args.since or state.get("last_run") or (dt.date.today() - dt.timedelta(days=31)).isoformat()
    cache = Path(args.cache)
    # Download three weeks more history than needed: the oldest commit of a shallow download looks as if it
    # touched every file, so it must fall before the reporting window, and a same-day rerun still finds commits.
    fetch_since = (dt.date.fromisoformat(since) - dt.timedelta(days=21)).isoformat()
    try:
        if not (cache / ".git").exists() and not (cache / "HEAD").exists():
            cache.parent.mkdir(parents=True, exist_ok=True)
            git(["clone", "-q", "--bare", "--filter=blob:none", f"--shallow-since={fetch_since}", REPO, str(cache)])
        else:
            try:
                git(["fetch", "-q", f"--shallow-since={fetch_since}", "origin", "+refs/heads/main:refs/heads/main"], cwd=cache)
            except subprocess.CalledProcessError:
                git(["fetch", "-q", "--depth=300", "origin", "+refs/heads/main:refs/heads/main"], cwd=cache)
        log = git(["log", "main", f"--since={since}", "--date=short", "--format=%H%x09%ad%x09%s", "--name-only",
                   "--", *WATCHED], cwd=cache)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"error: git failed: {exc}", file=sys.stderr)
        return 2

    changes: dict[str, list[str]] = {}
    commit = None
    for line in log.splitlines():
        if "\t" in line:
            sha, date, subject = line.split("\t", 2)
            commit = f"{date} {subject} ({REPO}/commit/{sha[:10]})"
        elif line.strip() in WATCHED and commit:
            changes.setdefault(line.strip(), []).append(commit)

    lines = [f"# Upstream watch: OnCo quality scripts since {since}", ""]
    if not changes:
        lines.append("No changes to the watched scripts. Nothing to carry over.")
    else:
        lines.append(f"{sum(len(v) for v in changes.values())} commits touched {len(changes)} watched files. "
                     "Read each and decide whether the kit needs the same fix.")
        for path, commits in changes.items():
            lines += ["", f"## {WATCHED[path]} ({path})"] + [f"- {c}" for c in commits[:15]]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"last_run": dt.date.today().isoformat()}))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
