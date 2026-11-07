"""Acceptance tests for WP-A7 (untrusted-text rule): the apply step reads only pull requests opened by trusted
accounts and titled "Nightly proposals ...", and model-written changes never auto-merge. No network: stand-ins."""
import json
import os
import subprocess
from pathlib import Path

from kgkit import apply

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "tools" / "publish_via_pr.sh"
URL = "https://example.org/pull/9"


def fake_runner(prs):
    def run(args):
        if args[:3] == ["gh", "pr", "list"]:
            return json.dumps(prs)
        raise AssertionError(args)
    return run


def pr(number, login, title="Nightly proposals 2026-11-05 (3)"):
    return {"number": number, "title": title, "body": "", "author": {"login": login}, "mergeCommit": {"oid": "abc"}}


def test_only_trusted_authors_and_exact_title():
    prs = [pr(1, "varioso"), pr(2, "stranger"), pr(3, "varioso-bot"),
           pr(4, "varioso", title="Nightly fixes: proposals push"), pr(5, "app/github-actions")]
    got = [p["number"] for p in apply.merged_proposal_prs(fake_runner(prs))]
    assert got == [1, 3]


def test_trusted_authors_can_be_set_by_environment(monkeypatch):
    monkeypatch.setenv("NIGHTLY_TRUSTED_AUTHORS", "someone-else")
    got = [p["number"] for p in apply.merged_proposal_prs(fake_runner([pr(1, "varioso"), pr(2, "someone-else")]))]
    assert got == [2]


GH_STUB = """#!/bin/sh
echo "$*" >> "$GH_LOG"
case "$1 $2" in
  "pr create") echo "%s"; exit 0;;
  "pr view") exit 1;;
  "pr merge") exit 0;;
esac
exit 0
""" % URL


def make_repo(tmp_path):
    remote, work, bin_dir = tmp_path / "remote.git", tmp_path / "work", tmp_path / "bin"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "clone", "-q", str(remote), str(work)], check=True, capture_output=True)
    for args in (["checkout", "-q", "-b", "main"], ["config", "user.name", "t"], ["config", "user.email", "t@example.org"]):
        subprocess.run(["git", *args], cwd=work, check=True, capture_output=True)
    (work / "records").mkdir()
    (work / "records" / "r.json").write_text("[]\n")
    subprocess.run(["git", "add", "."], cwd=work, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "start"], cwd=work, check=True)
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=work, check=True, capture_output=True)
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(GH_STUB)
    (bin_dir / "gh").chmod(0o755)
    env = {"PATH": "%s:%s" % (bin_dir, os.environ["PATH"]), "HOME": str(tmp_path), "GH_LOG": str(tmp_path / "gh.log")}
    return work, env, tmp_path / "gh.log"


def publish(work, env):
    return subprocess.run(["bash", str(HELPER), "nightly/x", "Apply approved proposals x", "records"],
                          cwd=work, env=env, capture_output=True, text=True)


def merge_calls(log):
    return [c for c in (log.read_text().splitlines() if log.exists() else []) if c.startswith("pr merge")]


def test_model_written_record_is_not_auto_merged(tmp_path):
    work, env, log = make_repo(tmp_path)
    (work / "records" / "r.json").write_text('[{"id": "x", "agentType": "automated_agent"}]\n')
    r = publish(work, env)
    assert r.returncode == 3
    assert r.stdout.strip().splitlines()[-1] == URL
    assert merge_calls(log) == []


def test_model_written_flag_is_not_auto_merged(tmp_path):
    work, env, log = make_repo(tmp_path)
    (work / "records" / "r.json").write_text('[{"id": "y"}]\n')
    r = publish(work, dict(env, MODEL_WRITTEN="1"))
    assert r.returncode == 3
    assert merge_calls(log) == []


def test_plain_change_still_auto_merges(tmp_path):
    work, env, log = make_repo(tmp_path)
    (work / "records" / "r.json").write_text('[{"id": "z"}]\n')
    r = publish(work, env)
    assert r.returncode == 0, r.stderr
    assert len(merge_calls(log)) == 1
