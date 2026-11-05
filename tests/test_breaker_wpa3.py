"""Breaker tests for tools/publish_via_pr.sh and run_nightly.sh (WP-A3): edge cases, malformed inputs, failure modes.
Uses a local bare repo as remote and stand-in gh command (no network, no GitHub)."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "tools" / "publish_via_pr.sh"

URL = "https://example.org/pull/7"

# One shell stub drives every gh stand-in in this file; behaviour is chosen by env vars:
#   GH_VIEW_URL / GH_VIEW_EXIT     -> gh pr view output / exit code (exit default 1: no open PR)
#   GH_CREATE_URL / GH_CREATE_EXIT -> gh pr create output / exit code (default URL / 0)
#   GH_MERGE_EXIT                  -> gh pr merge exit code (default 0)
#   GH_LIST_OPEN / GH_LIST_MERGED  -> gh pr list payload
#   GH_NOISE                       -> chatter gh writes to stderr on pr create
GH_STUB = '''#!/bin/sh
echo "gh $*" >> "$GH_LOG"
case "$*" in
  *"--state open"*) printf '%s' "${GH_LIST_OPEN:-}"; exit 0 ;;
  *"--state merged"*) printf '%s' "${GH_LIST_MERGED:-}"; exit 0 ;;
esac
case "$1 $2" in
  "pr view")
    [ -n "${GH_VIEW_URL:-}" ] && echo "$GH_VIEW_URL"
    exit "${GH_VIEW_EXIT:-1}" ;;
  "pr create")
    [ -n "${GH_NOISE:-}" ] && printf '%s\\n' "$GH_NOISE" >&2
    [ -n "${GH_CREATE_URL:-}" ] && echo "$GH_CREATE_URL"
    exit "${GH_CREATE_EXIT:-0}" ;;
  "pr merge") exit "${GH_MERGE_EXIT:-0}" ;;
esac
exit 0
'''

GH_ENV_DEFAULTS = {
    "GH_VIEW_EXIT": "1",
    "GH_CREATE_URL": URL,
    "GH_CREATE_EXIT": "0",
    "GH_MERGE_EXIT": "0",
    "GH_LIST_OPEN": "",
    "GH_LIST_MERGED": "[]",
}


def sh(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def make_gh_bin(tmp_path, **overrides):
    bin_dir = tmp_path / "gh_bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(GH_STUB)
    gh.chmod(0o755)
    # Empty-string values are preserved; keys not given keep the defaults.
    env = dict(GH_ENV_DEFAULTS)
    for key in ("GH_VIEW_URL", "GH_VIEW_EXIT", "GH_CREATE_URL", "GH_CREATE_EXIT",
                "GH_MERGE_EXIT", "GH_LIST_OPEN", "GH_LIST_MERGED", "GH_NOISE"):
        if key in overrides:
            env[key] = str(overrides[key])
    return bin_dir, env


def make_repo(tmp_path):
    """Create a bare remote and working clone with main branch, plus a configured gh stub."""
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "clone", "-q", str(remote), str(work)], check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-q", "-b", "main"], cwd=work, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=work, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.org"], cwd=work, check=True, capture_output=True)
    (work / "records").mkdir()
    (work / "records" / "r.json").write_text("{}\n")
    subprocess.run(["git", "add", "."], cwd=work, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "start"], cwd=work, check=True, capture_output=True)
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=work, check=True, capture_output=True)
    main_sha = sh(remote, "rev-parse", "main").stdout.strip()
    bin_dir, gh_env = make_gh_bin(tmp_path)
    return {"remote": remote, "work": work, "tmp": tmp_path, "bin_dir": bin_dir,
            "gh_env": gh_env, "main_sha": main_sha}


def gh_log(repo):
    p = repo["tmp"] / "gh.log"
    return p.read_text() if p.exists() else ""


def run_helper(repo, *args, extra_env=None):
    env = dict(os.environ)
    env.update(repo.get("gh_env", {}))
    env["PATH"] = str(repo["bin_dir"]) + ":" + env.get("PATH", "")
    env["GH_LOG"] = str(repo["tmp"] / "gh.log")
    if extra_env:
        env.update(extra_env)
    cmd = [shutil.which("bash") or "/bin/bash", str(HELPER)] + list(args)
    return subprocess.run(cmd, cwd=repo["work"], env=env, capture_output=True, text=True)


def path_without_gh():
    gh_dir = os.path.dirname(shutil.which("gh") or "")
    return ":".join(d for d in os.environ["PATH"].split(":") if d and d != gh_dir)


# --- publish_via_pr.sh: argument validation ---


def test_zero_args_exits_1_with_usage():
    r = subprocess.run(["bash", str(HELPER)], capture_output=True, text=True)
    assert r.returncode == 1
    assert "usage:" in r.stderr


def test_one_arg_exits_1_with_usage():
    r = subprocess.run(["bash", str(HELPER), "only-branch"], capture_output=True, text=True)
    assert r.returncode == 1
    assert "usage:" in r.stderr


def test_two_args_exits_1_with_usage():
    r = subprocess.run(["bash", str(HELPER), "branch", "message"], capture_output=True, text=True)
    assert r.returncode == 1
    assert "usage:" in r.stderr


# --- publish_via_pr.sh: branch name edge cases ---


def test_empty_branch_name_fails_gracefully(tmp_path):
    repo = make_repo(tmp_path)
    r = run_helper(repo, "", "msg", "records")
    assert r.returncode == 1


def test_branch_name_with_spaces_fails(tmp_path):
    repo = make_repo(tmp_path)
    r = run_helper(repo, "nightly/apply with spaces", "msg", "records")
    assert r.returncode == 1


def test_branch_name_with_special_chars(tmp_path):
    repo = make_repo(tmp_path)
    r = run_helper(repo, "nightly/apply-2026!@#$%", "msg", "records")
    # git may or may not accept this; we just ensure it doesn't crash the script
    assert r.returncode in (0, 1)


def test_branch_name_exceeding_git_limit(tmp_path):
    repo = make_repo(tmp_path)
    long_name = "nightly/" + "a" * 500
    r = run_helper(repo, long_name, "msg", "records")
    assert r.returncode == 1


# --- publish_via_pr.sh: path edge cases ---


def test_nonexistent_path_fails(tmp_path):
    repo = make_repo(tmp_path)
    r = run_helper(repo, "nightly/test", "msg", "nonexistent/path")
    assert r.returncode == 1


def test_multiple_paths(tmp_path):
    repo = make_repo(tmp_path)
    (repo["work"] / "extra").mkdir()
    (repo["work"] / "extra" / "e.json").write_text("{}\n")
    subprocess.run(["git", "add", "."], cwd=repo["work"], capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "add extra"], cwd=repo["work"], capture_output=True)
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=repo["work"], capture_output=True)
    # Now make changes to both paths
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    (repo["work"] / "extra" / "e.json").write_text('{"changed": true}\n')
    r = run_helper(repo, "nightly/multi", "msg with multiple paths", "records", "extra")
    assert r.returncode == 0


def test_path_with_spaces(tmp_path):
    repo = make_repo(tmp_path)
    spaced = repo["work"] / "my path"
    spaced.mkdir()
    (spaced / "f.json").write_text("{}\n")
    subprocess.run(["git", "add", "."], cwd=repo["work"], capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "add spaced"], cwd=repo["work"], capture_output=True)
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=repo["work"], capture_output=True)
    (spaced / "f.json").write_text('{"changed": true}\n')
    r = run_helper(repo, "nightly/spaced", "msg with spaces in path", str(spaced))
    assert r.returncode == 0


def test_path_with_special_chars(tmp_path):
    repo = make_repo(tmp_path)
    special = repo["work"] / "path-with-dashes_and_underscores"
    special.mkdir()
    (special / "f.json").write_text("{}\n")
    subprocess.run(["git", "add", "."], cwd=repo["work"], capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "add special"], cwd=repo["work"], capture_output=True)
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=repo["work"], capture_output=True)
    (special / "f.json").write_text('{"changed": true}\n')
    r = run_helper(repo, "nightly/special", "msg with special chars in path", str(special))
    assert r.returncode == 0


# --- publish_via_pr.sh: commit message edge cases ---


def test_empty_commit_message(tmp_path):
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    r = run_helper(repo, "nightly/test", "", "records")
    # git may reject empty message or create commit with empty msg; script should survive
    assert r.returncode in (0, 1)


def test_commit_message_with_special_chars(tmp_path):
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    r = run_helper(repo, "nightly/test", 'Apply: "quotes" & special <chars>', "records")
    assert r.returncode == 0


def test_very_long_commit_message(tmp_path):
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    long_msg = "msg: " + "x" * 1000
    r = run_helper(repo, "nightly/test", long_msg, "records")
    assert r.returncode == 0


def test_commit_message_with_newlines_in_title(tmp_path):
    """Commit message with embedded newlines should be handled by gh pr create --title."""
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    msg_with_newline = "Apply proposals\nwith embedded newline"
    r = run_helper(repo, "nightly/test", msg_with_newline, "records")
    # Script should not crash; gh may or may not handle newlines in --title well
    assert r.returncode in (0, 1)


# --- publish_via_pr.sh: gh stand-in edge cases ---


def test_reuse_open_pull_request_skips_creation_and_merges(tmp_path):
    """PR already open for the branch: its URL is reused, no second PR is created, merge is still requested."""
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    r = run_helper(repo, "nightly/test", "msg", "records", extra_env={"GH_VIEW_URL": URL, "GH_VIEW_EXIT": "0"})
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == URL
    calls = gh_log(repo).splitlines()
    assert any(c.startswith("gh pr view") for c in calls), calls
    assert not any(c.startswith("gh pr create") for c in calls), calls
    assert any(c.startswith("gh pr merge") and "nightly/test" in c and "--auto" in c
               and "--squash" in c and "--delete-branch" in c for c in calls), calls
    assert sh(repo["work"], "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "main"


def test_pull_request_title_is_commit_message_not_nightly_proposals(tmp_path):
    """kgkit/apply.py picks up merged PRs titled 'Nightly proposals'; the apply/held PRs must not use that title."""
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    r = run_helper(repo, "nightly/test", "Apply approved proposals 2026-11-05", "records")
    assert r.returncode == 0, r.stderr
    creates = [c for c in gh_log(repo).splitlines() if c.startswith("gh pr create ")]
    assert creates, gh_log(repo)
    for c in creates:
        assert "--head nightly/test" in c and "--base main" in c, c
        assert "--title Apply approved proposals 2026-11-05" in c, c
        assert "Nightly proposals" not in c, c  # must avoid kgkit/apply.py's search title
        assert "merges itself once the required checks pass" in c, c


def test_gh_create_returns_empty_string_fails(tmp_path):
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    r = run_helper(repo, "nightly/test", "msg", "records", extra_env={"GH_CREATE_URL": ""})
    assert r.returncode == 1


def test_gh_missing_from_path_fails(tmp_path):
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    # PATH without gh's directory (git, bash and every other tool are still reachable)
    env = {"PATH": path_without_gh()}
    r = run_helper(repo, "nightly/test", "msg", "records", extra_env=env)
    # gh pr view and gh pr create both fail (command not found) -> publishing fails
    assert r.returncode == 1
    assert not any(c.startswith("gh pr create") for c in gh_log(repo).splitlines())


def test_gh_pr_merge_returns_url_on_stdout_with_nonzero_exit(tmp_path):
    """Spec says gh pr merge may output URL on stdout even when it fails."""
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    r = run_helper(repo, "nightly/test", "msg", "records", extra_env={"GH_MERGE_EXIT": "1"})
    # Script should still output URL and exit 3 (merge failed)
    assert r.returncode == 3
    assert URL in r.stdout


def test_gh_pr_view_succeeds_but_merge_fails_returns_url_and_exit_3(tmp_path):
    """When pr view succeeds (PR exists) but merge fails, URL should still be printed."""
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    r = run_helper(repo, "nightly/test", "msg", "records", extra_env={"GH_VIEW_EXIT": "0", "GH_MERGE_EXIT": "1"})
    assert r.returncode == 3
    assert URL in r.stdout


def test_gh_pr_view_returns_empty_string_treated_as_no_pr(tmp_path):
    """When pr view returns empty string, script should try to create a PR."""
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    r = run_helper(repo, "nightly/test", "msg", "records", extra_env={"GH_VIEW_EXIT": "0"})
    assert r.returncode == 0
    assert URL in r.stdout


def test_stdout_contains_only_url(tmp_path):
    """Standard output should carry only the PR URL; all git/gh chatter goes to stderr."""
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    r = run_helper(repo, "nightly/test", "msg", "records")
    assert r.returncode == 0
    stdout_lines = [l for l in r.stdout.splitlines() if l.strip()]
    assert len(stdout_lines) == 1
    assert stdout_lines[0] == URL


def test_gh_chatter_routed_to_stderr_not_stdout(tmp_path):
    """Spec: git and gh chatter goes to standard error, so stdout carries only the URL."""
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    r = run_helper(repo, "nightly/test", "msg", "records", extra_env={"GH_NOISE": "gh: warning text"})
    assert r.returncode == 0
    assert r.stdout.strip() == URL
    assert "gh: warning text" in r.stderr


def test_failed_publish_prints_reason_to_stderr_and_returns_to_main(tmp_path):
    """Any failure: back to main, short reason on stderr, exit 1."""
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    sh(repo["work"], "remote", "set-url", "origin", str(repo["remote"]) + "-missing")
    r = run_helper(repo, "nightly/test", "msg", "records")
    assert r.returncode == 1
    assert r.stderr.strip()
    assert sh(repo["work"], "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "main"
    assert not any(c.startswith("gh pr create") for c in gh_log(repo).splitlines())


def test_force_push_replaces_stale_remote_branch(tmp_path):
    """Same branch name already exists on the remote with unrelated history; the nightly branch must be replaced."""
    repo = make_repo(tmp_path)
    work = repo["work"]
    sh(work, "checkout", "-q", "-b", "nightly/stale")
    (work / "records" / "other.json").write_text("{}\n")
    sh(work, "add", ".")
    sh(work, "commit", "-q", "-m", "stale")
    p = sh(work, "push", "-q", "origin", "nightly/stale")
    assert p.returncode == 0, p.stderr
    sh(work, "checkout", "-q", "main")
    (work / "records" / "r.json").write_text('{"changed": true}\n')
    r = run_helper(repo, "nightly/stale", "msg", "records")
    assert r.returncode == 0, r.stderr
    remote_tip = sh(repo["remote"], "log", "-1", "--format=%s", "nightly/stale").stdout.strip()
    main_remote = sh(repo["remote"], "rev-parse", "main").stdout.strip()
    assert remote_tip == "msg"  # branch replaced by fresh history
    assert main_remote == repo["main_sha"]  # main itself untouched


# --- publish_via_pr.sh: running from non-main branch ---


def test_running_from_non_main_branch_returns_to_main(tmp_path):
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    work = repo["work"]
    # Create and checkout a different branch
    subprocess.run(["git", "checkout", "-q", "-b", "other"], cwd=work, check=True, capture_output=True)
    r = run_helper(repo, "nightly/test", "msg", "records")
    assert r.returncode == 0
    # After the script, we should be back on main
    branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=work,
                            capture_output=True, text=True).stdout.strip()
    assert branch == "main"


# --- publish_via_pr.sh: no changes to commit ---


def test_no_changes_to_commit_still_works(tmp_path):
    repo = make_repo(tmp_path)
    # records/r.json is already committed, no changes - git commit will fail with "nothing to commit"
    r = run_helper(repo, "nightly/test", "msg", "records")
    # git commit fails with "nothing to commit" -> exit 1 from failed()
    assert r.returncode == 1


# --- publish_via_pr.sh: git failure edge cases ---


def test_git_checkout_main_fails_on_no_main(tmp_path):
    """If main doesn't exist, back_to_main should not crash the script."""
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    work = repo["work"]
    # Delete main and create a different branch
    subprocess.run(["git", "checkout", "-q", "-b", "other"], cwd=work, check=True, capture_output=True)
    subprocess.run(["git", "branch", "-D", "main"], cwd=work, check=True, capture_output=True)
    r = run_helper(repo, "nightly/test", "msg", "records")
    # Script should handle missing main gracefully (back_to_main uses || true)
    assert r.returncode in (0, 1)


