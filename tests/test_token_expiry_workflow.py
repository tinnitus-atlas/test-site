"""Acceptance tests for .github/workflows/token-expiry.yml: reports when NIGHTLY_TOKEN expires so the build
pipeline's pre-flight can warn 14 days ahead. Structure checks plus the step's shell run against a stand-in curl."""
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows" / "token-expiry.yml"
SECRET = "github_pat_STANDIN_never_print_me"

CURL_STUB = """#!/bin/sh
hdr=""
while [ $# -gt 0 ]; do
  case "$1" in -D) hdr="$2"; shift;; esac
  shift
done
[ -n "$hdr" ] && printf '%b' "${STUB_HEADERS:-}" > "$hdr"
printf '%s' "${STUB_CODE:-200}"
"""


@pytest.fixture(scope="module")
def wf():
    return yaml.safe_load(WF.read_text())


def the_step(wf):
    (job,) = wf["jobs"].values()
    found = [s for s in job["steps"] if s.get("id") == "expiry"]
    assert found, "no step with id expiry"
    return found[0]


def run_step(wf, tmp_path, token=SECRET, headers="", code="200"):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl = bin_dir / "curl"
    curl.write_text(CURL_STUB)
    curl.chmod(0o755)
    env = {"PATH": "%s:%s" % (bin_dir, os.environ["PATH"]), "NIGHTLY_TOKEN": token,
           "STUB_HEADERS": headers, "STUB_CODE": code}
    return subprocess.run(["bash", "-c", the_step(wf)["run"]], env=env, capture_output=True, text=True)


def test_manual_and_weekly_triggers_and_no_permissions(wf):
    on = wf.get("on", wf.get(True))
    assert "workflow_dispatch" in on
    assert on["schedule"] and on["schedule"][0]["cron"].split()[4] != "*"  # weekly, not daily
    assert wf.get("permissions") == {}


def test_secret_only_in_step_env(wf):
    step = the_step(wf)
    assert "secrets.NIGHTLY_TOKEN" in step["env"]["NIGHTLY_TOKEN"]
    assert "secrets." not in step["run"]


def test_reports_expiry_date(wf, tmp_path):
    r = run_step(wf, tmp_path, headers="HTTP/2 200\r\ngithub-authentication-token-expiration: 2027-11-05 23:00:00 UTC\r\n\r\n")
    assert r.returncode == 0, r.stderr
    assert "NIGHTLY_TOKEN expires: 2027-11-05 23:00:00 UTC" in r.stdout
    assert SECRET not in r.stdout + r.stderr


def test_no_expiry_header_means_never(wf, tmp_path):
    r = run_step(wf, tmp_path, headers="HTTP/2 200\r\n\r\n")
    assert r.returncode == 0
    assert "NIGHTLY_TOKEN expires: never" in r.stdout


def test_rejected_token_fails(wf, tmp_path):
    r = run_step(wf, tmp_path, code="401")
    assert r.returncode == 1
    assert "NIGHTLY_TOKEN expires: invalid (HTTP 401)" in r.stdout
    assert SECRET not in r.stdout + r.stderr


def test_missing_secret(wf, tmp_path):
    r = run_step(wf, tmp_path, token="")
    assert r.returncode == 0
    assert "NIGHTLY_TOKEN expires: not-configured" in r.stdout
