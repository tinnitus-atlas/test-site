"""Breaker tests for .github/workflows/nightly.yml (WP-A2) against the spec: template checks plus
running the workflow's own shell steps against stand-ins (no network, no GitHub).
Only behaviour the spec requires is asserted."""
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WF_PATH = ROOT / ".github" / "workflows" / "nightly.yml"
MANUAL_PATH = ROOT / ".github" / "workflows" / "nightly-manual-test.yml"
CHECKOUT_SHA = "11d5960a326750d5838078e36cf38b85af677262"
SETUP_PYTHON_SHA = "a26af69be951a213d495a4c3e4e4022e16d87065"


@pytest.fixture(scope="module")
def wf():
    return yaml.safe_load(WF_PATH.read_text())


def triggers(wf):
    return wf.get("on", wf.get(True))


def steps(wf):
    jobs = wf["jobs"]
    assert len(jobs) == 1
    return next(iter(jobs.values()))["steps"]


def step(wf, sid):
    found = [s for s in steps(wf) if s.get("id") == sid]
    assert found, "no step with id %s" % sid
    return found[0]


def step_env(s):
    return s.get("env") or {}


def token_check_env_name(wf):
    s = step(wf, "token-check")
    names = [k for k, v in step_env(s).items() if "secrets.NIGHTLY_TOKEN" in str(v)]
    assert len(names) == 1
    return names[0]


def run_step(work, script, env_extra, tmp_path):
    out, summ = tmp_path / "out.txt", tmp_path / "summary.md"
    out.write_text("")
    summ.write_text("")
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path), "GITHUB_OUTPUT": str(out),
           "GITHUB_STEP_SUMMARY": str(summ), "GH_TOKEN": "stand-in"}
    env.update(env_extra)
    r = subprocess.run(["bash", "-e", "-c", script], cwd=work, env=env, capture_output=True, text=True)
    return r, out.read_text(), summ.read_text()


@pytest.fixture()
def checked_out(tmp_path):
    """A stand-in for the checked-out repository: a git work dir with the real tools script and
    shell scripts in place, like the workflow sees after checkout."""
    work = tmp_path / "w"
    work.mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=work, check=True)
    tools = work / "tools"
    tools.mkdir(exist_ok=True)
    (tools / "post_digest.py").write_bytes((ROOT / "tools" / "post_digest.py").read_bytes())
    return work


# --- declared structure the spec pins down exactly ---

def test_schedule_is_exactly_the_night_slot_and_manual_start(wf):
    on = triggers(wf)
    assert "workflow_dispatch" in on
    sched = on["schedule"]
    assert isinstance(sched, list) and len(sched) == 1
    assert sched[0]["cron"] == "17 2 * * *"


def test_concurrency_is_group_nightly_and_never_cancels(wf):
    conc = wf["concurrency"]
    assert isinstance(conc, dict) and conc["group"] == "nightly"
    assert conc["cancel-in-progress"] is False


def test_timeout_is_thirty_minutes(wf):
    job = next(iter(wf["jobs"].values()))
    assert job.get("timeout-minutes") == 30


def test_pinned_actions_are_exactly_the_specified_shas(wf):
    uses = [s["uses"] for s in steps(wf) if "uses" in s]
    assert all(re.search(r"@[0-9a-f]{40}$", u) for u in uses), uses
    assert "actions/checkout@" + CHECKOUT_SHA in uses
    assert "actions/setup-python@" + SETUP_PYTHON_SHA in uses


def test_step_order_matches_spec(wf):
    ids = [s.get("id") for s in steps(wf)]
    assert ids.index("token-check") < ids.index("nightly") < ids.index("digest") < ids.index("fail-on-error")


def test_biolink_dir_is_the_clone_target(wf):
    clones = [s.get("run", "") for s in steps(wf) if "biolink-model" in s.get("run", "")]
    assert clones
    dests = set(re.findall(r"biolink/biolink-model\s+(\S+)", "\n".join(clones)))
    assert dests
    assert step_env(step(wf, "nightly"))["BIOLINK_DIR"] in dests


def test_git_user_matches_the_manual_test_workflow_and_never_disables_git(wf):
    s = step(wf, "nightly")["run"]
    manual = MANUAL_PATH.read_text()
    for needle in re.findall(r'git config user\.(?:name|email) "[^"]+"', manual):
        assert needle in s, needle
    assert "NO_GIT" not in WF_PATH.read_text()


def test_every_expression_reaches_a_step_only_through_env(wf):
    for s in steps(wf):
        assert "${{" not in s.get("run", ""), s.get("id") or s.get("name")


def test_token_check_env_is_the_secret_presence_expression(wf):
    s = step(wf, "token-check")
    value = re.sub(r"\s+", "", str(step_env(s)[token_check_env_name(wf)]))
    assert value == "${{secrets.NIGHTLY_TOKEN!=''}}"


# --- the token-check step run in a stand-in runner ---

def test_token_check_notes_builtin_token_when_unset(tmp_path, wf):
    s = step(wf, "token-check")
    r, _, summ = run_step(tmp_path, s["run"], {}, tmp_path)
    assert r.returncode == 0, r.stderr
    assert "built-in token" in summ.lower()
    assert "test workflow" in summ.lower()
    assert "approval" in summ.lower()


def test_token_check_writes_nothing_when_the_token_is_set(tmp_path, wf):
    s = step(wf, "token-check")
    r, _, summ = run_step(tmp_path, s["run"], {token_check_env_name(wf): "true"}, tmp_path)
    assert r.returncode == 0, r.stderr
    assert summ.strip() == ""


