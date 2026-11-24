"""Your actions: one short weekly list of everything waiting on the owner, put at the top of the nightly digest.

Covers: open review pull requests; other open pull requests waiting for a merge or a Ship it tick, or where Ship it
asked for something; the drafting computer's readiness report (missing, stale or with a "no"); and workflows whose
latest run failed. Each line links to the page where the action happens.

Usage: python3 -m kgkit.owner_actions --report reports/nightly.md [--bot varioso-bot]
Reads GitHub with the gh tool (GH_TOKEN). Exit 0 always: a failed lookup becomes a line, never a failed nightly.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

NOTE = re.compile(r"<!-- ship-it note=([a-z]+)")
NEEDS = {"workflows": "merge it yourself (it changes the automation)", "base": "it is not aimed at main",
         "unapproved": "tick Ship it again", "toolarge": "merge it yourself (too many files)",
         "void": "it changed after your tick: tick Ship it again", "conflict": "conflict with main, being fixed",
         "failed": "tests failed, being fixed", "updatefailed": "could not be brought up to date: merge it yourself",
         "refused": "GitHub refused the merge: check the Ship it bypass entry", "review": "merge it yourself",
         "records": "edit any tick so the review sync rebuilds the records"}
STUDIO_LABELS = {"settings": "settings file", "settings_private": "settings file private", "lms": "LM Studio tool",
                 "server": "model server", "key_ok": "API key", "model_loaded": "model loaded",
                 "local_only": "server only on this computer", "scheduled": "daily job"}
WAITING_OK = {"merged"}


def gh_json(*args: str):
    out = subprocess.run(["gh", "api", *args], capture_output=True, text=True, check=True).stdout
    return json.loads(out or "null")


def studio_lines(status: dict | None, now: dt.datetime) -> list[str]:
    if not status:
        return ["Drafting computer: no readiness report yet (run step 7 of docs/studio-drafting.md once)."]
    lines = []
    try:
        checked = dt.datetime.fromisoformat(status["checked_at"].replace("Z", "+00:00"))
        if now - checked > dt.timedelta(days=3):
            lines.append(f"Drafting computer: last report {checked:%d %b}; is it on and is the daily job running?")
    except (KeyError, ValueError):
        lines.append("Drafting computer: readiness report unreadable.")
    bad = [label for key, label in STUDIO_LABELS.items() if status.get(key) == "no"]
    if bad:
        lines.append("Drafting computer: not ready (" + ", ".join(bad) + ").")
    return lines


def pr_lines(prs: list[dict], notes: dict[int, str | None], bot: str) -> list[str]:
    lines = []
    for p in prs:
        url, title, n = p["html_url"], p["title"], p["number"]
        if p.get("draft"):
            continue
        last = notes.get(n)
        if last and last not in WAITING_OK:
            lines.append(f"#{n} {title}: {NEEDS.get(last, 'needs a look')} {url}")
        elif title.startswith("Nightly proposals"):
            lines.append(f"Review waiting: {title} {url}")
        elif p["user"]["login"] != bot:
            lines.append(f"#{n} {title}: waiting for your merge or Ship it tick {url}")
    return lines


def failing_lines(runs: list[dict]) -> list[str]:
    latest: dict[str, dict] = {}
    for r in runs:                                     # newest first from the API
        if r.get("status") == "completed" and r.get("event") != "pull_request":
            latest.setdefault(r["name"], r)
    return [f"Workflow failing: {name} {r['html_url']}" for name, r in sorted(latest.items())
            if r.get("conclusion") == "failure"]


def build(repo: str, bot: str, now: dt.datetime) -> list[str]:
    lines: list[str] = []
    try:
        prs = gh_json(f"repos/{repo}/pulls?state=open&per_page=50")
        notes = {}
        for p in prs:
            comments = gh_json(f"repos/{repo}/issues/{p['number']}/comments?per_page=100")
            mine = [c for c in comments if c["user"]["type"] == "Bot"]
            approved_at = max((c.get("updated_at") or "" for c in mine if "ship-it approved=" in (c.get("body") or "")),
                              default="")
            found = [m.group(1) for c in mine if (c.get("created_at") or "") > approved_at   # notes since the last tick
                     for m in NOTE.finditer(c.get("body") or "")]
            notes[p["number"]] = found[-1] if found else None
        lines += pr_lines(prs, notes, bot)
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError):
        lines.append("Pull requests: could not be read this time.")
    try:
        f = gh_json(f"repos/{repo}/contents/status/studio.json?ref=studio-status")
        status = json.loads(base64.b64decode(f["content"]).decode())
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        status = None
    lines += studio_lines(status, now)
    try:
        since = (now - dt.timedelta(days=7)).strftime("%Y-%m-%d")
        runs = gh_json(f"repos/{repo}/actions/runs?per_page=100&created=>={since}").get("workflow_runs", [])
        lines += failing_lines(runs)
    except (subprocess.CalledProcessError, json.JSONDecodeError, AttributeError):
        lines.append("Workflow runs: could not be read this time.")
    return lines


def insert(report: str, lines: list[str]) -> str:
    """Put the section right under the digest's first line, so a length cut never drops it."""
    block = ["", "## Your actions", "", *(f"- {x}" for x in lines or ["Nothing is waiting on you."]), ""]
    head, _, rest = report.partition("\n")
    return "\n".join([head, *block]) + ("\n" + rest if rest else "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kgkit.owner_actions", description=__doc__.splitlines()[0])
    ap.add_argument("--report", required=True)
    ap.add_argument("--repo", default=None)
    ap.add_argument("--bot", default="varioso-bot")
    args = ap.parse_args(argv)
    repo = args.repo
    if not repo:
        try:
            repo = subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
                                  capture_output=True, text=True, check=True).stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return 0
    path = Path(args.report)
    text = path.read_text(encoding="utf-8") if path.exists() else "Nightly run\n"
    path.write_text(insert(text, build(repo, args.bot, dt.datetime.now(dt.timezone.utc))), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
