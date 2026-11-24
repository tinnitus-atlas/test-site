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
BOT = "varioso-bot"
HEAD = "a" * 40
FP = "f" * 64
TICKED = shipit.SHIP_LINE.replace("- [ ]", "- [x]")


def pr(body=TICKED, state="clean", head=HEAD, user="varioso", title="Some change", fork=False, base="main"):
    return {"number": 7, "title": title, "body": body, "draft": False, "mergeable_state": state, "mergeable": True,
            "user": {"login": user},
            "head": {"sha": head, "ref": "branch", "repo": {"full_name": "o/other" if fork else "o/r"}},
            "base": {"ref": base, "repo": {"full_name": "o/r"}}}


def go(p, **kw):
    args = dict(default_branch="main", bot=BOT, approved=FP, current=FP, behind_by=0, touches_workflows=False,
                tests="success")
    args.update(kw)
    return shipit.decide(p, **args)


def test_box_detection_is_exact():
    assert shipit.ticked("intro\n" + TICKED)
    assert not shipit.ticked(shipit.SHIP_LINE)
    assert not shipit.ticked("- [x] Ship it")                                  # loose wording does not count
    assert not shipit.ticked(TICKED + "\n" + TICKED)                         # two boxes: ambiguous
    assert not shipit.ticked("<!-- " + TICKED + " -->")                       # hidden in a comment
    assert not shipit.ticked("```\n" + TICKED + "\n```")                    # hidden in a code block
    assert not shipit.ticked("- [x] Approved\n- [x] Maybe later") and not shipit.ticked(None)


def test_green_approved_pull_request_is_merged():
    assert go(pr()) == ("merge", HEAD)


def test_unapproved_tick_is_reported_not_merged():
    assert go(pr(), approved=None)[0] == "note" and go(pr(), approved=None)[1].startswith("unapproved")


def test_any_change_to_the_approved_content_voids_the_approval():
    assert go(pr(), current="e" * 64)[1].startswith("void")


def test_too_many_files_fails_closed():
    assert go(pr(), current=None)[1].startswith("toolarge")


def test_out_of_date_branch_is_updated_not_merged():
    assert go(pr(), behind_by=3) == ("update", HEAD)


def test_waits_for_tests():
    assert go(pr(), tests=None)[0] == "wait" and go(pr(), tests="pending")[0] == "wait"


def test_failed_tests_or_conflicts_are_reported_never_merged():
    assert go(pr(), tests="failure")[1].startswith("failed")
    assert go(pr(state="dirty"))[1].startswith("conflict")
    p = pr()
    p["mergeable"] = False
    assert go(p)[1].startswith("conflict")


def test_never_merged_here_workflows_reviews_other_bases_forks_drafts():
    assert go(pr(), touches_workflows=True) == ("note", "workflows")
    assert go(pr(user=BOT, title="Nightly proposals 2026-11-24 (40)")) == ("note", "review")
    assert go(pr(base="dev")) == ("note", "base")
    assert go(pr(fork=True))[0] == "skip"
    p = pr()
    p["draft"] = True
    assert go(p)[0] == "skip"


def test_every_note_has_text():
    for key in ("review", "base", "workflows", "unapproved-x", "toolarge-x", "void-x", "conflict-x", "failed-x",
                "updatefailed-x", "refused-x"):
        assert shipit.NOTES[key.split("-")[0]]


def test_fingerprint_ignores_updates_from_main_but_not_content_changes():
    files = [{"filename": "a.py", "status": "modified", "sha": "1"}, {"filename": "b.md", "status": "added", "sha": "2"}]
    fp = shipit.fingerprint("main", {"files": files})
    assert fp == shipit.fingerprint("main", {"files": list(reversed(files)), "behind_by": 0})
    assert fp != shipit.fingerprint("main", {"files": [files[0], dict(files[1], sha="3")]})
    assert fp != shipit.fingerprint("dev", {"files": files})
    assert shipit.fingerprint("main", {"files": [files[0]] * shipit.MAX_FILES}) is None
    assert shipit.fingerprint("main", {}) is None


def event(before, after, sender="varioso"):
    return {"action": "edited", "sender": {"login": sender}, "changes": {"body": {"from": before}},
            "pull_request": {"number": 7, "body": after, "head": {"sha": "c" * 40}}}


def test_only_the_owners_flip_of_the_box_counts():
    assert shipit.tick_change(event(shipit.SHIP_LINE, TICKED), "varioso") == (7, "tick", "c" * 40)
    assert shipit.tick_change(event(TICKED, shipit.SHIP_LINE), "varioso") == (7, "untick", "c" * 40)
    assert shipit.tick_change(event(shipit.SHIP_LINE, TICKED, sender=BOT), "varioso") is None
    assert shipit.tick_change(event(TICKED, TICKED + "\nmore text"), "varioso") is None
    title_only = event(shipit.SHIP_LINE, TICKED)
    del title_only["changes"]["body"]
    assert shipit.tick_change(title_only, "varioso") is None


