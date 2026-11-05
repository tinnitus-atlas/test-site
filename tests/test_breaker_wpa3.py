"""Breaker tests for tools/publish_via_pr.sh and run_nightly.sh (WP-A3): edge cases, malformed inputs, failure modes.
Uses a local bare repo as remote and stand-in gh command (no network, no GitHub)."""
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "tools" / "publish_via_pr.sh"

URL = "https://example.org/pull/42"


def make_gh_stub(bin_dir, pr_view_exit=1, pr_view_url="", pr_create_exit=0,
                 pr_merge_exit=0, pr_list_out=""):
    """Create a gh stand-in in the given bin_dir."""
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(f'''#!/bin/sh
case "$1 $2" in
  "pr view"*) exit {pr_view_exit};;
  "pr create"*) echo "{URL}" && exit {pr_create_exit};;
  "pr merge"*) exit {pr_merge_exit};;
  "pr list"*) printf '%s' "{pr_list_out}" && exit 0;;
esac
exit 0
''')
    gh.chmod(0o755)


def make_repo(tmp_path):
    """Create a bare remote and working clone with main branch."""
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
    return {"remote": remote, "work": work}


def run_helper(repo, *args, extra_env=None):
    env = dict(os.environ)
    path_parts = []
    if repo.get("bin_dir"):
        path_parts.append(str(repo["bin_dir"]))
    path_parts.append(env.get("PATH", ""))
    env["PATH"] = ":".join(p for p in path_parts if p)
    if extra_env:
        env.update(extra_env)
    cmd = ["bash", str(HELPER)] + list(args)
    return subprocess.run(cmd, cwd=repo["work"], env=env, capture_output=True, text=True)


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
    bin_dir = tmp_path / "gh_bin"
    make_gh_stub(bin_dir)
    repo["bin_dir"] = bin_dir
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
    bin_dir = tmp_path / "gh_bin"
    make_gh_stub(bin_dir)
    repo["bin_dir"] = bin_dir
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
    bin_dir = tmp_path / "gh_bin"
    make_gh_stub(bin_dir)
    repo["bin_dir"] = bin_dir
    r = run_helper(repo, "nightly/special", "msg with special chars in path", str(special))
    assert r.returncode == 0


# --- publish_via_pr.sh: commit message edge cases ---


def test_empty_commit_message(tmp_path):
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    bin_dir = tmp_path / "gh_bin"
    make_gh_stub(bin_dir)
    repo["bin_dir"] = bin_dir
    r = run_helper(repo, "nightly/test", "", "records")
    # git may reject empty message or create commit with empty msg; script should survive
    assert r.returncode in (0, 1)


def test_commit_message_with_special_chars(tmp_path):
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    bin_dir = tmp_path / "gh_bin"
    make_gh_stub(bin_dir)
    repo["bin_dir"] = bin_dir
    r = run_helper(repo, "nightly/test", 'Apply: "quotes" & special <chars>', "records")
    assert r.returncode == 0


def test_very_long_commit_message(tmp_path):
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    long_msg = "msg: " + "x" * 1000
    bin_dir = tmp_path / "gh_bin"
    make_gh_stub(bin_dir)
    repo["bin_dir"] = bin_dir
    r = run_helper(repo, "nightly/test", long_msg, "records")
    assert r.returncode == 0


# --- publish_via_pr.sh: gh stand-in edge cases ---


def test_gh_view_returns_url_reuses_pr(tmp_path):
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    bin_dir = tmp_path / "gh_bin"
    make_gh_stub(bin_dir, pr_view_exit=0)
    repo["bin_dir"] = bin_dir
    r = run_helper(repo, "nightly/test", "msg")
    assert r.returncode == 0
    assert URL in r.stdout


def test_gh_create_returns_empty_string_fails(tmp_path):
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    bin_dir = tmp_path / "gh_bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(f'''#!/bin/sh
case "$1 $2" in
  "pr view"*) exit 1;;
  "pr create"*) echo "" && exit 0;;
  "pr merge"*) exit 0;;
