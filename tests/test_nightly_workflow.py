"""Acceptance tests for .github/workflows/nightly.yml (scheduled nightly run). Structure checks plus running the
workflow's own shell steps against stand-ins (no network, no GitHub)."""
import hashlib
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WF_PATH = ROOT / ".github" / "workflows" / "nightly.yml"
CHECKOUT_SHA = "11d5960a326750d5838078e36cf38b85af677262"
SETUP_PYTHON_SHA = "a26af69be951a213d495a4c3e4e4022e16d87065"


@pytest.fixture(scope="module")
def wf():
    return yaml.safe_load(WF_PATH.read_text())


def triggers(wf):
    return wf.get("on", wf.get(True))  # PyYAML reads the key `on` as True


def steps(wf):
    jobs = wf["jobs"]
    assert len(jobs) == 1
    return next(iter(jobs.values()))["steps"]


def step(wf, sid):
    found = [s for s in steps(wf) if s.get("id") == sid]
    assert found, "no step with id %s" % sid
    return found[0]


def test_daily_schedule_off_the_hour_and_manual_start(wf):
    on = triggers(wf)
    assert "workflow_dispatch" in on
    crons = [c["cron"] for c in on["schedule"]]
    assert len(crons) == 1
    minute, hour, dom, month, dow = crons[0].split()
    assert minute.isdigit() and 1 <= int(minute) <= 59
    assert hour.isdigit() and 0 <= int(hour) <= 23
    assert (dom, month, dow) == ("*", "*", "*")


def test_one_run_at_a_time_without_cancelling(wf):
    conc = wf["concurrency"]
    group = conc if isinstance(conc, str) else conc["group"]
    assert group
    assert not (isinstance(conc, dict) and conc.get("cancel-in-progress") is True)


def test_permissions_and_timeout(wf):
    assert wf["permissions"] == {"contents": "write", "pull-requests": "write"}
    job = next(iter(wf["jobs"].values()))
    assert isinstance(job.get("timeout-minutes"), int)


def test_setup_matches_live_check_with_pinned_actions(wf):
    st = steps(wf)
    uses = [s["uses"] for s in st if "uses" in s]
    assert all(re.search(r"@[0-9a-f]{40}$", u) for u in uses), uses
    assert "actions/checkout@" + CHECKOUT_SHA in uses
    py = [s for s in st if s.get("uses") == "actions/setup-python@" + SETUP_PYTHON_SHA]
    assert py and str(py[0]["with"]["python-version"]) == "3.12"
    runs = "\n".join(s.get("run", "") for s in st)
    assert "pip install -r requirements.txt" in runs
    assert re.search(r"git clone --depth 1 --branch v4\.4\.6 https://github\.com/biolink/biolink-model", runs)


def test_checkout_uses_dedicated_token_with_fallback(wf):
    co = [s for s in steps(wf) if s.get("uses", "").startswith("actions/checkout@")][0]
    tok = co["with"]["token"]
    assert "secrets.NIGHTLY_TOKEN" in tok and "github.token" in tok
    assert co["with"]["fetch-depth"] == 0


def test_nightly_step_runs_script_with_git_enabled(wf):
    s = step(wf, "nightly")
    assert "./run_nightly.sh" in s["run"]
    gh = s["env"]["GH_TOKEN"]
    assert "secrets.NIGHTLY_TOKEN" in gh and "github.token" in gh
    assert s["env"]["BIOLINK_DIR"]
    assert "NO_GIT" not in WF_PATH.read_text()


def test_no_expressions_inside_run_scripts(wf):
    for s in steps(wf):
        assert "${{" not in s.get("run", ""), s.get("name")


def test_digest_step_always_runs_with_webhook_secret(wf):
    s = step(wf, "digest")
    assert "always()" in s["if"]
    assert "tools/post_digest.py" in s["run"]
    assert "GITHUB_STEP_SUMMARY" in s["run"]
    assert s["env"]["NIGHTLY_WEBHOOK_URL"].replace(" ", "") == "${{secrets.NIGHTLY_WEBHOOK_URL}}"
    assert "steps.nightly.outputs.code" in " ".join(str(v) for v in s["env"].values())


def test_failed_run_fails_workflow_after_digest(wf):
    st = steps(wf)
    ids = [s.get("id") for s in st]
    s = step(wf, "fail-on-error")
    assert ids.index("fail-on-error") > ids.index("digest") > ids.index("nightly")
    cond = s["if"].replace(" ", "")
    assert "always()" in cond
    assert "steps.nightly.outputs.code!='0'" in cond and "steps.nightly.outputs.code!='1'" in cond
    r = subprocess.run(["bash", "-c", s["run"]], capture_output=True)
    assert r.returncode != 0


def test_live_check_workflow_unchanged():
    h = hashlib.sha256((ROOT / ".github" / "workflows" / "live-check.yml").read_bytes()).hexdigest()
    assert h == "081bc7fe40fe64e103890b4719c20658df8d5b3287f09724560d83a233eec3ab"


# ---- the workflow's own shell steps, run against stand-ins ----

def run_step(wf, sid, tmp_path, env_extra, stub_exit=None):
    s = step(wf, sid)
    work = tmp_path / "w"
    work.mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=work, check=True)
    if stub_exit is not None:
        (work / "run_nightly.sh").write_text("#!/bin/sh\nmkdir -p reports\necho 'Nightly run 2026-11-05' > reports/nightly.md\nexit %d\n" % stub_exit)
        (work / "run_validation.sh").write_text("#!/bin/sh\nexit 0\n")
    out, summ = tmp_path / "out.txt", tmp_path / "summary.md"
    out.write_text("")
    summ.write_text("")
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path), "GITHUB_OUTPUT": str(out), "GITHUB_STEP_SUMMARY": str(summ),
           "GH_TOKEN": "stand-in", "BIOLINK_DIR": str(tmp_path)}
    env.update(env_extra)
    r = subprocess.run(["bash", "-e", "-c", s["run"]], cwd=work, env=env, capture_output=True, text=True)
    return r, out.read_text(), summ.read_text()


@pytest.mark.parametrize("code", [0, 1, 2])
def test_nightly_step_records_exit_code_and_never_fails_itself(wf, tmp_path, code):
    r, out, _ = run_step(wf, "nightly", tmp_path, {}, stub_exit=code)
    assert r.returncode == 0, r.stderr
    assert re.search(r"^code=%d$" % code, out, re.M)


def test_token_check_notes_builtin_token_limits(wf, tmp_path):
    s = step(wf, "token-check")
    var = [k for k, v in s["env"].items() if "secrets.NIGHTLY_TOKEN" in str(v)]
    assert len(var) == 1
    r, _, summ = run_step(wf, "token-check", tmp_path, {var[0]: "false"})
    assert r.returncode == 0
    assert "built-in token" in summ.lower()
    assert "test workflow" in summ.lower() and "approval" in summ.lower()
    r, _, summ = run_step(wf, "token-check", tmp_path, {var[0]: "true"})
    assert r.returncode == 0
    assert "built-in token" not in summ.lower()