def test_withdrawn_approval_cannot_be_revived_by_a_re_tick():
    approved = {"id": 1, "body": f"<!-- ship-it approved={FP} head={HEAD} -->\nok"}
    assert shipit.approval_state([approved]) == (approved, FP)
    revoked = {"id": 1, "body": shipit.REVOKED + "\nwithdrawn"}
    assert shipit.approval_state([revoked]) == (revoked, None)
    assert shipit.approval_state([]) == (None, None)


class FakeGH:
    """Stand-in GitHub API for run-level tests: a pull request, its comments and its changed files."""

    def __init__(self, files, behind=0, tests="success"):
        self.files, self.behind, self.tests, self.calls, self.comments = files, behind, tests, [], []
        self.body = TICKED
        self.head = HEAD

    def __call__(self, method, path, token, body=None):
        self.calls.append((method, path.split("?")[0], body))
        if method == "GET" and path.startswith("/repos/o/r/pulls/7"):
            p = pr(head=self.head, body=self.body)
            p["merged"] = False
            return p
        if method == "GET" and "/compare/" in path:
            return {"files": self.files, "behind_by": self.behind}
        if method == "GET" and "/check-runs" in path:
            return {"check_runs": [{"app": {"slug": "github-actions"}, "conclusion": self.tests,
                                    "started_at": "1"}]}
        if method == "GET" and "/comments" in path:
            return self.comments if "page=1" in path else []
        if method == "POST" and path.endswith("/comments"):
            self.comments.append({"id": len(self.comments) + 1, "user": {"login": "app[bot]"}, "body": body["body"]})
            return {}
        if method == "PATCH":
            cid = int(path.rsplit("/", 1)[1])
            for c in self.comments:
                if c["id"] == cid:
                    c["body"] = body["body"]
            return {}
        if method == "PUT" and path.endswith("/merge"):
            return {"sha": "d" * 40}
        return {}


def ship(fake, change=None, monkeypatch=None):
    monkeypatch.setattr(shipit, "call", fake)
    summary = []
    shipit.ship_one(shipit.Repo("o/r", "read", "write", "app[bot]"), 7, "main", BOT, change, summary)
    return summary


def test_tick_then_merge_in_one_run(monkeypatch):
    fake = FakeGH([{"filename": "a.py", "status": "modified", "sha": "1"}])
    ship(fake, (7, "tick", HEAD), monkeypatch)
    assert any(m == "PUT" and p.endswith("/merge") and b["sha"] == HEAD for m, p, b in fake.calls)


def test_a_push_after_the_tick_is_never_merged(monkeypatch):
    fake = FakeGH([{"filename": "a.py", "status": "modified", "sha": "1"}])
    ship(fake, (7, "tick", HEAD), monkeypatch)            # approves and merges version 1
    fake.calls.clear()
    fake.files = [{"filename": "a.py", "status": "modified", "sha": "2"}]   # someone pushes new content
    fake.head = "e" * 40
    ship(fake, None, monkeypatch)
    assert not any(p.endswith("/merge") for _, p, _ in fake.calls)
    assert "ship-it note=void" in fake.comments[-1]["body"]


def test_update_from_main_keeps_the_approval_and_untick_withdraws_it(monkeypatch):
    files = [{"filename": "a.py", "status": "modified", "sha": "1"}]
    fake = FakeGH(files, behind=2, tests=None)
    ship(fake, (7, "tick", HEAD), monkeypatch)
    assert any(p.endswith("/update-branch") for _, p, _ in fake.calls)
    fake.behind, fake.tests, fake.head = 0, "success", "e" * 40          # same content, now up to date
    fake.calls.clear()
    ship(fake, None, monkeypatch)
    assert any(p.endswith("/merge") for _, p, _ in fake.calls)
    fake.calls.clear()
    ship(fake, (7, "untick", fake.head), monkeypatch)
    ship(fake, None, monkeypatch)                                          # someone ticks it again: nothing
    assert not any(p.endswith("/merge") for _, p, _ in fake.calls)


def test_a_check_named_tests_from_another_app_does_not_count(monkeypatch):
    def fake(method, path, token, body=None):
        return {"check_runs": [{"app": {"slug": "some-app"}, "conclusion": "success", "started_at": "1"}]}
    monkeypatch.setattr(shipit, "call", fake)
    assert shipit.tests_result("o/r", HEAD, "t") is None


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
    assert WF["jobs"]["ship"]["environment"] == "ship-it", "the app key must be an environment secret, main only"


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
