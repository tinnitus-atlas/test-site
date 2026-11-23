"""Tests for kgkit.backfill (WP-B1): older material in a window that never overlaps the nightly feeds, top papers by
evidence level, no item already reviewed or already in an open proposals pull request, output the apply step reads."""
import datetime as dt
import json
import subprocess
import sys
import urllib.parse
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kgkit import apply as ap  # noqa: E402
from kgkit import backfill, proposals  # noqa: E402
from kgkit.common import FetchError, Http  # noqa: E402

CFG = yaml.safe_load((ROOT / "kit.tinnitus.yaml").read_text())
REAL = json.loads((ROOT / "records" / "tinnitus.records.json").read_text())["records"]


def days_ago(n):
    return (dt.date.today() - dt.timedelta(days=n)).isoformat()


def study(nct, title, conditions, updated):
    return {"protocolSection": {
        "identificationModule": {"nctId": nct, "briefTitle": title},
        "conditionsModule": {"conditions": conditions},
        "statusModule": {"overallStatus": "COMPLETED", "lastUpdatePostDateStruct": {"date": updated}}}}


def paper(n, title, pub_type="research-article; journal article", age=60):
    return {"title": title, "doi": f"10.9/bf{n}", "pmid": str(900000 + n), "journalTitle": "J", "pubType": pub_type,
            "firstPublicationDate": days_ago(age)}


class Standin:
    """Answers registry, literature and FDA requests from canned pages; records every URL asked for."""

    def __init__(self, trial_pages=None, paper_pages=None, devices=None, fail=()):
        self.trial_pages = trial_pages or [{"studies": []}]
        self.paper_pages = paper_pages or [{"resultList": {"result": []}}]
        self.devices = devices or []
        self.fail = set(fail)
        self.urls = []

    def __call__(self, url):
        self.urls.append(urllib.parse.unquote_plus(url))
        u = self.urls[-1]
        if "clinicaltrials.gov" in u:
            if "trials" in self.fail:
                raise FetchError("down")
            i = 1 if "pageToken=p2" in u else 0
            return self.trial_pages[i]
        if "europepmc" in u:
            if "papers" in self.fail:
                raise FetchError("down")
            i = 1 if "cursorMark=c2" in u else 0
            return self.paper_pages[i]
        if "classification.json" in u:
            return {"results": []}
        if "510k.json" in u:
            return {"results": self.devices}
        raise FetchError(f"no route {u}")


def run(tmp_path, standin, seen=(), open_keys=(), cap=30, since=183, until=30):
    return backfill.run(REAL, CFG, Http(fetcher=standin), tmp_path, since, until, cap, set(seen), set(open_keys))


def test_window_starts_where_the_nightly_stops_and_asks_registry_for_that_range(tmp_path):
    s = Standin()
    rep = run(tmp_path, s)
    assert (rep["since"], rep["until"]) == (days_ago(183), days_ago(30))
    ct = [u for u in s.urls if "clinicaltrials.gov" in u][0]
    assert f"AREA[LastUpdatePostDate]RANGE[{days_ago(183)},{days_ago(30)}]" in ct
    ep = [u for u in s.urls if "europepmc" in u][0]
    assert f"FIRST_PDATE:[{days_ago(183)} TO {days_ago(30)}]" in ep


def test_window_must_be_ordered():
    with pytest.raises(Exception):
        backfill.window(30, 183)


def test_trials_inside_window_on_topic_only_and_pages_followed(tmp_path):
    s = Standin(trial_pages=[
        {"studies": [study("NCT05000001", "Sound therapy for tinnitus", ["Tinnitus"], days_ago(90)),
                     study("NCT05000002", "Insomnia in chronic pain", ["Insomnia"], days_ago(90)),
                     study("NCT05000003", "Recent tinnitus trial", ["Tinnitus"], days_ago(5))],
         "nextPageToken": "p2"},
        {"studies": [study("NCT05000004", "Tinnitus app trial", ["Tinnitus"], days_ago(150))]}])
    rep = run(tmp_path, s)
    tr = rep["feeds"]["trials"]
    assert [c["nct"] for c in tr["candidates"]] == ["NCT05000001", "NCT05000004"]
    assert tr["off_topic_skipped"] == ["NCT05000002"]  # the recent one is the nightly's, not counted at all


