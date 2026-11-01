"""Audit: contradictions, sourcing and hygiene. Pure function of the records and configuration; no network.

Blocking issues (the record is held back from publishing, the run exits 1):
  missing required field, unknown kind, unknown predicate, invalid asOf, record with no source,
  dangling reference, knowledge assertion without a quote or without a publication or source URL.
Everything else is a warning published on the audit page.
"""
from __future__ import annotations

import re
from collections import defaultdict
from urllib.parse import urlparse

from .common import levenshtein, parse_date, today, write_report

REQUIRED = ("id", "kind", "name", "tldr", "asOf")
ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.\-]*:[^\s]+$")


def is_regulator_url(url: str, domains: list[str]) -> bool:
    host = (urlparse(url or "").hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in domains)


def regulatory_rule(records: list[dict], cfg: dict, issue) -> None:
    """A record that claims a regulatory status must cite the regulator, not only the maker or the press.

    Triggers on (a) a claim word in the name, TL;DR or summary, or (b) a fact whose key starts with a
    configured regulatory prefix. (b) is checked per fact: each regulatory fact needs its own regulator source.
    """
    conf = cfg.get("regulatory")
    if not conf:
        return
    domains = [d.lower() for d in conf.get("regulator_domains") or []]
    terms = conf.get("claim_terms") or []
    pattern = re.compile(r"\b(" + "|".join(re.escape(t) for t in terms) + r")\b", re.I) if terms else None
    prefixes = tuple(conf.get("fact_prefixes") or [])
    for r in records:
        rid = r.get("id") or "(no id)"
        text = " ".join(filter(None, [r.get("name"), r.get("tldr"), r.get("summary")]))
        urls = [s.get("url") for s in r.get("sources") or []]
        urls += [f.get("source") for f in (r.get("facts") or {}).values() if isinstance(f, dict)]
        if pattern and pattern.search(text) and not any(is_regulator_url(u, domains) for u in urls):
            word = pattern.search(text).group(0)
            issue(rid, "sourcing", "regulatory-claim-without-regulator-source",
                  f"Text says '{word}' but no source is from a regulator ({', '.join(domains[:4])}, ...)", True)
        for key, fact in (r.get("facts") or {}).items():
            if prefixes and key.startswith(prefixes):
                src = fact.get("source") if isinstance(fact, dict) else None
                if not is_regulator_url(src, domains):
                    issue(rid, "sourcing", "regulatory-fact-without-regulator-source",
                          f"facts.{key} must be sourced from a regulator, not {src or 'nothing'}", True)