def test_token_check_notes_builtin_token_for_false_means_empty_secret(tmp_path, wf):
    r, _, summ = run_step(tmp_path, step(wf, "token-check")["run"],
                          {token_check_env_name(wf): "false"}, tmp_path)
    assert r.returncode == 0, r.stderr
    assert "built-in token" in summ.lower()


# --- the nightly step run in a stand-in runner ---

@pytest.mark.parametrize("code", [0, 1, 2, 3, 255])
def test_nightly_step_survives_any_exit_code_and_records_it(wf, tmp_path, code):
    work = tmp_path / "w"
    work.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=work, check=True)
    (work / "run_nightly.sh").write_text("#!/bin/sh\necho out line\necho err line >&2\nexit %d\n" % code)
    (work / "run_validation.sh").write_text("#!/bin/sh\nexit 0\n")
    os.chmod(work / "run_nightly.sh", 0o600)  # not executable: the step must chmod +x it itself
    r, out, _ = run_step(work, step(wf, "nightly")["run"], {}, tmp_path)
    assert r.returncode == 0, r.stderr
    assert out.count("code=%d\n" % code) == 1


def test_nightly_step_swallows_a_run_that_prints_a_lot(wf, tmp_path):
    work = tmp_path / "w"
    work.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=work, check=True)
    body = "\n".join("progress %d" % i for i in range(50_000))
    (work / "run_nightly.sh").write_text("#!/bin/sh\nprintf '%s\\n' '%s'\nexit 1\n" % ("%s", body))
    (work / "run_validation.sh").write_text("#!/bin/sh\nexit 0\n")
    r, out, _ = run_step(work, step(wf, "nightly")["run"], {}, tmp_path)
    assert r.returncode == 0, r.stderr
    assert "code=1" in out


# --- the digest step run with the real post_digest.py as stand-in ---

def write_report(work, report, exit_code, webhook=None, log="some log line"):
    reports = work / "reports"
    reports.mkdir(exist_ok=True)
    if report is not None:
        (reports / "nightly.md").write_text(report)
    if log is not None:
        (reports / "nightly.log").write_text(log)
    env = {"RUN_CODE": "" if exit_code is None else str(exit_code)}
    if webhook:
        env["NIGHTLY_WEBHOOK_URL"] = webhook
    return env


NORMAL_REPORT = """Nightly run 2026-11-05
Status: all clear
Approved proposals: none newly approved
Website: held list unchanged
Biolink export: valid (KGX passed)
Pull request: https://example.org/pr/7
"""

FAILED_REPORT = """Status: RUN FAILED
git pull failed
"""


def test_digest_reports_success_day_when_code_is_zero(checked_out, tmp_path, wf):
    env = write_report(checked_out, NORMAL_REPORT, 0)
    r, _, summ = run_step(checked_out, step(wf, "digest")["run"], env, tmp_path)
    assert r.returncode == 0, r.stderr
    assert "2026-11-05" in summ.lower()
    assert "all clear" in summ.lower()


def test_digest_defaults_to_failure_when_the_nightly_step_never_wrote_a_code(checked_out, tmp_path, wf):
    env = write_report(checked_out, NORMAL_REPORT, None)
    r, _, summ = run_step(checked_out, step(wf, "digest")["run"], env, tmp_path)
    assert r.returncode == 0, r.stderr
    assert "failed" in summ.lower()


def test_digest_shows_failure_for_code_two(checked_out, tmp_path, wf):
    env = write_report(checked_out, FAILED_REPORT, 2)
    r, _, summ = run_step(checked_out, step(wf, "digest")["run"], env, tmp_path)
    assert r.returncode == 0, r.stderr
    assert "git pull failed" in summ


def test_digest_survives_a_completely_missing_report(checked_out, tmp_path, wf):
    env = write_report(checked_out, None, 1)
    r, _, summ = run_step(checked_out, step(wf, "digest")["run"], env, tmp_path)
    assert r.returncode == 0, r.stderr
    assert summ.strip()


def test_digest_still_appends_when_posting_fails_bad_webhook_address(checked_out, tmp_path, wf):
    """A webhook misconfiguration or chat-service outage must not lose the run summary."""
    env = write_report(checked_out, NORMAL_REPORT, 0, webhook="http://hooks.invalid/hook")
    r, _, summ = run_step(checked_out, step(wf, "digest")["run"], env, tmp_path)
    assert r.returncode == 0, r.stderr
    assert "2026-11-05" in summ.lower()
    assert "Digest: posting FAILED" in summ


def test_digest_handles_a_huge_report(checked_out, tmp_path, wf):
    filler = "\n".join("Freshness: line %d looks completely unremarkable but long" % i for i in range(120))
    report = "**filler** where is it\n" + filler + "\nPull request: https://example.org/pr/9\n"
    env = write_report(checked_out, report, 0)
    r, _, summ = run_step(checked_out, step(wf, "digest")["run"], env, tmp_path)
    assert r.returncode == 0, r.stderr
    assert summ.strip()


# --- the fail-on-error step ---

@pytest.mark.parametrize("code", [2, 3, ""])
def test_fail_on_error_exits_one_with_a_reason(checked_out, tmp_path, wf, code):
    env = {"RUN_CODE": str(code)}
    s = step(wf, "fail-on-error")
    r, _, _ = run_step(checked_out, s["run"], env, tmp_path)
    assert r.returncode == 1
    assert r.stdout.strip() or r.stderr.strip()


def test_fail_on_error_is_the_last_step_and_covers_success_codes(wf):
    s = step(wf, "fail-on-error")
    ids = [x.get("id") for x in steps(wf)]
    assert ids[-1] == "fail-on-error"
    cond = s["if"].replace(" ", "")
    assert "always()" in cond
    assert "steps.nightly.outputs.code!='0'" in cond
    assert "steps.nightly.outputs.code!='1'" in cond