def test_papers_ranked_by_evidence_level_and_capped_rest_queued(tmp_path):
    rows = [paper(1, "Tinnitus in rats after noise"),
            paper(2, "A randomized controlled trial of sound therapy for tinnitus"),
            paper(3, "Clinical practice guideline: tinnitus"),
            paper(4, "Tinnitus: a systematic review and meta-analysis", pub_type="review"),
            paper(5, "A cohort study of tinnitus in adults")]
    s = Standin(paper_pages=[{"resultList": {"result": rows}}])
    rep = run(tmp_path, s, cap=3)
    pa = rep["feeds"]["papers"]
    assert [p["doi"] for p in pa["candidates"]] == ["10.9/bf3", "10.9/bf4", "10.9/bf2"]
    assert [p["doi"] for p in pa["queued"]] == ["10.9/bf5", "10.9/bf1"]
    queue = json.loads((tmp_path / "backfill_queue.json").read_text())
    assert [p["doi"] for p in queue["papers"]] == ["10.9/bf5", "10.9/bf1"]


def test_paper_pages_follow_the_cursor(tmp_path):
    s = Standin(paper_pages=[{"resultList": {"result": [paper(1, "Tinnitus study one")]}, "nextCursorMark": "c2"},
                             {"resultList": {"result": [paper(2, "Tinnitus study two")]}, "nextCursorMark": "c2"}])
    rep = run(tmp_path, s)
    assert len(rep["feeds"]["papers"]["candidates"]) == 2


def test_devices_have_no_date_limit(tmp_path):
    s = Standin(devices=[{"k_number": "K100001", "device_name": "Old masker", "applicant": "A", "decision_date": "2012-01-01",
                          "decision_description": "Substantially Equivalent", "product_code": "QVN"}])
    rep = run(tmp_path, s)
    assert [d["number"] for d in rep["feeds"]["devices"]["candidates"]] == ["K100001"]


def test_seen_and_open_pull_request_items_are_not_proposed(tmp_path):
    s = Standin(trial_pages=[{"studies": [study("NCT05000001", "Tinnitus A", ["Tinnitus"], days_ago(90)),
                                          study("NCT05000002", "Tinnitus B", ["Tinnitus"], days_ago(90)),
                                          study("NCT05000003", "Tinnitus C", ["Tinnitus"], days_ago(90))]}])
    rep = run(tmp_path, s, seen={"new_record:trial:clinicaltrials:nct05000001"},
              open_keys={"new_record:trial:clinicaltrials:nct05000002"})
    props = json.loads((tmp_path / "proposals.json").read_text())["proposals"]
    assert [proposals.proposal_key(p) for p in props] == ["new_record:trial:clinicaltrials:nct05000003"]
    assert rep["excluded"] == {"seen": 1, "open_pr": 1}


def test_output_is_the_nightly_format_and_the_apply_step_applies_a_ticked_item(tmp_path):
    s = Standin(trial_pages=[{"studies": [study("NCT05000001", "Sound therapy for tinnitus", ["Tinnitus"], days_ago(90))]}])
    run(tmp_path, s)
    md = (tmp_path / "proposals.md").read_text()
    assert md.startswith("# Proposed changes") and "- [ ] Approved" in md
    records = tmp_path / "records"
    records.mkdir()
    (records / "r.json").write_text((ROOT / "records" / "tinnitus.records.json").read_text())
    body = tmp_path / "body.md"
    body.write_text(md.replace("- [ ] Approved", "- [x] Approved", 1))
    assert ap.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(records / "r.json"), "--body", str(body),
                    "--proposals", str(tmp_path / "proposals.json"), "--label", "backfill-1"]) == 0
    recs = json.loads((records / "r.json").read_text())["records"]
    assert any("CLINICALTRIALS:NCT05000001" in (r.get("xrefs") or []) for r in recs)