def test_git_add_fails_on_permission_denied(tmp_path):
    """If git add fails due to permissions, the script should exit 1."""
    repo = make_repo(tmp_path)
    # Make a file unreadable
    f = repo["work"] / "records" / "r.json"
    f.write_text('{"changed": true}\n')
    f.chmod(0o000)
    r = run_helper(repo, "nightly/test", "msg", "records")
    assert r.returncode == 1
    f.chmod(0o644)  # restore for cleanup


def test_git_push_fails_on_refused(tmp_path):
    """If git push is refused, the script should exit 1."""
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    # Set up a push restriction on the remote
    remote_hooks = repo["remote"] / "hooks"
    remote_hooks.mkdir(exist_ok=True)
    pre_receive = remote_hooks / "pre-receive"
    pre_receive.write_text("#!/bin/sh\nexit 1\n")
    pre_receive.chmod(0o755)
    r = run_helper(repo, "nightly/test", "msg", "records")
    assert r.returncode == 1


# --- publish_via_pr.sh: combined failure modes ---


def test_branch_creation_fails_on_existing_unrelated(tmp_path):
    """If branch already exists with unrelated history, -B should handle it."""
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    # First run creates the branch fine
    r1 = run_helper(repo, "nightly/test", "msg1", "records")
    assert r1.returncode == 0
    # Second run should also work (-B reuses the branch)
    (repo["work"] / "records" / "r.json").write_text('{"changed2": true}\n')
    r2 = run_helper(repo, "nightly/test", "msg2", "records")
    assert r2.returncode == 0


