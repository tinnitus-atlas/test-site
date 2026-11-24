"""Ship it: the owner ticks one box; the pull request is kept up to date, tested and merged without further clicks,
and nothing the owner did not approve is ever merged."""
import base64
import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from kgkit import shipit

ROOT = Path(__file__).resolve().parents[1]
APP = "kg-ship-it[bot]"
BOT = "varioso-bot"
HEAD = "a" * 40
OLD = "b" * 40


def pr(body="- [x] **Ship it**: tick", state="clean", head=HEAD, user="varioso", title="Some change", fork=False):
    return {"number": 7, "title": title, "body": body, "draft": False, "mergeable_state": state,
            "user": {"login": user},
            "head": {"sha": head, "ref": "branch", "repo": {"full_name": "o/other" if fork else "o/r"}},
            "base": {"repo": {"full_name": "o/r"}}}


def go(p, **kw):
    args = dict(approved=HEAD, new_commits=[], tick_event=False, touches_workflows=False, tests="success",
                sync_running=False, app_login=APP, bot=BOT)
    args.update(kw)
    return shipit.decide(p, **args)


def app_merge():
    return {"author": {"login": APP}, "parents": [{}, {}], "commit": {"verification": {"verified": True}}}


def sync_commit(files=("records/tinnitus.records.json",), message=shipit.SYNC_MESSAGE):
    return {"author": None, "parents": [{}], "commit": {"message": message, "verification": {"verified": False}},
            "files": [{"filename": f} for f in files]}


def test_box_detection():
    assert shipit.ticked("intro\n- [x] **Ship it**: tick when done")
    assert shipit.ticked("- [X] Ship it")
    assert not shipit.ticked(shipit.SHIP_LINE)
    assert not shipit.ticked("- [x] Approved\n- [x] Maybe later")
    assert not shipit.ticked(None)


def test_green_approved_pull_request_is_merged():
    assert go(pr()) == ("merge", HEAD)


def test_nothing_happens_without_the_box():
    assert go(pr(body="- [ ] **Ship it**"))[0] == "skip"


def test_a_tick_by_anyone_but_the_owner_is_not_an_approval():
    assert go(pr(), approved=None) == ("skip", "ticked, but not by the owner")


def test_owner_tick_records_approval_of_the_current_version():
    assert go(pr(), approved=None, tick_event=True) == ("approve", HEAD)


def test_out_of_date_branch_is_updated_not_merged():
    assert go(pr(state="behind")) == ("update", HEAD)


def test_waits_for_tests_and_for_github():
    assert go(pr(), tests=None)[0] == "wait"
    assert go(pr(), tests="pending")[0] == "wait"
    assert go(pr(state=None))[0] == "wait"
    assert go(pr(), sync_running=True)[0] == "wait"


def test_failed_tests_or_conflicts_are_reported_never_merged():
    assert go(pr(), tests="failure")[0] == "note"
    assert go(pr(state="dirty"))[0] == "note"


def test_workflow_changes_always_need_a_manual_merge():
    assert go(pr(), touches_workflows=True) == ("note", "workflows")
    assert go(pr(), touches_workflows=True, tick_event=True, approved=None) == ("note", "workflows")


def test_forks_and_drafts_are_ignored():
    assert go(pr(fork=True))[0] == "skip"
    p = pr()
    p["draft"] = True
    assert go(p)[0] == "skip"


def test_app_update_merge_keeps_the_approval():
    assert go(pr(), approved=OLD, new_commits=[app_merge()]) == ("approve", HEAD)


def test_any_other_new_commit_voids_the_approval():
    other = {"author": {"login": "someone"}, "parents": [{}], "commit": {"message": "x", "verification": {}}}
    assert go(pr(), approved=OLD, new_commits=[app_merge(), other])[0] == "note"
    unverified = app_merge()
    unverified["commit"]["verification"]["verified"] = False
    assert go(pr(), approved=OLD, new_commits=[unverified])[0] == "note"
    assert go(pr(), approved=OLD, new_commits=[])[0] == "note"


