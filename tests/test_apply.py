"""Tests for kgkit.apply: approved proposals reach the records, nothing else does."""
import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kgkit import apply as ap  # noqa: E402
from kgkit.proposals import to_markdown  # noqa: E402

CFG = yaml.safe_load((ROOT / "kit.tinnitus.yaml").read_text())


def proposals():
    return [
        {"type": "update", "claim": "TENT-A: status should be 'completed' (currently 'None')",
         "source": "https://clinicaltrials.gov/study/NCT02669069", "confidence": "medium", "origin": "x",
         "apply": {"record": "tin:trial-tent-a", "field": "status", "from": None, "to": "completed"},
         "why": "w", "evidence": "e", "wrong_if": "x"},
        {"type": "update", "claim": "TENT-A: facts.enrollment should be '326' (currently 'None')",
         "source": "https://clinicaltrials.gov/study/NCT02669069", "confidence": "medium", "origin": "x",
         "apply": {"record": "tin:trial-tent-a", "field": "facts.enrollment", "from": None, "to": 326},
         "why": "w", "evidence": "e", "wrong_if": "x"},
        {"type": "new_record", "claim": "Add trial NCT09999999: Example new study", "source": "https://clinicaltrials.gov/study/NCT09999999",
         "confidence": "medium", "origin": "x", "why": "w", "evidence": "e", "wrong_if": "x",
         "apply": {"new_record": {"kind": "trial", "name": "Example new study", "xrefs": ["CLINICALTRIALS:NCT09999999"], "status": "recruiting"}}},
        {"type": "review_paper", "claim": "Review new paper for relevant claims: A new tinnitus paper", "source": "https://doi.org/10.9/new",
         "confidence": "low", "origin": "x", "why": "w", "evidence": "e", "wrong_if": "x", "apply": {"cite": "doi:10.9/new"}},
    ]


def ticked(props, numbers):
    md = to_markdown(props)
    lines, current = md.splitlines(), None
    for i, line in enumerate(lines):
        if line.startswith("## "):
            current = int(line[3:].split(".")[0])
        if line.strip() == "- [ ] Approved" and current in numbers:
            lines[i] = "- [x] Approved"
    return "\n".join(lines)


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "records").mkdir()
    shutil.copy(ROOT / "records" / "tinnitus.records.json", tmp_path / "records" / "r.json")
    (tmp_path / "p.json").write_text(json.dumps({"proposals": proposals()}))
    return tmp_path


def run_manual(ws, numbers, label="pr-1", props=None):
    if props is not None:
        (ws / "p.json").write_text(json.dumps({"proposals": props}))
    body = ws / "body.md"
    body.write_text(ticked(props or proposals(), numbers))
    return ap.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(ws / "records" / "r.json"),
                    "--body", str(body), "--proposals", str(ws / "p.json"), "--label", label])


def load(ws):
    return {r["id"]: r for r in json.loads((ws / "records" / "r.json").read_text())["records"]}


def test_only_ticked_proposals_are_applied(workspace):
    assert run_manual(workspace, {1}) == 0
    recs = load(workspace)
    assert recs["tin:trial-tent-a"]["status"] == "completed"
    assert "enrollment" not in (recs["tin:trial-tent-a"].get("facts") or {})


def test_fact_update_carries_source_and_bumps_asof(workspace):
    run_manual(workspace, {2})
    t = load(workspace)["tin:trial-tent-a"]
    assert t["facts"]["enrollment"] == {"value": 326, "source": "https://clinicaltrials.gov/study/NCT02669069"}
    assert t["asOf"] == ap.dt.date.today().isoformat()


def test_new_record_is_linked_to_condition(workspace):
    run_manual(workspace, {3})
    new = load(workspace)["tin:trial-nct09999999"]
    assert new["relations"][0]["object"] == "tin:tinnitus" and new["status"] == "recruiting"


def test_review_paper_goes_to_queue_not_records(workspace):
    before = set(load(workspace))
    run_manual(workspace, {4})
    assert set(load(workspace)) == before
    queue = json.loads((workspace / "records" / "review_queue.json").read_text())
    assert queue[0]["cite"] == "doi:10.9/new"


def test_conflict_when_record_changed_since_proposal(workspace):
    props = proposals()
    props[0]["apply"]["from"] = "recruiting"  # record actually has no status
    run_manual(workspace, {1}, props=props)
    assert "status" not in load(workspace)["tin:trial-tent-a"]


def test_edited_heading_is_skipped(workspace):
    body = ticked(proposals(), {1}).replace("TENT-A: status", "SOMETHING ELSE: status")
    (workspace / "body.md").write_text(body)
    ap.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(workspace / "records" / "r.json"),
             "--body", str(workspace / "body.md"), "--proposals", str(workspace / "p.json"), "--label", "x"])
    assert "status" not in load(workspace)["tin:trial-tent-a"]


def test_same_pull_request_is_applied_once(workspace):
    run_manual(workspace, {3}, label="pr-7")
    assert run_manual(workspace, {3}, label="pr-7") == 0
    assert sum(1 for r in load(workspace) if r == "tin:trial-nct09999999") == 1
    assert json.loads((workspace / "records" / "applied_prs.json").read_text()) == ["pr-7"]


def test_duplicate_new_trial_is_skipped(workspace):
    props = proposals()
    props[2]["apply"]["new_record"]["xrefs"] = ["CLINICALTRIALS:NCT02669069"]
    run_manual(workspace, {3}, props=props)
    assert "tin:trial-nct02669069" not in load(workspace)


def test_change_that_breaks_audit_is_not_written(workspace):
    props = proposals()
    props[0]["apply"] = {"record": "tin:trial-tent-a", "field": "kind", "from": "trial", "to": "planet"}
    before = (workspace / "records" / "r.json").read_text()
    assert run_manual(workspace, {1}, props=props) == 1
    assert (workspace / "records" / "r.json").read_text() == before


def test_nothing_ticked_changes_nothing_but_marks_applied(workspace):
    before = load(workspace)
    assert run_manual(workspace, set()) == 0
    assert load(workspace) == before


def test_from_github_with_standin(workspace):
    body = ticked(proposals(), {1, 4})
    calls = []

    def runner(args):
        calls.append(args)
        if args[:3] == ["gh", "pr", "list"]:
            return json.dumps([{"number": 12, "title": "Nightly proposals", "body": body, "mergeCommit": {"oid": "abc"}},
                               {"number": 11, "title": "Nightly proposals", "body": "", "mergeCommit": {"oid": "def"}}])
        if args[:2] == ["git", "show"]:
            return json.dumps({"proposals": proposals()})
        raise AssertionError(args)

    (workspace / "records" / "applied_prs.json").write_text("[11]")
    code = ap.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(workspace / "records" / "r.json"),
                    "--from-github"], runner=runner)
    assert code == 0 and load(workspace)["tin:trial-tent-a"]["status"] == "completed"
    assert json.loads((workspace / "records" / "applied_prs.json").read_text()) == [11, 12]
    assert ["git", "show", "abc:reports/proposals.json"] in calls


def test_github_unavailable_exit_2(workspace):
    def runner(args):
        raise FileNotFoundError("gh")
    code = ap.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(workspace / "records" / "r.json"),
                    "--from-github"], runner=runner)
    assert code == 2


def test_manual_mode_needs_inputs(workspace):
    assert ap.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(workspace / "records" / "r.json")]) == 2
