"""Sample audit of drafted entries (gate G1): pick finished entries written by the drafting step at random and write
reports/draft_audit.md with, for each, the source link, the drafted text and quotes, and an empty verdict column a
person fills in ("ok" or the factual error found). The pass bar: at most 5 percent of the sample with a factual error.

Usage: python3 -m kgkit.draft_audit --records records/x.json --reports reports [--n 30] [--seed 1]
Exit codes: 0 written (also when there is nothing to sample yet); 2 bad input.
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from .common import KitError, load_records


def drafted(records: list[dict]) -> list[dict]:
    return [r for r in records if (r.get("provenance") or {}).get("drafted_by") and r.get("summary")]


def markdown(sample: list[dict], total: int) -> str:
    lines = ["# Draft audit", "",
             f"Sample: {len(sample)} of {total} drafted entries, picked at random. Fill in the Verdict column with "
             "\"ok\" or the factual error you found. Pass bar: at most 5 percent with a factual error.", "",
             "| # | Entry | Source | Drafted text and quotes | Verdict |", "|---|---|---|---|---|"]
    for i, r in enumerate(sample, 1):
        src = next((rel.get("sourceUrl") for rel in r.get("relations") or [] if rel.get("sourceUrl")), None) \
            or next((s.get("url") for s in r.get("sources") or [] if s.get("url")), "")
        quotes = " ".join(f"[{rel['predicate']} {rel['object']}: \"{rel['quote']}\"]"
                          for rel in r.get("relations") or [] if rel.get("quote"))
        text = f"{r.get('tldr')} {r.get('summary')} {quotes}".replace("|", "/").replace("\n", " ")
        lines.append(f"| {i} | {r['id']}: {r.get('name')} | {src} | {text} | |")
    if not sample:
        lines.append("| - | No drafted entries yet | | | |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kgkit.draft_audit", description="Random sample of drafted entries for a person to check")
    ap.add_argument("--records", required=True)
    ap.add_argument("--reports", default="reports")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int)
    args = ap.parse_args(argv)
    try:
        records = load_records(args.records)
    except KitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    pool = drafted(records)
    sample = random.Random(args.seed).sample(pool, min(args.n, len(pool)))
    out = Path(args.reports)
    out.mkdir(parents=True, exist_ok=True)
    (out / "draft_audit.md").write_text(markdown(sample, len(pool)), encoding="utf-8")
    print(f"draft audit: {len(sample)} of {len(pool)} drafted entries written to {out / 'draft_audit.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
