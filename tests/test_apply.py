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


def test_nothing_ticked_changes_nothing_and_stays_open(workspace):
    before = load(workspace)
    notes = workspace / "notes.txt"
    body = workspace / "body.md"
    body.write_text(ticked(proposals(), set()))
    code = ap.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(workspace / "records" / "r.json"),
                    "--body", str(body), "--proposals", str(workspace / "p.json"), "--label", "pr-1", "--notes", str(notes)])
    assert code == 0
    assert load(workspace) == before
    assert not (workspace / "records" / "applied_prs.json").exists()
    assert not (workspace / "records" / "seen_proposals.json").exists()
    assert "batch pr-1 was merged with no box ticked; its items stay open" in notes.read_text()


def test_unticked_merged_pull_request_is_skipped_and_reported(workspace):
    ticked_body = ticked(proposals(), {1})

    def runner(args):
        if args[:3] == ["gh", "pr", "list"]:
            return json.dumps([
                {"number": 12, "title": "Nightly proposals", "body": ticked(proposals(), set()), "mergeCommit": {"oid": "abc"}, "author": {"login": "varioso-bot"}},
                {"number": 13, "title": "Nightly proposals", "body": ticked_body, "mergeCommit": {"oid": "def"}, "author": {"login": "varioso-bot"}}])
        if args[:2] == ["git", "show"]:
            return json.dumps({"proposals": proposals()})
        raise AssertionError(args)

    notes = workspace / "notes.txt"
    code = ap.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(workspace / "records" / "r.json"),
                    "--from-github", "--notes", str(notes)], runner=runner)
    assert code == 0
    assert json.loads((workspace / "records" / "applied_prs.json").read_text()) == [13]
    assert notes.read_text() == "pull request #12 was merged with no box ticked; its items stay open\n"
    assert load(workspace)["tin:trial-tent-a"]["status"] == "completed"


def test_notes_file_is_empty_when_nothing_was_skipped(workspace):
    notes = workspace / "notes.txt"
    body = workspace / "body.md"
    body.write_text(ticked(proposals(), {1}))
    assert ap.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(workspace / "records" / "r.json"),
                    "--body", str(body), "--proposals", str(workspace / "p.json"), "--label", "pr-1", "--notes", str(notes)]) == 0
    assert notes.read_text() == ""


def test_from_github_with_standin(workspace):
    body = ticked(proposals(), {1, 4})
    calls = []

    def runner(args):
        calls.append(args)
        if args[:3] == ["gh", "pr", "list"]:
            return json.dumps([{"number": 12, "title": "Nightly proposals", "body": body, "mergeCommit": {"oid": "abc"}, "author": {"login": "varioso-bot"}},
                               {"number": 11, "title": "Nightly proposals", "body": "", "mergeCommit": {"oid": "def"}, "author": {"login": "varioso-bot"}}])
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


# --- the reviewed text is what gets applied (hardening of 24 Nov) ---------------------------------------------------
def _records():
    return json.loads((ROOT / "records" / "tinnitus.records.json").read_text())["records"]


def _apply(body, props):
    import copy
    work = copy.deepcopy(_records())
    return ap.apply_selected(work, props, ap.approved_numbers(body), CFG, [], "2026-11-24", body=body)


def test_genuine_ticked_item_is_applied():
    props = proposals()
    res = _apply(ticked(props, {1}), props)
    assert [a["number"] for a in res["applied"]] == [1]


def test_ticks_hidden_from_the_reviewer_never_count():
    props = proposals()
    body = to_markdown(props)
    hidden = [f"<!--\n## 1. {props[0]['claim']}\n- [x] Approved\n-->",
              f"```\n## 1. {props[0]['claim']}\n- [x] Approved\n```",
              f"<details><summary>x</summary>\n\n## 1. {props[0]['claim']}\n- [x] Approved\n</details>"]
    for h in hidden:
        assert ap.approved_numbers(h + "\n" + body) == {}, h


def test_an_item_shown_twice_is_ambiguous_and_never_applied():
    props = proposals()
    body = ticked(props, {1})
    dup = body + f"\n## 1. {props[0]['claim']}\n\n- [ ] Approved\n"
    assert 1 not in ap.approved_numbers(dup)


def test_data_that_differs_from_what_the_reviewer_saw_is_not_applied():
    props = proposals()
    body = ticked(props, {1})                       # the reviewer read "to: completed"
    swapped = [dict(p) for p in props]
    swapped[0] = dict(props[0], apply=dict(props[0]["apply"], to="terminated"))
    res = _apply(body, swapped)
    assert not res["applied"] and "differ" in res["skipped"][0]["reason"]


def test_maybe_later_and_reasons_hidden_from_the_reviewer_never_count():
    from kgkit import decisions
    body = "<!--\n## 2. x\n- [x] Maybe later\nReason: hidden\n-->\n## 1. y\n- [ ] Maybe later\n"
    assert decisions.maybe_numbers(body) == set() and decisions.reasons(body) == {}


def test_item_held_back_by_the_details_check_stays_open_for_the_next_review(workspace):
    props = proposals()
    body = workspace / "body.md"
    body.write_text(ticked(props, {1}))                     # the reviewer saw "to: completed"
    swapped = [dict(p) for p in props]
    swapped[0] = dict(props[0], apply=dict(props[0]["apply"], to="terminated"))
    (workspace / "p.json").write_text(json.dumps({"proposals": swapped}))
    assert ap.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(workspace / "records" / "r.json"),
                    "--body", str(body), "--proposals", str(workspace / "p.json"), "--label", "pr-9"]) == 0
    assert load(workspace)["tin:trial-tent-a"].get("status") != "terminated"
    rec_dir = workspace / "records"
    seen = json.loads((rec_dir / "seen_proposals.json").read_text()) if (rec_dir / "seen_proposals.json").exists() else []
    from kgkit.proposals import proposal_key
    assert proposal_key(swapped[0]) not in {e["key"] for e in seen}
    hist = (rec_dir / "decisions.jsonl").read_text() if (rec_dir / "decisions.jsonl").exists() else ""
    assert props[0]["claim"] not in hist


def test_an_unclosed_comment_or_fence_refuses_the_whole_text():
    from kgkit.common import visible
    props = proposals()
    body = ticked(props, {1, 2})
    assert ap.approved_numbers(body) and not ap.approved_numbers("<!-- oops\n" + body)
    assert not ap.approved_numbers("```\n" + body)
    odd = body.replace(props[0]["claim"], props[0]["claim"] + " <details")    # a stray tag inside a claim
    assert set(ap.approved_numbers(odd)) == {1, 2}
    assert visible("text with a `<details` mention") == "text with a `<details` mention"


def test_multi_line_details_still_match(workspace):
    props = proposals()
    props[0] = dict(props[0], why="first paragraph\n\nsecond paragraph")
    body = ticked(props, {1})
    assert ap.shown_matches(body, 1, props[0])
    assert ap.shown_matches(body.replace("\n", "\r\n"), 1, props[0])