# --- run_nightly.sh: shell syntax validation ---


def test_run_nightly_sh_syntax_is_valid():
    r = subprocess.run(["bash", "-n", str(ROOT / "run_nightly.sh")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_publish_via_pr_sh_syntax_is_valid():
    r = subprocess.run(["bash", "-n", str(HELPER)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# --- run_nightly.sh: spec-required command lines (mirrors the style of the acceptance tests) ---


def test_run_nightly_open_apply_check_uses_spec_command():
    text = (ROOT / "run_nightly.sh").read_text()
    assert 'gh pr list --state open --search "Apply approved proposals in:title" --json number -q length' in text


def test_run_nightly_calls_publish_script_for_apply_with_spec_arguments():
    text = (ROOT / "run_nightly.sh").read_text()
    pattern = (r'tools/publish_via_pr\.sh\s+"nightly/apply-\$DAY"\s+'
               r'"Apply approved proposals \$DAY"\s+"\$\(dirname "\$RECORDS"\)"')
    assert __import__("re").search(pattern, text), text


def test_run_nightly_calls_publish_script_for_held_with_spec_arguments():
    import re
    text = (ROOT / "run_nightly.sh").read_text()
    pattern = r'tools/publish_via_pr\.sh\s+"nightly/held-\$DAY"\s+"Update held records \$DAY"\s+"\$HELD_DEST"'
    assert re.search(pattern, text), text


def test_run_nightly_apply_and_held_result_lines_match_spec():
    text = (ROOT / "run_nightly.sh").read_text()
    assert "Approved proposals: waiting, the previous apply pull request is still open" in text
    assert "Approved proposals: applied; pull request $URL merges itself once the checks pass" in text
    assert "Approved proposals: applied; pull request $URL needs a manual merge (auto-merge unavailable)" in text
    assert 'fail "could not publish applied proposals"' in text
    assert "held list goes through pull request $URL" in text
    assert "needs a manual merge (auto-merge unavailable)" in text
    assert 'could not publish the held list' in text


# --- run_nightly.sh: end-to-end against a local bare remote with the stand-in gh ---


def make_nightly_repo(tmp_path):
    """Copy the repository, turn it into a clone of a fresh bare remote, and configure the gh stub."""
    run = tmp_path / "nightly_run"
    shutil.copytree(ROOT, run, ignore=shutil.ignore_patterns(".git", "__pycache__", "reports", "exports", ".pytest_cache"))
    (run / "records" / "held_records.json").unlink(missing_ok=True)  # the run must create it, also once main holds one
    subprocess.run(["git", "init", "-q", "-b", "main", "."], cwd=run, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=run, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.org"], cwd=run, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=run, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "start"], cwd=run, check=True, capture_output=True)
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=run, check=True, capture_output=True)
    p = subprocess.run(["git", "push", "-q", "origin", "main"], cwd=run, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    bin_dir, gh_env = make_gh_bin(tmp_path)
    return {"run": run, "remote": remote, "bin_dir": bin_dir, "gh_env": gh_env,
            "tmp": tmp_path, "main_sha": sh(remote, "rev-parse", "main").stdout.strip()}


def run_nightly(nightly, extra_env=None):
    env = dict(os.environ)
    env.update(nightly["gh_env"])
    env["PATH"] = str(nightly["bin_dir"]) + ":" + env.get("PATH", "")
    env["HOME"] = str(nightly["tmp"])
    env["GH_LOG"] = str(nightly["tmp"] / "gh.log")
    env.pop("NO_GIT", None)
    if extra_env:
        env.update(extra_env)
    r = subprocess.run(["bash", str(nightly["run"] / "run_nightly.sh")],
                       cwd=nightly["run"], env=env, capture_output=True, text=True)
    md = (nightly["run"] / "reports" / "nightly.md")
    log = (nightly["run"] / "reports" / "nightly.log")
    return {"r": r,
            "md": md.read_text() if md.exists() else "",
            "log": log.read_text() if log.exists() else "",
            "gh_calls": gh_log(nightly)}


def test_run_nightly_waits_while_open_apply_pull_request(tmp_path):
    """Open apply pull request (pr list prints 7): apply and its publish must be skipped."""
    nightly = make_nightly_repo(tmp_path)
    out = run_nightly(nightly, {"GH_LIST_OPEN": "7"})
    assert "Approved proposals: waiting, the previous apply pull request is still open" in out["md"]
    assert any("--state open" in c and "Apply approved proposals in:title" in c for c in out["gh_calls"].splitlines())
    assert "Nothing to apply" not in out["log"]  # kgkit.apply never ran
    assert not any(c.startswith("gh pr create") and "--head nightly/apply-" in c
                   for c in out["gh_calls"].splitlines())  # no publish of applied proposals


def test_run_nightly_publishes_held_list_through_pull_request(tmp_path):
    """Held list changed: branch nightly/held-<day> pushed, PR created to main, auto-merge set."""
    nightly = make_nightly_repo(tmp_path)
    out = run_nightly(nightly)  # held_records.json does not exist yet; the run creates it -> publish runs
    assert "Website: held list goes through pull request %s" % URL in out["md"]
    assert "merges itself once the checks pass" in out["md"]
    assert any(c.startswith("gh pr create") and "--head " in c and "--base main" in c
               for c in out["gh_calls"].splitlines())
    assert any(c.startswith("gh pr merge") and "--auto" in c and "--squash" in c and "--delete-branch" in c
               for c in out["gh_calls"].splitlines())
    refs = sh(nightly["remote"], "for-each-ref", "--format=%(refname:short)", "refs/heads").stdout.split()
    held = [x for x in refs if x.startswith("nightly/held-")]
    assert len(held) == 1, refs
    subject = sh(nightly["remote"], "log", "-1", "--format=%s", held[0]).stdout.strip()
    assert subject.startswith("Update held records "), subject
    assert sh(nightly["remote"], "rev-parse", "main").stdout.strip() == nightly["main_sha"]  # main never pushed
    if "Proposals awaiting approval: 0" not in out["md"]:  # proposals exist: their branch must reach the remote
        assert any(x.startswith("proposals/") for x in refs), (refs, out["md"])


def test_run_nightly_held_list_auto_merge_refused(tmp_path):
    """gh pr merge fails: exit 3 wording, branch still pushed and pull request opened for a person."""
    nightly = make_nightly_repo(tmp_path)
    out = run_nightly(nightly, {"GH_MERGE_EXIT": "1"})
    assert "needs a manual merge (auto-merge unavailable)" in out["md"]
    assert URL in out["md"]
    refs = sh(nightly["remote"], "for-each-ref", "--format=%(refname:short)", "refs/heads").stdout.split()
    held = [x for x in refs if x.startswith("nightly/held-")]
    assert len(held) == 1, refs
    assert sh(nightly["remote"], "rev-parse", "main").stdout.strip() == nightly["main_sha"]
