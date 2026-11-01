"""Freshness: is any record older than the limit set for its kind (and optionally its status)?

Rules come from the configuration's `freshness` list; the first matching rule applies, so status-specific
rules go before general ones. The run fails when stale critical records exceed `critical_stale_limit`
(a share of all critical records, default 0.05).
"""
from __future__ import annotations

from .common import parse_date, today, write_report


def rule_for(record: dict, rules: list[dict]) -> dict | None:
    for rule in rules:
        if record.get("kind") not in rule.get("kinds", []):
            continue
        if rule.get("status") and record.get("status") not in rule["status"]:
            continue
        return rule
    return None


def run(records: list[dict], cfg: dict, reports_dir) -> dict:
    now = today()
    rules = cfg.get("freshness") or []
    limit = float(cfg.get("critical_stale_limit", 0.05))
    stale, unruled, critical_total = [], [], 0
    for r in records:
        rule = rule_for(r, rules)
        if not rule:
            unruled.append(r.get("id"))
            continue
        critical = bool(rule.get("critical"))
        critical_total += critical
        as_of = parse_date(r.get("asOf"))
        age = (now - as_of).days if as_of else None
        if age is None or age > rule["days"]:
            stale.append({"record": r.get("id"), "name": r.get("name"), "kind": r.get("kind"), "asOf": r.get("asOf"),
                          "age_days": age, "limit_days": rule["days"], "critical": critical,
                          "over_by_days": None if age is None else age - rule["days"]})
    critical_stale = sum(1 for s in stale if s["critical"])
    share = critical_stale / critical_total if critical_total else 0.0
    breach = share > limit
    report = {"check": "freshness", "records": len(records), "critical_records": critical_total,
              "critical_stale": critical_stale, "critical_stale_share": round(share, 4), "limit": limit,
              "breach": breach, "stale": sorted(stale, key=lambda s: -(s["over_by_days"] or 10**6)),
              "records_without_rule": unruled}
    write_report(reports_dir, "freshness", report)
    return report