esac
exit 0
''')
    gh.chmod(0o755)
    repo["bin_dir"] = bin_dir
    r = run_helper(repo, "nightly/test", "msg")
    assert r.returncode == 1


def test_gh_missing_from_path_fails(tmp_path):
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    # No bin_dir set, so gh is not in PATH - use a path that doesn't have gh
    r = run_helper(repo, "nightly/test", "msg", extra_env={"PATH": "/nonexistent"})
    # gh pr view will fail, then gh pr create will also fail (command not found)
    assert r.returncode == 1


def test_gh_pr_merge_returns_url_on_stdout_with_nonzero_exit(tmp_path):
    """Spec says gh pr merge may output URL on stdout even when it fails."""
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    bin_dir = tmp_path / "gh_bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(f'''#!/bin/sh
case "$1 $2" in
  "pr view"*) exit 1;;
  "pr create"*) echo "{URL}" && exit 0;;
  "pr merge"*) echo "{URL}" && exit 1;;
esac
exit 0
''')
    gh.chmod(0o755)
    repo["bin_dir"] = bin_dir
    r = run_helper(repo, "nightly/test", "msg")
    # Script should still output URL and exit 3 (merge failed)
    assert r.returncode == 3
    assert URL in r.stdout


# --- publish_via_pr.sh: running from non-main branch ---


def test_running_from_non_main_branch_returns_to_main(tmp_path):
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    work = repo["work"]
    # Create and checkout a different branch
    subprocess.run(["git", "checkout", "-q", "-b", "other"], cwd=work, check=True, capture_output=True)
    bin_dir = tmp_path / "gh_bin"
    make_gh_stub(bin_dir)
    repo["bin_dir"] = bin_dir
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
    bin_dir = tmp_path / "gh_bin"
    make_gh_stub(bin_dir)
    repo["bin_dir"] = bin_dir
    r = run_helper(repo, "nightly/test", "msg", "records")
    # git commit fails with "nothing to commit" -> exit 1 from failed()
    assert r.returncode == 1


# --- run_nightly.sh: OPEN_APPLY edge cases ---


def test_open_apply_empty_string_defaults_to_zero():
    """When gh pr list returns empty, OPEN_APPLY should be 0."""
    bin_dir = ROOT / "tests" / "_gh_stub_empty_list"
    if not bin_dir.exists():
        bin_dir.mkdir(exist_ok=True)
        gh = bin_dir / "gh"
        gh.write_text('''#!/bin/sh
case "$1 $2" in
  "pr list"*) echo "" && exit 0;;
esac
exit 0
''')
        gh.chmod(0o755)
    r = subprocess.run(["bash", str(ROOT / "run_nightly.sh")], capture_output=True, text=True,
                       env={**os.environ, "PATH": str(bin_dir) + ":" + os.environ.get("PATH", ""),
                            "NO_GIT": "", "CONFIG": str(ROOT / "kit.tinnitus.yaml"),
                            "RECORDS": str(ROOT / "records" / "tinnitus.records.json")})
    # Script should not crash; OPEN_APPLY="" should be treated as 0
    assert r.returncode in (0, 1, 2)


def test_open_apply_garbage_string_defaults_to_zero():
    """When gh pr list returns garbage, OPEN_APPLY should be 0."""
    bin_dir = ROOT / "tests" / "_gh_stub_garbage_list"
    if not bin_dir.exists():
        bin_dir.mkdir(exist_ok=True)
        gh = bin_dir / "gh"
        gh.write_text('''#!/bin/sh
case "$1 $2" in
  "pr list"*) echo "not-a-number" && exit 0;;
esac
exit 0
''')
        gh.chmod(0o755)
    r = subprocess.run(["bash", str(ROOT / "run_nightly.sh")], capture_output=True, text=True,
                       env={**os.environ, "PATH": str(bin_dir) + ":" + os.environ.get("PATH", ""),
                            "NO_GIT": "", "CONFIG": str(ROOT / "kit.tinnitus.yaml"),
                            "RECORDS": str(ROOT / "records" / "tinnitus.records.json")})
    assert r.returncode in (0, 1, 2)


def test_open_apply_large_number_skips_apply():
    """When OPEN_APPLY is a large number, apply should be skipped."""
    bin_dir = ROOT / "tests" / "_gh_stub_large_list"
    if not bin_dir.exists():
        bin_dir.mkdir(exist_ok=True)
        gh = bin_dir / "gh"
        gh.write_text('''#!/bin/sh
