"""Command line: python3 -m kgkit --config kit.yaml --records records.json --reports reports/ [--only ...] [--offline]

Run order: feeds, factcheck, doi, audit, freshness, proposals. Writes one JSON report per check, plus
held_records.json (records the site must not publish), summary.json and summary.md (a short digest).

Exit codes: 0 nothing blocking; 1 blocking findings (held records or a freshness breach); 2 bad input.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import audit, doi_check, factcheck, feeds, freshness, proposals
from .common import Http, KitError, load_config, load_records, write_report

ORDER = ["feeds", "factcheck", "doi", "audit", "freshness", "proposals"]
NETWORK = {"feeds", "factcheck", "doi"}


def summarise(results: dict) -> tuple[dict, str]:
    held = sorted(set((results.get("doi") or {}).get("held_records", [])) |
                  set((results.get("audit") or {}).get("held_records", [])))
    fr = results.get("freshness") or {}
    blocking = bool(held) or bool(fr.get("breach"))
    s = {
        "blocking": blocking,
        "held_records": held,
        "doi": (results.get("doi") or {}).get("counts"),
        "audit": (results.get("audit") or {}).get("counts"),
        "factcheck": (results.get("factcheck") or {}).get("counts"),
        "freshness": {k: fr.get(k) for k in ("critical_stale", "critical_records", "critical_stale_share", "breach")} if fr else None,
        "new_trials": len(((results.get("feeds") or {}).get("trials") or {}).get("candidates") or []),
        "new_papers": len(((results.get("feeds") or {}).get("papers") or {}).get("candidates") or []),
        "new_devices": len(((results.get("feeds") or {}).get("devices") or {}).get("candidates") or []),
        "proposals": (results.get("proposals") or {}).get("count"),
        "skipped_checks": [c for c in ORDER if c not in results],
    }
    doi = results.get("doi") or {}
    unreachable = []
    n = (doi.get("counts") or {}).get("unreachable", 0)
    if n:
        unreachable.append(f"Europe PMC ({n} citations not checked)")
    n = len((results.get("factcheck") or {}).get("unreachable") or [])
    if n:
        unreachable.append(f"ClinicalTrials.gov ({n} trials not checked)")
    for feed in ("trials", "papers", "devices"):
        if (((results.get("feeds") or {}).get(feed)) or {}).get("status") == "unreachable":
            unreachable.append(f"{feed} feed")
    s["unreachable"] = unreachable
    status = "BLOCKING ISSUES" if blocking else ("INCOMPLETE (services unreachable)" if unreachable else "all clear")
    lines = [f"Status: {status}"]
    if unreachable:
        lines.append("Could not reach: " + "; ".join(unreachable))
    if held:
        lines.append(f"Held back from publishing ({len(held)}): " + ", ".join(held[:10]) + (" ..." if len(held) > 10 else ""))
    if fr:
        lines.append(f"Freshness: {fr.get('critical_stale')} of {fr.get('critical_records')} critical records stale"
                     + (" (limit exceeded)" if fr.get("breach") else ""))
    if s["factcheck"]:
        fc = s["factcheck"]
        lines.append(f"Registry mismatches: {fc.get('high', 0)} high, {fc.get('medium', 0)} medium, {fc.get('low', 0)} low")
    lines.append(f"Feeds: {s['new_trials']} new trials, {s['new_papers']} new papers, {s['new_devices']} new FDA device decisions")
    lines.append(f"Proposals awaiting approval: {s['proposals'] or 0}")
    if s["skipped_checks"]:
        lines.append("Not run: " + ", ".join(s["skipped_checks"]))
    return s, "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kgkit", description="Knowledge Quality Kit checks")
    ap.add_argument("--config", required=True)
    ap.add_argument("--records", required=True)
    ap.add_argument("--reports", default="reports")
    ap.add_argument("--only", help="comma-separated subset of: " + ",".join(ORDER))
    ap.add_argument("--offline", action="store_true", help="skip checks that need the network")
    ap.add_argument("--cache", default=".cache/http", help="HTTP cache folder")
    args = ap.parse_args(argv)

    try:
        cfg = load_config(args.config)
        records = load_records(args.records)
    except KitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    wanted = [c for c in ORDER if not args.only or c in args.only.split(",")]
    if args.offline:
        wanted = [c for c in wanted if c not in NETWORK]
    http = Http(cache_dir=args.cache)
    reports = Path(args.reports)
    results: dict = {}
    for check in wanted:
        if check == "feeds":
            results[check] = feeds.run(records, cfg, http, reports)
        elif check == "factcheck":
            results[check] = factcheck.run(records, cfg, http, reports)
        elif check == "doi":
            results[check] = doi_check.run(records, http, reports)
        elif check == "audit":
            results[check] = audit.run(records, cfg, reports)
        elif check == "freshness":
            results[check] = freshness.run(records, cfg, reports)
        elif check == "proposals":
            results[check] = proposals.run(records, cfg, reports)
        print(f"ran {check}")

    summary, text = summarise(results)
    write_report(reports, "summary", summary)
    write_report(reports, "held_records", {"held_records": summary["held_records"]})
    (reports / "summary.md").write_text(text + "\n", encoding="utf-8")
    print(text)
    return 1 if summary["blocking"] else 0


if __name__ == "__main__":
    sys.exit(main())