def run(records: list[dict], cfg: dict, reports_dir) -> dict:
    kinds, predicates = cfg["kinds"], cfg["predicates"]
    now = today()
    issues: list[dict] = []

    def issue(rec_id, family, code, message, blocking):
        issues.append({"record": rec_id, "family": family, "code": code, "message": message, "blocking": blocking})

    ids = {r.get("id") for r in records if r.get("id")}
    inbound: dict[str, int] = defaultdict(int)
    for r in records:
        for rel in r.get("relations") or []:
            inbound[rel.get("object")] += 1

    seen: set = set()
    for r in records:
        rid = r.get("id") or "(no id)"
        # --- required fields and shape
        for f in REQUIRED:
            if not r.get(f):
                issue(rid, "sourcing" if f == "asOf" else "hygiene", "missing-field", f"Missing required field '{f}'", True)
        if r.get("id") and not ID.match(r["id"]):
            issue(rid, "hygiene", "bad-id", "id must look like prefix:local-name", True)
        if rid in seen:
            issue(rid, "hygiene", "duplicate-id", "The same id is used by more than one record", True)
        seen.add(rid)
        if r.get("kind") and r["kind"] not in kinds:
            issue(rid, "hygiene", "unknown-kind", f"Kind '{r['kind']}' is not declared in the configuration", True)
        as_of = parse_date(r.get("asOf"))
        if r.get("asOf") and not as_of:
            issue(rid, "hygiene", "bad-date", f"asOf '{r['asOf']}' is not YYYY-MM-DD", True)
        # --- contradictions
        if as_of and as_of > now:
            issue(rid, "contradiction", "future-asof", f"asOf {r['asOf']} is in the future", False)
        dated = [(k, parse_date(v.get("value") if isinstance(v, dict) else v))
                 for k, v in (r.get("facts") or {}).items() if k.endswith("_date")]
        for key, d in dated:
            if d and as_of and d > as_of and d <= now:
                issue(rid, "contradiction", "asof-before-event",
                      f"{key} ({d}) has passed since the record was last checked ({r['asOf']})", False)
        # --- sourcing
        if not r.get("sources"):
            issue(rid, "sourcing", "no-source", "Record has no source", True)
        for key, fact in (r.get("facts") or {}).items():
            value = fact.get("value") if isinstance(fact, dict) else fact
            if isinstance(value, (int, float)) and not (isinstance(fact, dict) and fact.get("source")):
                issue(rid, "sourcing", "unsourced-number", f"Number in facts.{key} has no source", False)
        # --- relations
        for i, rel in enumerate(r.get("relations") or []):
            where = f"relation[{i}] {rel.get('predicate')} -> {rel.get('object')}"
            if rel.get("predicate") not in predicates:
                issue(rid, "hygiene", "unknown-predicate", f"{where}: predicate not declared in the configuration", True)
            if rel.get("object") not in ids:
                issue(rid, "hygiene", "dangling-reference", f"{where}: object does not exist", True)
            if rel.get("knowledgeLevel", cfg["project"].get("default_knowledge_level")) == "knowledge_assertion":
                if not rel.get("quote"):
                    issue(rid, "sourcing", "assertion-without-quote", f"{where}: knowledge assertion has no quote", True)
                if not (rel.get("publications") or rel.get("sourceUrl")):
                    issue(rid, "sourcing", "assertion-without-source",
                          f"{where}: knowledge assertion has no publication or source URL", True)
            if rel.get("quote") and len(rel["quote"].split()) > 25:
                issue(rid, "sourcing", "long-quote", f"{where}: quote is longer than 25 words", False)
        # --- hygiene: orphans
        if not (r.get("relations") or inbound.get(r.get("id"))):
            issue(rid, "hygiene", "orphan", "Nothing links to or from this record", False)

    # --- hygiene: duplicate and near-duplicate names
    by_name: dict[str, list] = defaultdict(list)
    for r in records:
        if r.get("name"):
            by_name[r["name"].strip().lower()].append(r)
    for name, group in by_name.items():
        if len(group) > 1:
            kinds_used = {g.get("kind") for g in group}
            code = "name-collision-across-kinds" if len(kinds_used) > 1 else "duplicate-name"
            for g in group:
                issue(g.get("id"), "hygiene", code, f"Name '{g['name']}' is used by {len(group)} records", False)
    names = sorted((n, g[0]) for n, g in by_name.items() if len(n) >= 6)
    for i, (a, ra) in enumerate(names):
        for b, rb in names[i + 1:i + 40]:
            if ra.get("kind") == rb.get("kind") and levenshtein(a, b, 2) <= 2:
                issue(ra.get("id"), "hygiene", "near-duplicate-name",
                      f"'{ra['name']}' is within two edits of '{rb['name']}' ({rb.get('id')})", False)

    regulatory_rule(records, cfg, issue)

    held = sorted({i["record"] for i in issues if i["blocking"]})
    counts: dict = defaultdict(int)
    for i in issues:
        counts[f"{i['family']}:{'blocking' if i['blocking'] else 'warning'}"] += 1
    report = {"check": "audit", "records": len(records), "counts": dict(counts), "held_records": held, "issues": issues}
    write_report(reports_dir, "audit", report)
    return report