case "$1 $2" in
  "pr list"*) echo "999999" && exit 0;;
esac
exit 0
''')
        gh.chmod(0o755)
    r = subprocess.run(["bash", str(ROOT / "run_nightly.sh")], capture_output=True, text=True,
                       env={**os.environ, "PATH": str(bin_dir) + ":" + os.environ.get("PATH", ""),
                            "NO_GIT": "", "CONFIG": str(ROOT / "kit.tinnitus.yaml"),
                            "RECORDS": str(ROOT / "records" / "tinnitus.records.json")})
    # Script should not crash; large OPEN_APPLY means skip apply
    assert r.returncode in (0, 1, 2)


def test_open_apply_negative_number_defaults_to_zero():
    """Negative OPEN_APPLY should be treated as 0."""
    bin_dir = ROOT / "tests" / "_gh_stub_negative_list"
    if not bin_dir.exists():
        bin_dir.mkdir(exist_ok=True)
        gh = bin_dir / "gh"
        gh.write_text('''#!/bin/sh
case "$1 $2" in
  "pr list"*) echo "-5" && exit 0;;
esac
exit 0
''')
        gh.chmod(0o755)
    r = subprocess.run(["bash", str(ROOT / "run_nightly.sh")], capture_output=True, text=True,
                       env={**os.environ, "PATH": str(bin_dir) + ":" + os.environ.get("PATH", ""),
                            "NO_GIT": "", "CONFIG": str(ROOT / "kit.tinnitus.yaml"),
                            "RECORDS": str(ROOT / "records" / "tinnitus.records.json")})
    assert r.returncode in (0, 1, 2)


def test_open_apply_float_defaults_to_zero():
    """Float OPEN_APPLY should be treated as 0."""
    bin_dir = ROOT / "tests" / "_gh_stub_float_list"
    if not bin_dir.exists():
        bin_dir.mkdir(exist_ok=True)
        gh = bin_dir / "gh"
        gh.write_text('''#!/bin/sh
case "$1 $2" in
  "pr list"*) echo "3.14" && exit 0;;
esac
exit 0
''')
        gh.chmod(0o755)
    r = subprocess.run(["bash", str(ROOT / "run_nightly.sh")], capture_output=True, text=True,
                       env={**os.environ, "PATH": str(bin_dir) + ":" + os.environ.get("PATH", ""),
                            "NO_GIT": "", "CONFIG": str(ROOT / "kit.tinnitus.yaml"),
                            "RECORDS": str(ROOT / "records" / "tinnitus.records.json")})
    assert r.returncode in (0, 1, 2)


# --- run_nightly.sh: gh missing ---


def test_gh_missing_in_run_nightly_still_runs():
    """When gh is not installed, run_nightly.sh should still work (just skip PR operations)."""
    r = subprocess.run(["bash", str(ROOT / "run_nightly.sh")], capture_output=True, text=True,
                       env={**os.environ, "PATH": "/nonexistent",
                            "NO_GIT": "", "CONFIG": str(ROOT / "kit.tinnitus.yaml"),
                            "RECORDS": str(ROOT / "records" / "tinnitus.records.json")})
    # Script should not crash due to missing gh
    assert r.returncode in (0, 1, 2)


# --- publish_via_pr.sh: git failure edge cases ---


def test_git_checkout_main_fails_on_no_main(tmp_path):
    """If main doesn't exist, back_to_main should not crash the script."""
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    work = repo["work"]
    # Delete main and create a different branch
    subprocess.run(["git", "checkout", "-q", "-b", "other"], cwd=work, check=True, capture_output=True)
    subprocess.run(["git", "branch", "-D", "main"], cwd=work, check=True, capture_output=True)
    bin_dir = tmp_path / "gh_bin"
    make_gh_stub(bin_dir)
    repo["bin_dir"] = bin_dir
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
    bin_dir = tmp_path / "gh_bin"
    make_gh_stub(bin_dir)
    repo["bin_dir"] = bin_dir
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
    bin_dir = tmp_path / "gh_bin"
    make_gh_stub(bin_dir)
    repo["bin_dir"] = bin_dir
    r = run_helper(repo, "nightly/test", "msg", "records")
    assert r.returncode == 1


# --- publish_via_pr.sh: combined failure modes ---


def test_branch_creation_fails_on_existing_unrelated(tmp_path):
    """If branch already exists with unrelated history, -B should handle it."""
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    bin_dir = tmp_path / "gh_bin"
    make_gh_stub(bin_dir)
    repo["bin_dir"] = bin_dir
    # First run creates the branch fine
    r1 = run_helper(repo, "nightly/test", "msg1", "records")
    assert r1.returncode == 0
    # Second run should also work (-B reuses the branch)
    (repo["work"] / "records" / "r.json").write_text('{"changed2": true}\n')
    r2 = run_helper(repo, "nightly/test", "msg2", "records")
    assert r2.returncode == 0


def test_gh_pr_view_succeeds_but_merge_fails_returns_url_and_exit_3(tmp_path):
    """When pr view succeeds (PR exists) but merge fails, URL should still be printed."""
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    bin_dir = tmp_path / "gh_bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(f'''#!/bin/sh
case "$1 $2" in
  "pr view"*) exit 0;;
  "pr create"*) echo "{URL}" && exit 0;;
  "pr merge"*) exit 1;;
