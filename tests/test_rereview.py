"""Tests for the Re-review button (kgkit/rereview.py, run_rereview.sh, .github/workflows/rereview.yml) and the
weekly review pull request in run_nightly.sh."""
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kgkit import proposals, rereview  # noqa: E402

CFG = yaml.safe_load((ROOT / "kit.tinnitus.yaml").read_text())
REAL = json.loads((ROOT / "records" / "tinnitus.records.json").read_text())["records"]


def feed(*ncts):
    return proposals.from_feeds({"trials": {"candidates": [{"nct": n, "title": f"Tinnitus study {n}", "url": f"https://clinicaltrials.gov/study/{n}"} for n in ncts]}})


def runner_for(props, title="Nightly proposals 2026-11-06 (38)"):
    calls = []

    def runner(args):
        calls.append(args)
        if args[:3] == ["gh", "pr", "list"]:
            return "[]"
        if args[:3] == ["gh", "pr", "view"]:
            return json.dumps({"number": 12, "title": title, "state": "MERGED", "mergeCommit": {"oid": "abc"}})
        if args[:2] == ["git", "fetch"]:
            return ""
        if args[:2] == ["git", "show"]:
            return json.dumps({"proposals": props})
        raise AssertionError(args)
    runner.calls = calls
    return runner


def test_items_are_screened_again_with_the_replaced_number(tmp_path):
    props = feed("NCT05000001", "NCT05000002")
    rep = rereview.build(REAL, CFG, 12, runner_for(props), tmp_path, False, [])
    out = json.loads((tmp_path / "proposals.json").read_text())
    assert rep["count"] == 2 and out["replaces"] == [12]
    assert all(p["screen"] and p["why"].startswith("Sent again from pull request #12") for p in out["proposals"])
    assert "# Recommended: tick" in (tmp_path / "proposals.md").read_text()


def test_items_already_in_the_graph_are_left_out(tmp_path):
    tent = next(r for r in REAL if r["id"] == "tin:trial-tent-a")
    nct = tent["xrefs"][0].split(":")[1]
    rep = rereview.build(REAL, CFG, 12, runner_for(feed(nct, "NCT05000003")), tmp_path, False, [])
    assert rep["count"] == 1 and rep["dropped"]["in_graph"] == 1


def test_only_skipped_keeps_skipped_and_undecided(tmp_path):
    props = feed("NCT05000001", "NCT05000002", "NCT05000004")
    history = [{"key": "new_record:trial:clinicaltrials:nct05000001", "decision": "skipped", "pull_request": 12},
               {"key": "new_record:trial:clinicaltrials:nct05000002", "decision": "maybe_later", "pull_request": 12}]
    rep = rereview.build(REAL, CFG, 12, runner_for(props), tmp_path, True, history)
    keys = [proposals.proposal_key(p) for p in json.loads((tmp_path / "proposals.json").read_text())["proposals"]]
    assert rep["dropped"]["not_skipped"] == 1 and set(keys) == {"new_record:trial:clinicaltrials:nct05000001",
                                                               "new_record:trial:clinicaltrials:nct05000004"}


def test_refuses_a_pull_request_that_is_not_a_proposals_list(tmp_path):
    code = rereview.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(ROOT / "records" / "tinnitus.records.json"),
                          "--reports", str(tmp_path), "--pr", "13"], runner=runner_for([], title="Resume plan"))
    assert code == 2


def test_script_rejects_a_missing_number():
    r = subprocess.run(["bash", str(ROOT / "run_rereview.sh"), "twelve"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 2 and "give the number" in r.stdout


def test_workflow_is_manual_and_inputs_reach_the_shell_only_through_env():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "rereview.yml").read_text())
    on = wf.get("on", wf.get(True))
    assert set(on) == {"workflow_dispatch"} and wf["concurrency"]["group"] == "nightly"
    assert "${{" not in wf["jobs"]["rereview"]["steps"][-1]["run"]


def test_nightly_opens_the_review_pull_request_weekly():
    script = (ROOT / "run_nightly.sh").read_text()
    assert 'REVIEW_WEEKDAY' in script and "the review pull request opens on" in script and "still open" in script
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "nightly.yml").read_text())
    env = next(s for s in wf["jobs"]["nightly"]["steps"] if s.get("id") == "nightly")["env"]
    assert env["REVIEW_WEEKDAY"] == "monday" and "workflow_dispatch" in env["FORCE_PROPOSALS"]


def test_items_in_an_open_proposals_pull_request_are_left_out(tmp_path):
    props = feed("NCT05000001", "NCT05000002")
    rep = rereview.build(REAL, CFG, 12, runner_for(props), tmp_path, False, [],
                         {"new_record:trial:clinicaltrials:nct05000001"})
    assert rep["count"] == 1 and rep["dropped"]["in_open_pull_request"] == 1
