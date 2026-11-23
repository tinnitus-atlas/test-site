"""One-off backfill: propose older material for review, in a window that never overlaps the nightly feeds.

Window: from `--until-days` back (default 30, where the nightly feeds stop) to `--since-days` back (default 183,
about six months). The same command serves the later 12 and 24-month stages by changing the two numbers.

What it proposes:
  trials   on-topic studies (the nightly relevance filter) last updated inside the window
  papers   only the top `--paper-cap` papers (default 30) first published inside the window, ranked by
           evidence level: guidelines and consensus statements, then systematic reviews and meta-analyses,
           then randomized trials, then other reviews, then other studies in people, then animal studies.
           Papers beyond the cap go to backfill_queue.json and are not proposed.
  devices  every FDA decision under the configured product codes, with no date limit (there are few)

Nothing already in the records, on the seen list (records/seen_proposals.json) or in an open proposals pull
request is proposed. Output in the reports folder: feeds.json, proposals.json and proposals.md (the same
format as the nightly, so the existing approval and apply steps work unchanged), backfill_queue.json and
backfill_pilot.md (counts for the person judging the pilot).

Usage:
  python3 -m kgkit.backfill --config kit.yaml --records records/x.json --reports reports [--since-days 183]
         [--until-days 30] [--paper-cap 30] [--open-prs] [--offline-standin]
Exit codes: 0 done (even with zero proposals); 2 bad input.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

from . import feeds, proposals
from .common import FetchError, Http, KitError, load_config, load_records, qs, today, write_report
from .doi_check import EPMC, norm_id

Runner = Callable[[list[str]], str]

GUIDELINE = ("guideline", "consensus", "practice parameter", "position statement", "recommendation")
SYSTEMATIC = ("systematic review", "meta-analysis", "meta analysis", "cochrane")
RANDOMIZED = ("randomized", "randomised", "rct")
ANIMAL = (" rat ", " rats", " mice", " mouse", " murine", "animal model", "guinea pig", " rodent", " in vitro")


def window(since_days: int, until_days: int) -> tuple[str, str]:
    if since_days <= until_days:
        raise KitError("--since-days must be larger than --until-days")
    end = today() - dt.timedelta(days=until_days)
    start = today() - dt.timedelta(days=since_days)
    return start.isoformat(), end.isoformat()


def evidence_rank(paper: dict) -> int:
    """0 is strongest. Uses the publication type Europe PMC reports plus the title."""
    text = f" {(paper.get('pub_type') or '')} {(paper.get('title') or '')} ".lower()
    if any(w in text for w in GUIDELINE):
        return 0
    if any(w in text for w in SYSTEMATIC):
        return 1
    if any(w in text for w in RANDOMIZED):
        return 2
    if any(w in text for w in ANIMAL):
        return 5
    if "review" in text:
        return 3
    return 4


RANK_LABEL = {0: "guideline or consensus", 1: "systematic review or meta-analysis", 2: "randomized trial",
              3: "other review", 4: "other study", 5: "animal or laboratory study"}


def trials(records: list[dict], conf: dict, http: Http, start: str, end: str, max_pages: int = 5) -> dict:
    have = feeds.known_ncts(records)
    terms = conf.get("relevance_terms") or [conf["condition"]]
    params = {"query.cond": conf["condition"], "filter.advanced": f"AREA[LastUpdatePostDate]RANGE[{start},{end}]",
              "sort": "LastUpdatePostDate:desc", "pageSize": 100,
              "fields": "NCTId,BriefTitle,OfficialTitle,Condition,OverallStatus,Phase,LastUpdatePostDate,LeadSponsorName"}
    out, off_topic, token = [], [], None
    for _ in range(max_pages):
        page = dict(params, **({"pageToken": token} if token else {}))
        try:
            data = http.get_json(f"{feeds.CTGOV}?{qs(page)}") or {}
        except FetchError as exc:
            return {"status": "unreachable", "error": str(exc), "candidates": out, "off_topic_skipped": off_topic}
        for s in data.get("studies") or []:
            p = s.get("protocolSection") or {}
            ident, st, des = p.get("identificationModule") or {}, p.get("statusModule") or {}, p.get("designModule") or {}
            nct = str(ident.get("nctId") or "").upper()
            updated = (st.get("lastUpdatePostDateStruct") or {}).get("date") or ""
            if not nct or nct in have or not (start <= updated <= end):
                continue
            if not feeds.is_on_topic(p, terms):
                off_topic.append(nct)
                continue
            out.append({"nct": nct, "title": ident.get("briefTitle"), "status": (st.get("overallStatus") or "").lower(),
                        "phase": "/".join(x.lower() for x in des.get("phases") or []) or None,
                        "sponsor": ((p.get("sponsorCollaboratorsModule") or {}).get("leadSponsor") or {}).get("name"),
                        "last_update": updated, "url": f"https://clinicaltrials.gov/study/{nct}"})
        token = data.get("nextPageToken")
        if not token:
            break
    return {"status": "ok", "since": start, "until": end, "candidates": out, "off_topic_skipped": off_topic}


def papers(records: list[dict], conf: dict, http: Http, start: str, end: str, cap: int, max_pages: int = 5) -> dict:
    have = feeds.known_papers(records)
    query = f"({conf['query']}) AND FIRST_PDATE:[{start} TO {end}]"
    found, cursor = [], "*"
    for _ in range(max_pages):
        params = {"query": query, "format": "json", "resultType": "lite", "pageSize": 100, "cursorMark": cursor,
                  "sort": "P_PDATE_D desc"}
        try:
            data = http.get_json(f"{EPMC}?{qs(params)}") or {}
        except FetchError as exc:
            return {"status": "unreachable", "error": str(exc), "candidates": [], "queued": []}
        rows = (data.get("resultList") or {}).get("result") or []
        for r in rows:
            ids = {norm_id(f"doi:{r['doi']}") if r.get("doi") else None, norm_id(f"pmid:{r['pmid']}") if r.get("pmid") else None}
            ids.discard(None)
            if not ids or ids & have:
                continue
            found.append({"title": (r.get("title") or "").rstrip("."), "doi": r.get("doi"), "pmid": r.get("pmid"),
                          "journal": r.get("journalTitle"), "published": r.get("firstPublicationDate"),
                          "pub_type": r.get("pubType"),
                          "url": f"https://doi.org/{r['doi']}" if r.get("doi") else f"https://europepmc.org/article/MED/{r.get('pmid')}"})
        nxt = data.get("nextCursorMark")
        if not rows or not nxt or nxt == cursor:
            break
        cursor = nxt
    for p in found:
        p["evidence_rank"] = evidence_rank(p)
        p["evidence_level"] = RANK_LABEL[p["evidence_rank"]]
    found.sort(key=lambda p: (p["evidence_rank"], p.get("published") or ""), reverse=False)
    return {"status": "ok", "since": start, "until": end, "candidates": found[:cap], "queued": found[cap:]}


def open_proposal_keys(runner: Runner) -> set[str]:
    """Keys of feed proposals already listed in an open proposals pull request."""
    keys: set[str] = set()
    prs = json.loads(runner(["gh", "pr", "list", "--state", "open", "--search", "Nightly proposals in:title",
                             "--json", "number,headRefName"]) or "[]")
    for pr in prs:
        head = pr.get("headRefName")
        if not head:
            continue
        runner(["git", "fetch", "-q", "origin", head])
        try:
            data = json.loads(runner(["git", "show", f"FETCH_HEAD:reports/proposals.json"]) or "{}")
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        for p in data.get("proposals") or []:
            k = proposals.proposal_key(p) if p.get("type") in proposals.SEEN_TYPES else None
            if k:
                keys.add(k)
    return keys


def run_cmd(args: list[str]) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def pilot_markdown(rep: dict) -> str:
    tr, pa, de = rep["feeds"]["trials"], rep["feeds"]["papers"], rep["feeds"]["devices"]
    lines = [f"# Backfill pilot {rep['since']} to {rep['until']}", "",
             f"Proposals in the pull request: {rep['count']} ({rep['by_type']['trials']} trials, "
             f"{rep['by_type']['papers']} papers, {rep['by_type']['devices']} devices)",
             f"Not proposed: {rep['excluded']['seen']} already reviewed, {rep['excluded']['open_pr']} already in an open "
             f"proposals pull request",
             f"Trials skipped as off-topic: {len(tr.get('off_topic_skipped') or [])}"]
    off = tr.get("off_topic_skipped") or []
    if off:
        lines.append("Off-topic registry numbers (spot-check about ten): " + ", ".join(off[:40]) + (" ..." if len(off) > 40 else ""))
    lines.append(f"Papers queued for later (beyond the cap): {len(pa.get('queued') or [])}")
    levels: dict[str, int] = {}
    for p in pa.get("candidates") or []:
        levels[p["evidence_level"]] = levels.get(p["evidence_level"], 0) + 1
    if levels:
        lines.append("Proposed papers by evidence level: " + ", ".join(f"{k} {v}" for k, v in levels.items()))
    unreachable = [n for n, f in (("trials", tr), ("papers", pa), ("devices", de)) if f.get("status") == "unreachable"]
    if unreachable:
        lines.append("Could not reach: " + ", ".join(unreachable))
    lines.append("Quote and citation checks: run by the next nightly on every record the pull request adds; "
                 "a record that fails is held back from the website.")
    lines.append(f"Run time: {rep['seconds']} seconds")
    return "\n".join(lines) + "\n"


def run(records: list[dict], cfg: dict, http: Http, reports_dir, since_days: int, until_days: int, paper_cap: int,
        seen: set[str], open_keys: set[str]) -> dict:
    t0 = time.time()
    start, end = window(since_days, until_days)
    conf = cfg.get("feeds") or {}
    feed_report = {"check": "feeds", "mode": "backfill", "since": start, "until": end,
                   "trials": trials(records, conf["trials"], http, start, end) if conf.get("trials") else {"candidates": []},
                   "papers": papers(records, conf["papers"], http, start, end, paper_cap) if conf.get("papers") else {"candidates": []},
                   "devices": feeds.devices(records, dict(conf["devices"], since_days=100000), http) if conf.get("devices") else {"candidates": []}}
    props = proposals.from_feeds(feed_report)
    excluded = {"seen": 0, "open_pr": 0}
    kept = []
    for p in props:
        k = proposals.proposal_key(p)
        if k in seen:
            excluded["seen"] += 1
        elif k in open_keys:
            excluded["open_pr"] += 1
        else:
            kept.append(p)
    for p in kept:
        p["why"] = p["why"].replace("A new paper matching", "An older paper matching").replace(" was published", " was published in the backfill window")
        p["auto_apply"] = False
    by_type = {"trials": sum(1 for p in kept if p["origin"] == "clinicaltrials_gov_v2"),
               "papers": sum(1 for p in kept if p["type"] == "review_paper"),
               "devices": sum(1 for p in kept if p["origin"] == "openfda_device")}
    reports = Path(reports_dir)
    reports.mkdir(parents=True, exist_ok=True)
    write_report(reports, "feeds", feed_report)
    write_report(reports, "proposals", {"check": "proposals", "mode": "backfill", "count": len(kept), "auto_apply": 0,
                                        "already_reviewed_skipped": excluded["seen"], "proposals": kept})
    (reports / "proposals.md").write_text(proposals.to_markdown(kept), encoding="utf-8")
    write_report(reports, "backfill_queue", {"papers": feed_report["papers"].get("queued") or []})
    rep = {"since": start, "until": end, "count": len(kept), "by_type": by_type, "excluded": excluded,
           "feeds": feed_report, "seconds": round(time.time() - t0, 1)}
    (reports / "backfill_pilot.md").write_text(pilot_markdown(rep), encoding="utf-8")
    return rep


def main(argv: list[str] | None = None, runner: Runner = run_cmd, http: Http | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kgkit.backfill", description="One-off backfill of older trials, papers and devices")
    ap.add_argument("--config", required=True)
    ap.add_argument("--records", required=True)
    ap.add_argument("--reports", default="reports")
    ap.add_argument("--since-days", type=int, default=183)
    ap.add_argument("--until-days", type=int, default=30)
    ap.add_argument("--paper-cap", type=int, default=30)
    ap.add_argument("--open-prs", action="store_true", help="exclude items in open proposals pull requests (needs gh and git)")
    ap.add_argument("--cache", default=".cache/http")
    args = ap.parse_args(argv)
    try:
        cfg = load_config(args.config)
        records = load_records(args.records)
        window(args.since_days, args.until_days)
    except KitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.paper_cap < 0:
        print("error: --paper-cap must be 0 or more", file=sys.stderr)
        return 2
    seen_file = Path(args.records).parent / "seen_proposals.json"
    seen = {e["key"] for e in json.loads(seen_file.read_text())} if seen_file.exists() else set()
    open_keys: set[str] = set()
    if args.open_prs:
        try:
            open_keys = open_proposal_keys(runner)
        except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as exc:
            print(f"error: could not read open proposals pull requests: {exc}", file=sys.stderr)
            return 2
    rep = run(records, cfg, http or Http(cache_dir=args.cache), args.reports, args.since_days, args.until_days,
              args.paper_cap, seen, open_keys)
    print((Path(args.reports) / "backfill_pilot.md").read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