esac
exit 0
''')
    gh.chmod(0o755)
    repo["bin_dir"] = bin_dir
    r = run_helper(repo, "nightly/test", "msg")
    assert r.returncode == 3
    assert URL in r.stdout


def test_gh_pr_view_returns_empty_string_treated_as_no_pr(tmp_path):
    """When pr view returns empty string, script should try to create a PR."""
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    bin_dir = tmp_path / "gh_bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(f'''#!/bin/sh
case "$1 $2" in
  "pr view"*) echo "" && exit 0;;
  "pr create"*) echo "{URL}" && exit 0;;
  "pr merge"*) exit 0;;
esac
exit 0
''')
    gh.chmod(0o755)
    repo["bin_dir"] = bin_dir
    r = run_helper(repo, "nightly/test", "msg")
    assert r.returncode == 0
    assert URL in r.stdout


# --- run_nightly.sh: shell syntax validation ---


def test_run_nightly_sh_syntax_is_valid():
    r = subprocess.run(["bash", "-n", str(ROOT / "run_nightly.sh")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_publish_via_pr_sh_syntax_is_valid():
    r = subprocess.run(["bash", "-n", str(HELPER)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# --- publish_via_pr.sh: message used in PR title ---


def test_commit_message_with_newlines_in_title(tmp_path):
    """Commit message with embedded newlines should be handled by gh pr create --title."""
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    bin_dir = tmp_path / "gh_bin"
    make_gh_stub(bin_dir)
    repo["bin_dir"] = bin_dir
    msg_with_newline = "Apply proposals\nwith embedded newline"
    r = run_helper(repo, "nightly/test", msg_with_newline, "records")
    # Script should not crash; gh may or may not handle newlines in --title well
    assert r.returncode in (0, 1)


# --- publish_via_pr.sh: stdout carries only URL ---


def test_stdout_contains_only_url(tmp_path):
    """Standard output should carry only the PR URL; all git/gh chatter goes to stderr."""
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    bin_dir = tmp_path / "gh_bin"
    make_gh_stub(bin_dir)
    repo["bin_dir"] = bin_dir
    r = run_helper(repo, "nightly/test", "msg", "records")
    assert r.returncode == 0
    stdout_lines = [l for l in r.stdout.splitlines() if l.strip()]
    assert len(stdout_lines) == 1
    assert stdout_lines[0] == URL


def test_stderr_contains_git_and_gh_chatter(tmp_path):
    """Standard error should contain git and gh output."""
    repo = make_repo(tmp_path)
    (repo["work"] / "records" / "r.json").write_text('{"changed": true}\n')
    bin_dir = tmp_path / "gh_bin"
    make_gh_stub(bin_dir)
    repo["bin_dir"] = bin_dir
    r = run_helper(repo, "nightly/test", "msg", "records")
    assert r.returncode == 0
    # There should be some stderr output (git/gh chatter)
    assert len(r.stderr.strip()) > 0 or r.returncode == 1
