"""Acceptance tests for tools/post_digest.py (nightly digest for the chat channel). No network: urlopen is replaced."""
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import post_digest  # noqa: E402

ENV = "NIGHTLY_WEBHOOK_URL"
INSTRUCTION = ("To approve, tick the Approved box under each proposal you accept in the pull request description, "
               "then merge. Unticked items are ignored. Tomorrow's run applies the ticked ones.")

NORMAL = """Nightly run 2026-11-05
Status: blocking findings
Could not reach: ClinicalTrials.gov
Held back from publishing (2): rec-1, rec-2
Freshness: 1 of 12 critical records stale (limit 365 days)
Registry mismatches: 0 high, 1 medium, 0 low
Feeds: 3 new trials, 2 new papers, 0 new FDA device decisions
Debug: internal line that must not be posted
Approved proposals: none newly approved
Website: held list unchanged
Biolink export: valid (KGX passed)

Top proposals:
1. [high] First claim
2. [medium] Second claim
Pull request: https://example.org/pr/7
"""

CLEAR = """Nightly run 2026-11-06
Status: all clear
Feeds: 0 new trials, 0 new papers, 0 new FDA device decisions
Approved proposals: none newly approved
Website: held list unchanged
Biolink export: valid (KGX passed)

Top proposals:
none
No pull request (no proposals)
"""

FAILED = """Status: RUN FAILED
git pull failed

old log line
"""


class FakeResp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_normal_digest_header_and_copied_lines():
    d = post_digest.build_digest(NORMAL, 1)
    assert d.splitlines()[0] == "**Knowledge graph nightly run, 2026-11-05**"
    for line in ["Status: blocking findings", "Could not reach: ClinicalTrials.gov",
                 "Held back from publishing (2): rec-1, rec-2", "Approved proposals: none newly approved",
                 "Website: held list unchanged", "Freshness: 1 of 12 critical records stale (limit 365 days)",
                 "Registry mismatches: 0 high, 1 medium, 0 low",
                 "Feeds: 3 new trials, 2 new papers, 0 new FDA device decisions",
                 "Biolink export: valid (KGX passed)", "Top proposals:", "1. [high] First claim",
                 "2. [medium] Second claim", "Pull request: https://example.org/pr/7"]:
        assert line in d.splitlines(), line


def test_held_back_line_gets_warning_sentence():
    d = post_digest.build_digest(NORMAL, 1)
    assert "These records stay off the website until fixed." in d


def test_unlisted_lines_are_not_posted():
    assert "Debug:" not in post_digest.build_digest(NORMAL, 0)


def test_approval_instruction_only_with_pull_request():
    assert post_digest.build_digest(NORMAL, 0).rstrip().endswith(INSTRUCTION)
    clear = post_digest.build_digest(CLEAR, 0)
    assert INSTRUCTION not in clear
    assert "Status: all clear" in clear


def test_top_proposals_capped_at_ten():
    many = NORMAL.replace("1. [high] First claim\n2. [medium] Second claim\n",
                          "".join("%d. [low] Claim %d\n" % (i, i) for i in range(1, 13)) + "... and 2 more in the pull request\n")
    lines = post_digest.build_digest(many, 0).splitlines()
    numbered = [ln for ln in lines if ln[:1].isdigit() and ". [" in ln]
    assert len(numbered) == 10
    assert "11. [low] Claim 11" not in lines


def test_exit_code_2_gives_failure_digest_with_log_tail():
    log = "\n".join("log line %d" % i for i in range(1, 31))
    d = post_digest.build_digest(FAILED, 2, log)
    lines = d.splitlines()
    assert lines[0] == "**Knowledge graph nightly run FAILED**"
    assert "git pull failed" in lines
    assert "```" in d
    assert "log line 30" in lines and "log line 16" in lines  # last 15 lines of the log
    assert "log line 15" not in lines


def test_missing_report_gives_failure_digest():
    d = post_digest.build_digest(None, 0, "boom")
    assert d.splitlines()[0] == "**Knowledge graph nightly run FAILED**"
    assert "boom" in d


@pytest.mark.parametrize("code", [0, 1, 2])
def test_digest_never_exceeds_1800_characters(code):
    huge = NORMAL.replace("First claim", "x" * 5000).replace("Could not reach: ClinicalTrials.gov",
                                                             "Could not reach: " + "y" * 5000)
    assert len(post_digest.build_digest(huge, code, "z" * 9000 + "\n" + "w" * 9000)) <= 1800


def _files(tmp_path, report=NORMAL, log="last log line\n"):
    r, lg = tmp_path / "nightly.md", tmp_path / "nightly.log"
    if report is not None:
        r.write_text(report)
    lg.write_text(log)
    return ["--report", str(r), "--log", str(lg)]


def test_main_skips_posting_without_webhook(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(ENV, raising=False)

    def boom(*a, **k):
        raise AssertionError("must not call the network")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert post_digest.main(_files(tmp_path) + ["--exit-code", "0"]) == 0
    assert "Digest: skipped" in capsys.readouterr().out


def test_main_posts_once_with_digest_text(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(ENV, "https://hooks.example.org/abc")
    calls = []

    def fake(req, *a, **k):
        calls.append(req)
        return FakeResp(b"ok")
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert post_digest.main(_files(tmp_path) + ["--exit-code", "1"]) == 0
    assert len(calls) == 1
    req = calls[0]
    assert req.full_url == "https://hooks.example.org/abc"
    assert req.get_method() == "POST"
    body = json.loads(req.data.decode())
    assert "**Knowledge graph nightly run, 2026-11-05**" in json.dumps(body)
    out = capsys.readouterr().out
    assert "Digest: posted" in out
    assert "hooks.example.org/abc" not in out  # the webhook address is a secret


def test_main_posting_failure_does_not_fail(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(ENV, "https://hooks.example.org/abc")

    def fail(*a, **k):
        raise urllib.error.URLError("down")
    monkeypatch.setattr(urllib.request, "urlopen", fail)
    assert post_digest.main(_files(tmp_path) + ["--exit-code", "0"]) == 0
    out = capsys.readouterr().out
    assert "Digest: posting FAILED" in out
    assert "hooks.example.org/abc" not in out


def test_main_failure_digest_when_exit_2_and_report_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(ENV, "https://hooks.example.org/abc")
    sent = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, *a, **k: sent.append(req) or FakeResp(b"ok"))
    assert post_digest.main(_files(tmp_path, report=None, log="fatal: oops\n") + ["--exit-code", "2"]) == 0
    assert len(sent) == 1
    assert "FAILED" in sent[0].data.decode() and "fatal: oops" in sent[0].data.decode()
