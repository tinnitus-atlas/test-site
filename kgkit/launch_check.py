"""Launch check: one list of what stands between the test site and a public launch.

Each line is a blocker (the site must not launch), a warning (launch is allowed, with a reason shown) or done.
Reads only the config and the records file; changes nothing.

Usage: python3 -m kgkit.launch_check --config kit.tinnitus.yaml --records records/tinnitus.records.json [--report out.md]
Exit 0 when nothing blocks, 1 when something does, 2 on bad input.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from kgkit.common import KitError, load_config, load_records

BLOCK, WARN, DONE = "blocker", "warning", "done"
EMAIL = re.compile(r"[^@\s<>\"']+@[^@\s<>\"']+\.[A-Za-z]{2,}")
TOKEN = re.compile(r"[A-Za-z0-9]{16,64}")


def check(cfg: dict, records: list[dict]) -> list[tuple[str, str, str]]:
    """Return (state, item, what to do) for every launch item, blockers first."""
    s = cfg.get("site") or {}
    out = []

    def add(ok: bool, item: str, fix: str, severity: str = BLOCK):
        out.append((DONE if ok else severity, item, "" if ok else fix))

    add(bool(s.get("licence_decided")) and bool(s.get("licence_data")), "Data licence chosen",
        "choose the data licence, then set licence_data and licence_decided: true")
    add(bool(EMAIL.fullmatch(str(s.get("contact_email") or "").strip())), "Corrections address published",
        "set contact_email to a role address (for example corrections@ your domain), not a personal one")
    base = str(s.get("base_url") or "")
    host = urlparse(base).hostname or ""
    add(base.startswith("https://") and bool(host), "Site address set", "set base_url to the site's https address")
    add(bool(host) and not host.endswith(".pages.dev"), "Own domain",
        "connect a domain in Cloudflare Pages and set base_url to it; launching on the pages.dev address is allowed", WARN)
    add(not s.get("test_site"), "Test mode off", "set test_site: false (this is the switch that launches the site)")
    target = int(s.get("launch_target_records") or 0)
    add(len(records) >= target, f"Records: {len(records)} of {target}",
        "launch as a pilot or wait for more records; the pilot banner says so on every page", WARN)
    add(bool(s.get("clinical_review")), "Clinician review",
        "no clinician has reviewed the records: the site shows the Pilot banner until clinical_review: true", WARN)
    token = str(s.get("analytics_token") or "").strip()
    add(bool(TOKEN.fullmatch(token)), "Visit statistics",
        "optional: add a Cloudflare Web Analytics site token as analytics_token" if not token else
        "analytics_token is not a valid token: it is ignored", WARN)
    order = {BLOCK: 0, WARN: 1, DONE: 2}
    return sorted(out, key=lambda x: order[x[0]])


def render(items: list[tuple[str, str, str]]) -> str:
    icon = {BLOCK: "❌", WARN: "⚠️", DONE: "✅"}
    blockers = sum(1 for st, _, _ in items if st == BLOCK)
    head = "Ready to launch." if not blockers else f"Not ready: {blockers} blocker{'s' if blockers != 1 else ''}."
    lines = ["## Launch check", "", head, ""]
    lines += [f"- {icon[st]} {item}" + (f": {fix}" if fix else "") for st, item, fix in items]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="List what stands between the test site and launch")
    ap.add_argument("--config", required=True)
    ap.add_argument("--records", required=True)
    ap.add_argument("--report", help="also write the list to this markdown file")
    args = ap.parse_args(argv)
    try:
        items = check(load_config(args.config), load_records(args.records))
    except KitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    text = render(items)
    print(text, end="")
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
    return 1 if any(st == BLOCK for st, _, _ in items) else 0


if __name__ == "__main__":
    sys.exit(main())
