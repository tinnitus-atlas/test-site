"""Acceptance tests for tools/publish_via_pr.sh and its use in run_nightly.sh: main stays protected, so the nightly
publishes record changes through a pull request set to auto-merge. Uses a local bare repository as the remote and a
stand-in `gh` command (no network, no GitHub)."""
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "tools" / "publish_via_pr.sh"
URL = "https://example.org/pull/42"

GH_STUB = """#!/bin/sh
echo "$*" >> "$GH_LOG"
case "$1 $2" in
  "pr create") echo "%s"; exit "${GH_CREATE_EXIT:-0}";;
  "pr view") exit 1;;
  "pr merge") exit "${GH_MERGE_EXIT:-0}";;
  "pr list") printf '%%s' "${GH_LIST_OUT:-}"; exit 0;;
esac
exit 0
""" % URL


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    remote, work, bin_dir = tmp_path / "remote.git", tmp_path / "work", tmp_path / "bin"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "clone", "-q", str(remote), str(work)], check=True, capture_output=True)
    git(work, "checkout", "-q", "-b", "main")
    git(work, "config", "user.name", "test")
    git(work, "config", "user.email", "test@example.org")
    (work / "records").mkdir()
    (work / "records" / "r.json").write_text("{}\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "start")
    git(work, "push", "-q", "origin", "main")
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(GH_STUB)
    gh.chmod(0o755)
    (work / "records" / "r.json").write_text('{"changed": true}\n')
    env = {"PATH": "%s:%s" % (bin_dir, os.environ["PATH"]), "HOME": str(tmp_path), "GH_LOG": str(tmp_path / "gh.log")}
    return {"remote": remote, "work": work, "env": env, "log": tmp_path / "gh.log"}


def run_helper(repo, extra_env=None, branch="nightly/apply-2026-11-05", msg="Apply approved proposals 2026-11-05"):
    env = dict(repo["env"], **(extra_env or {}))
    return subprocess.run(["bash", str(HELPER), branch, msg, "records"], cwd=repo["work"], env=env, capture_output=True, text=True)


def gh_calls(repo):
    return repo["log"].read_text().splitlines() if repo["log"].exists() else []


def test_publishes_branch_and_sets_auto_merge(repo):
    r = run_helper(repo)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().splitlines()[-1] == URL
    remote_branch = git(repo["remote"], "log", "-1", "--format=%s", "nightly/apply-2026-11-05")
    assert remote_branch == "Apply approved proposals 2026-11-05"
    assert git(repo["remote"], "log", "-1", "--format=%s", "main") == "start"  # main itself is never pushed
    calls = gh_calls(repo)
    assert any(re.search(r"^pr create .*--head nightly/apply-2026-11-05.*--base main", c) for c in calls), calls
    assert any(c.startswith("pr merge") and "nightly/apply-2026-11-05" in c and "--auto" in c and "--squash" in c
               and "--delete-branch" in c for c in calls), calls
    assert git(repo["work"], "rev-parse", "--abbrev-ref", "HEAD") == "main"


def test_auto_merge_refused_leaves_pull_request_for_a_person(repo):
    r = run_helper(repo, {"GH_MERGE_EXIT": "1"})
    assert r.returncode == 3
    assert URL in r.stdout
    assert git(repo["work"], "rev-parse", "--abbrev-ref", "HEAD") == "main"


def test_push_failure_returns_1_and_back_on_main(repo):
    git(repo["work"], "remote", "set-url", "origin", str(repo["remote"]) + "-missing")
    r = run_helper(repo)
    assert r.returncode == 1
    assert git(repo["work"], "rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert not any(c.startswith("pr create") for c in gh_calls(repo))


def test_pull_request_failure_returns_1(repo):
    r = run_helper(repo, {"GH_CREATE_EXIT": "1"})
    assert r.returncode == 1
    assert git(repo["work"], "rev-parse", "--abbrev-ref", "HEAD") == "main"


def test_run_nightly_never_pushes_main_directly():
    text = (ROOT / "run_nightly.sh").read_text()
    assert not re.search(r"git push[^\n]*\borigin main\b", text)
    assert text.count("tools/publish_via_pr.sh") >= 2  # applied proposals and the held list


def test_run_nightly_waits_for_open_apply_pull_request():
    text = (ROOT / "run_nightly.sh").read_text()
    assert "gh pr list" in text and "Apply approved proposals" in text
    assert "--state open" in text
