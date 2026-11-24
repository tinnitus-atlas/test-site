"""Tests for one merge per review (kgkit/review.py, review-sync workflow, nightly and drafting integration)."""
import json
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kgkit import apply as ap  # noqa: E402
from kgkit import proposals, review, screener  # noqa: E402

CFG = yaml.safe_load((ROOT / "kit.tinnitus.yaml").read_text())


def trial(n, title="Tinnitus sound therapy trial"):
    return proposals.from_feeds({"trials": {"candidates": [{"nct": n, "title": title, "url": f"https://clinicaltrials.gov/study/{n}"}]}})[0]


def setup(tmp_path, props):
    rec_dir = tmp_path / "records"
    rec_dir.mkdir()
    shutil.copy(ROOT / "records" / "tinnitus.records.json", rec_dir / "r.json")
    main_copy = tmp_path / "main_records"
    shutil.copytree(rec_dir, main_copy)
    (tmp_path / "p.json").write_text(json.dumps({"proposals": props}))

    def runner(args):
        assert args[:2] == ["git", "checkout"] and args[2] == "origin/main"
        shutil.rmtree(rec_dir)
        shutil.copytree(main_copy, rec_dir)
        return ""
    return rec_dir / "r.json", runner


def ids(rec):
    return {r["id"] for r in json.loads(rec.read_text())["records"]}


def test_sync_puts_ticked_items_on_the_branch_and_unticking_undoes_it(tmp_path):
    props = screener.screen([trial("NCT05000001"), trial("NCT05000002")], CFG)
    rec, runner = setup(tmp_path, props)
    body = tmp_path / "body.md"
    body.write_text(proposals.to_markdown(props).replace("- [x] Approved", "- [ ] Approved").replace("- [ ] Approved", "- [x] Approved", 1))
    assert review.sync(str(ROOT / "kit.tinnitus.yaml"), str(rec), 23, str(body), str(tmp_path / "p.json"), "origin/main", runner) == 0
    assert len([i for i in ids(rec) if i.startswith("tin:trial-nct0500000")]) == 1
    assert json.loads((rec.parent / "applied_prs.json").read_text()) == [23]
    body.write_text(proposals.to_markdown(props).replace("- [x] Approved", "- [ ] Approved"))
    review.sync(str(ROOT / "kit.tinnitus.yaml"), str(rec), 23, str(body), str(tmp_path / "p.json"), "origin/main", runner)
    assert not [i for i in ids(rec) if i.startswith("tin:trial-nct0500000")]
    assert not (rec.parent / "applied_prs.json").exists()  # nothing ticked: the nightly still sees it as open


def test_nightly_skips_a_synced_pull_request_after_the_merge(tmp_path):
    props = [trial("NCT05000001")]
    rec_dir = tmp_path / "records"
    rec_dir.mkdir()
    shutil.copy(ROOT / "records" / "tinnitus.records.json", rec_dir / "r.json")
    (rec_dir / "applied_prs.json").write_text("[23]")
    body = proposals.to_markdown(props).replace("- [ ] Approved", "- [x] Approved")

    def runner(args):
        if args[:3] == ["gh", "pr", "list"]:
            return json.dumps([{"number": 23, "title": "Nightly proposals 2026-11-30 (1)", "body": body,
                                "mergeCommit": {"oid": "abc"}, "author": {"login": "varioso-bot"}}])
        raise AssertionError(args)
    assert ap.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(rec_dir / "r.json"), "--from-github"], runner=runner) == 0


def test_append_keeps_existing_ticks_and_numbers_new_items_after_them(tmp_path):
    old = screener.screen([trial("NCT05000001")], CFG)
    body = proposals.to_markdown(old).replace("- [ ] Maybe later", "- [x] Maybe later") + "\nReason: keep this note\n"
    new = [trial("NCT05000002", "Another tinnitus trial")]
    text, merged = review.append(body, {"proposals": old, "count": 1}, new)
    assert text.startswith(body.rstrip()) and "- [x] Maybe later" in text and "Reason: keep this note" in text
    assert "## 2. Add trial NCT05000002" in text and merged["count"] == 2
    rec, runner = setup(tmp_path, merged["proposals"])
    f = tmp_path / "b.md"
    f.write_text(text.replace("- [ ] Approved", "- [x] Approved"))
    review.sync(str(ROOT / "kit.tinnitus.yaml"), str(rec), 30, str(f), str(tmp_path / "p.json"), "origin/main", runner)
    assert {"tin:trial-nct05000001", "tin:trial-nct05000002"} <= ids(rec)


def test_review_sync_runs_only_for_the_owner_on_bot_proposals_from_this_repository():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "review-sync.yml").read_text())
    on = wf.get("on", wf.get(True))
    assert on == {"pull_request": {"types": ["edited"]}}
    cond = wf["jobs"]["sync"]["if"]
    for needle in ("github.event.sender.login == (vars.REVIEW_OWNER", "startsWith(github.event.pull_request.title, 'Nightly proposals')",
                   "head.repo.full_name == github.repository", "pull_request.user.login == (vars.REVIEW_BOT"):
        assert needle in cond
    run = wf["jobs"]["sync"]["steps"][-1]["run"]
    assert "${{" not in run and "main" not in run.replace("origin/main", "")  # never pushes to main


def test_nightly_and_drafting_use_the_one_merge_path():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "nightly.yml").read_text())
    env = next(s for s in wf["jobs"]["nightly"]["steps"] if s.get("id") == "nightly")["env"]
    assert env["SYNC_ON_OPEN"] == "1"
    assert "kgkit.review sync" in (ROOT / "run_nightly.sh").read_text()
    assert "kgkit.review append" in (ROOT / "run_drafts.sh").read_text()
