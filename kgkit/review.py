"""One merge per review: the proposals pull request itself carries the record changes for the ticked items.

sync     Rebuilds the record changes on the pull request's branch from what is ticked now: the records folder is
         reset to main, then the ticked items are applied exactly as the nightly apply step would. Run when the
         pull request opens (for pre-ticked items) and each time the owner edits its ticks. Merging the pull request
         then puts the ticked items live; the nightly sees the number in records/applied_prs.json and skips it.
append   Adds new items (for example drafts of entries approved last week) to the end of an open proposals pull
         request without touching what is already there: existing ticks and reason lines stay as they are.

Usage:
  python3 -m kgkit.review sync --config kit.yaml --records records/x.json --pr 23 --body-file body.md --base origin/main
  python3 -m kgkit.review append --body-file body.md --proposals reports/proposals.json --new new.json --out-body new_body.md
Exit codes: 0 done; 2 bad input.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import apply, proposals


def run_cmd(args: list[str]) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def sync(config: str, records: str, pr: int, body_file: str, proposals_file: str, base: str, runner=run_cmd) -> int:
    folder = str(Path(records).parent)
    runner(["git", "checkout", base, "--", folder])  # start from main's records, so unticking undoes a change
    return apply.main(["--config", config, "--records", records, "--body", body_file, "--proposals", proposals_file,
                       "--label", str(pr)])


def append(body: str, report: dict, new: list[dict]) -> tuple[str, dict]:
    """Returns the new pull request text and proposals report with `new` added after the existing items."""
    old = report.get("proposals", [])
    start = len(old) + 1
    lines = [body.rstrip(), "", f"# Added on a later run ({len(new)})", "",
             "_Added after this pull request opened, for example drafts of entries approved earlier._", ""]
    md = proposals.to_markdown(new).split("\n")
    # renumber the new items so they follow the existing ones; skip the header block of the stand-alone view
    first = next((i for i, x in enumerate(md) if x.startswith("## ")), len(md))
    for x in md[first:]:
        if x.startswith("## ") and ". " in x:
            n, rest = x[3:].split(". ", 1)
            if n.isdigit():
                x = f"## {int(n) + start - 1}. {rest}"
        lines.append(x)
    merged = dict(report, proposals=old + new, count=len(old) + len(new))
    return "\n".join(lines).rstrip() + "\n", merged


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kgkit.review", description="One merge per review: sync ticks, append items")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sync")
    s.add_argument("--config", required=True)
    s.add_argument("--records", required=True)
    s.add_argument("--pr", type=int, required=True)
    s.add_argument("--body-file", required=True)
    s.add_argument("--proposals", default="reports/proposals.json")
    s.add_argument("--base", default="origin/main")
    a = sub.add_parser("append")
    a.add_argument("--body-file", required=True)
    a.add_argument("--proposals", required=True)
    a.add_argument("--new", required=True)
    a.add_argument("--out-body", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "sync":
        try:
            return sync(args.config, args.records, args.pr, args.body_file, args.proposals, args.base)
        except subprocess.CalledProcessError as exc:
            print(f"error: could not reset the records to {args.base}: {exc}", file=sys.stderr)
            return 2
    try:
        body = Path(args.body_file).read_text(encoding="utf-8")
        report = json.loads(Path(args.proposals).read_text(encoding="utf-8"))
        new = json.loads(Path(args.new).read_text(encoding="utf-8")).get("proposals", [])
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not new:
        Path(args.out_body).write_text(body, encoding="utf-8")
        return 0
    text, merged = append(body, report, new)
    Path(args.out_body).write_text(text, encoding="utf-8")
    Path(args.proposals).write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