def test_pilot_report_has_every_count(tmp_path):
    s = Standin(trial_pages=[{"studies": [study("NCT05000001", "Tinnitus A", ["Tinnitus"], days_ago(90)),
                                          study("NCT05000002", "Insomnia", ["Insomnia"], days_ago(90))]}],
                paper_pages=[{"resultList": {"result": [paper(1, "Guideline for tinnitus"), paper(2, "Tinnitus study")]}}])
    run(tmp_path, s, cap=1)
    md = (tmp_path / "backfill_pilot.md").read_text()
    for needle in ("Proposals in the pull request: 2 (1 trials, 1 papers, 0 devices)", "Trials skipped as off-topic: 1",
                   "NCT05000002", "Papers queued for later (beyond the cap): 1", "guideline or consensus 1",
                   "Not proposed: 0 already reviewed, 0 already in an open proposals pull request", "Run time:"):
        assert needle in md, needle


def test_unreachable_service_is_reported_not_fatal(tmp_path):
    rep = run(tmp_path, Standin(fail=("trials", "papers")))
    assert rep["count"] == 0
    assert "Could not reach: trials, papers" in (tmp_path / "backfill_pilot.md").read_text()


def test_open_proposal_keys_reads_the_open_pull_request_branches():
    calls = []

    def runner(args):
        calls.append(args)
        if args[:3] == ["gh", "pr", "list"]:
            return json.dumps([{"number": 20, "headRefName": "proposals/2026-12-01"}])
        if args[:2] == ["git", "fetch"]:
            return ""
        if args[:2] == ["git", "show"]:
            return json.dumps({"proposals": proposals.from_feeds(
                {"trials": {"candidates": [{"nct": "NCT05000009", "title": "T", "url": "u"}]}})})
        raise AssertionError(args)

    assert backfill.open_proposal_keys(runner) == {"new_record:trial:clinicaltrials:nct05000009"}
    assert ["git", "fetch", "-q", "origin", "proposals/2026-12-01"] in calls


def test_cli_rejects_bad_window(tmp_path):
    assert backfill.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(ROOT / "records" / "tinnitus.records.json"),
                          "--reports", str(tmp_path), "--since-days", "10", "--until-days", "30"]) == 2


def test_run_script_without_git_writes_reports_and_opens_nothing(tmp_path):
    # The shell wrapper end to end, with git disabled and the network replaced by a stand-in module.
    stub = tmp_path / "stub"
    stub.mkdir()
    (stub / "sitecustomize.py").write_text(
        "import kgkit.common as c\n"
        "c.Http.get_json = lambda self, url: {}\n")
    env = {"PATH": "/usr/bin:/bin", "NO_GIT": "1", "PYTHONPATH": f"{stub}:{ROOT}", "REPORTS": str(tmp_path / "reports")}
    r = subprocess.run(["bash", str(ROOT / "run_backfill.sh"), "183", "30", "30"], cwd=ROOT, env=env,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "# Backfill pilot" in r.stdout and "Pull request: none (git disabled for this run)" in r.stdout
    assert (tmp_path / "reports" / "proposals.json").exists()


def test_run_script_rejects_non_numbers():
    r = subprocess.run(["bash", str(ROOT / "run_backfill.sh"), "six", "30", "30"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 2 and "whole numbers" in r.stdout


def test_workflow_is_manual_only_and_title_matches_the_apply_step():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "backfill.yml").read_text())
    on = wf.get("on", wf.get(True))
    assert set(on) == {"workflow_dispatch"}
    assert wf["concurrency"]["group"] == "nightly"
    script = (ROOT / "run_backfill.sh").read_text()
    assert 'TITLE="Nightly proposals backfill' in script
    assert "reports/proposals.json" in (ROOT / "kgkit" / "apply.py").read_text()
