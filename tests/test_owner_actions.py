"""Your actions: the weekly list of what waits on the owner, at the top of the digest."""
import datetime as dt
from pathlib import Path

import yaml

from kgkit import owner_actions as oa

ROOT = Path(__file__).resolve().parents[1]
NOW = dt.datetime(2026, 11, 30, 2, 30, tzinfo=dt.timezone.utc)


def p(n, title, user="varioso"):
    return {"number": n, "title": title, "user": {"login": user}, "html_url": f"https://example.org/pull/{n}"}


def test_pull_requests_waiting_on_the_owner_are_listed_with_links():
    prs = [p(30, "Nightly proposals 2026-11-30 (12)", "varioso-bot"), p(31, "Fix"), p(32, "Bot chore", "varioso-bot"),
           p(33, "Workflow change")]
    lines = oa.pr_lines(prs, {30: None, 31: None, 32: None, 33: "workflows"}, "varioso-bot")
    assert lines[0] == "Review waiting: Nightly proposals 2026-11-30 (12) https://example.org/pull/30"
    assert any(x.startswith("#31 Fix: waiting for your merge or Ship it tick") for x in lines)
    assert not any("#32" in x for x in lines)
    assert any("#33" in x and "merge it yourself" in x for x in lines)


def test_studio_report_missing_stale_or_not_ready():
    assert "no readiness report" in oa.studio_lines(None, NOW)[0]
    ok = {"checked_at": "2026-11-29T09:15:00Z", "server": "yes", "model_loaded": "yes", "key_ok": "n/a"}
    assert oa.studio_lines(ok, NOW) == []
    assert "last report" in oa.studio_lines(dict(ok, checked_at="2026-11-20T09:15:00Z"), NOW)[0]
    assert "model server" in oa.studio_lines(dict(ok, server="no"), NOW)[0]


def test_only_workflows_whose_latest_run_failed_are_listed():
    runs = [{"name": "Nightly", "status": "completed", "conclusion": "success", "event": "schedule", "html_url": "u1"},
            {"name": "Nightly", "status": "completed", "conclusion": "failure", "event": "schedule", "html_url": "u0"},
            {"name": "Backfill", "status": "completed", "conclusion": "failure", "event": "workflow_dispatch",
             "html_url": "u2"},
            {"name": "Tests", "status": "completed", "conclusion": "failure", "event": "pull_request", "html_url": "u3"}]
    assert oa.failing_lines(runs) == ["Workflow failing: Backfill u2"]


def test_section_goes_right_under_the_first_line():
    out = oa.insert("Nightly run 2026-11-30\nStatus: OK\n", ["a"])
    assert out.splitlines()[:5] == ["Nightly run 2026-11-30", "", "## Your actions", "", "- a"]
    assert "Nothing is waiting on you." in oa.insert("x\n", [])


def test_nightly_adds_it_on_mondays_and_manual_runs_before_the_digest():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "nightly.yml").read_text())
    names = [s.get("name") for s in wf["jobs"]["nightly"]["steps"]]
    assert names.index("Your actions (weekly, at the top of the digest)") < names.index("Post digest")
    assert wf["permissions"]["actions"] == "read"