def test_review_sync_commit_keeps_approval_only_on_review_pull_requests_and_only_for_records():
    review = pr(user=BOT, title="Nightly proposals 2026-11-24 (40)")
    assert go(review, approved=OLD, new_commits=[sync_commit()]) == ("approve", HEAD)
    assert go(review, approved=OLD, new_commits=[sync_commit(files=("kgkit/apply.py",))])[0] == "note"
    assert go(review, approved=OLD, new_commits=[sync_commit(message="Other")])[0] == "note"
    assert go(pr(), approved=OLD, new_commits=[sync_commit()])[0] == "note"


def test_every_note_has_text():
    for key in ("workflows", "void-x", "conflict-x", "failed-x", "refused-x"):
        assert shipit.NOTES[key.split("-")[0]]


@pytest.mark.skipif(not shutil.which("openssl"), reason="openssl not installed")
def test_app_key_signs_a_valid_jwt(tmp_path):
    key = tmp_path / "k.pem"
    subprocess.run(["openssl", "genrsa", "-out", str(key), "2048"], check=True, capture_output=True)
    token = shipit.app_jwt("123", key.read_text())
    head, claims, sig = token.split(".")
    pad = lambda s: s + "=" * (-len(s) % 4)
    assert json.loads(base64.urlsafe_b64decode(pad(head)))["alg"] == "RS256"
    body = json.loads(base64.urlsafe_b64decode(pad(claims)))
    assert body["iss"] == "123" and body["exp"] - body["iat"] <= 600
    pub = tmp_path / "p.pem"
    subprocess.run(["openssl", "rsa", "-in", str(key), "-pubout", "-out", str(pub)], check=True, capture_output=True)
    (tmp_path / "s").write_bytes(base64.urlsafe_b64decode(pad(sig)))
    ok = subprocess.run(["openssl", "dgst", "-sha256", "-verify", str(pub), "-signature", str(tmp_path / "s")],
                        input=f"{head}.{claims}".encode(), capture_output=True)
    assert ok.returncode == 0
    assert not list(tmp_path.glob("tmp*")), "the key copy must be deleted"


def test_missing_setup_does_nothing(monkeypatch, capsys):
    for k in ("SHIPIT_APP_ID", "SHIPIT_APP_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GH_READ_TOKEN", "x")
    assert shipit.run() == 0
    assert "not set up" in capsys.readouterr().out


WF = yaml.safe_load((ROOT / ".github" / "workflows" / "ship-it.yml").read_text())


def test_workflow_token_is_read_only_and_never_runs_pull_request_code():
    assert all(v == "read" for v in WF["permissions"].values())
    on = WF.get("on") or WF.get(True)
    assert "pull_request" not in on, "pull_request would run the pull request's own copy with the app key"
    steps = WF["jobs"]["ship"]["steps"]
    co = steps[0]["with"]
    assert co["ref"] == "${{ github.event.repository.default_branch }}" and co["persist-credentials"] is False
    assert not any("pip install" in (s.get("run") or "") for s in steps)
    assert "sender.login" in WF["jobs"]["ship"]["if"]


def test_review_pull_requests_carry_the_ship_it_box():
    from kgkit.proposals import to_markdown
    md = to_markdown([{"claim": "x", "why": "w", "evidence": "e", "source": "https://example.org", "wrong_if": "f",
                      "confidence": "low", "apply": "a"}])
    assert shipit.SHIP_LINE in md and not shipit.ticked(md)


def test_nightly_opens_a_fresh_review_when_todays_was_closed(tmp_path):
    """A review closed earlier the same day must not block a new one (it did on 24 Nov)."""
    import os
    stub = tmp_path / "gh"
    stub.write_text('#!/bin/sh\nif [ "$1 $2" = "pr view" ] && [ "$3" = "proposals/2026-11-24" ]; then echo CLOSED; '
                    'exit 0; fi\nexit 1\n')
    stub.chmod(0o755)
    text = (ROOT / "run_nightly.sh").read_text()
    block = text[text.index('  BRANCH="proposals/$DAY"'):text.index('  {\n    git checkout -q -B "$BRANCH"')]
    out = subprocess.run(["bash", "-c", 'DAY=2026-11-24\n' + block + '\necho "$BRANCH"'], capture_output=True,
                         text=True, env={"PATH": f"{tmp_path}:{os.environ['PATH']}"}).stdout.strip()
    assert out.startswith("proposals/2026-11-24-") and len(out) == len("proposals/2026-11-24-1530")
