"""Breaker tests for tools/post_digest.py (WP-A1): edge cases, spec-required security/format behaviour."""
import io
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import post_digest  # noqa: E402

ENV = "NIGHTLY_WEBHOOK_URL"
WARNING = "These records stay off the website until fixed."
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

FAILED = """Status: RUN FAILED
git pull failed
"""


class FakeResp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# --- post(): security gate ---


def test_post_returns_false_then_never_touches_network_for_non_https(monkeypatch):
    calls = []

    def boom(*a, **k):
        calls.append((a, k))
        return FakeResp(b"ok")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    bad = ["", " ", "http://hooks.example.org/x", "file:///etc/passwd",
           "ftp://hooks.example.org/x", "HTTPS://hooks.example.org/x",
           "https:/hooks.example.org/x", "javascript:alert(1)", "https//no-scheme"]
    for url in bad:
        assert post_digest.post("hi", url) is False, url
    assert not calls  # no network call at all


def test_post_posts_json_payload_over_https_and_returns_true(monkeypatch):
    calls = []

    def fake(ur, *a, **k):
        calls.append((ur, k))
        return FakeResp(b"ok")
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    r = post_digest.post("digest body", "https://hooks.example.org/abc")
    assert r is True
    assert len(calls) == 1
    req, kwargs = calls[0]
    assert req.full_url == "https://hooks.example.org/abc"
    assert req.get_method() == "POST"
    assert req.headers.get("Content-type") == "application/json"
    assert json.loads(req.data.decode()) == {"content": "digest body", "text": "digest body"}
    assert kwargs.get("timeout") == 15


def test_post_forwards_explicit_timeout(monkeypatch):
    seen = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, *a, **k: seen.append(k) or FakeResp(b"ok"))
    assert post_digest.post("x", "https://h.example/x", timeout=0.5) is True
    assert seen[0].get("timeout") == 0.5


def test_post_never_raises_on_any_error(monkeypatch):
    for exc in [ValueError("bad"), OSError("down"), TypeError("weird"), MemoryError("big")]:
        def boom(req, *a, _e=exc, **k):
            raise _e
        monkeypatch.setattr(urllib.request, "urlopen", boom)
        assert post_digest.post("x", "https://h.example/x") is False


# --- post(): the required nosemgrep comment, only urlopen call ---


def test_normal_digest_ignores_log_tail():
    d = post_digest.build_digest(NORMAL, 0, "SECRET-LOG CONTENT")
    assert "SECRET-LOG" not in d


def test_warning_sits_directly_after_held_back_line():
    d = post_digest.build_digest(NORMAL, 1)
    lines = d.splitlines()
    held = [i for i, l in enumerate(lines) if l.startswith("Held back from publishing")]
    assert len(held) == 1
    assert lines[held[0] + 1] == WARNING


def test_no_warning_without_held_back_line():
    clear = "Nightly run 2026-11-06\nStatus: all clear\nFeeds: 0 new trials\nTop proposals:\nnone\n"
    assert WARNING not in post_digest.build_digest(clear, 0)


def test_exit_0_with_failed_status_report_is_still_a_normal_digest():
    d = post_digest.build_digest("Nightly run 2026-01-01\nStatus: RUN FAILED\nbye\n", 0)
    assert d.splitlines()[0] == "**Knowledge graph nightly run, 2026-01-01**"
    assert "**Knowledge graph nightly run FAILED**" not in d
    assert "Status: RUN FAILED" in d.splitlines()


def test_unlisted_lines_are_not_posted_including_proposals_trailer():
    many = NORMAL.replace("1. [high] First claim\n2. [medium] Second claim\n",
                          "".join("%d. [low] Claim %d\n" % (i, i) for i in range(1, 13))
                          + "... and 2 more in the pull request\n")
    d = post_digest.build_digest(many, 0)
    assert "... and 2 more in the pull request" not in d.splitlines()
    clear = "Nightly run 2026-11-06\nStatus: all clear\nTop proposals:\nnone\nNo pull request (no proposals)\n"
    d2 = post_digest.build_digest(clear, 0)
    assert "No pull request (no proposals)" not in d2.splitlines()


def test_top_proposals_capped_and_pull_request_still_last():
    many = NORMAL.replace("1. [high] First claim\n2. [medium] Second claim\n",
                          "".join("%d. [low] Claim %d\n" % (i, i) for i in range(1, 13))
                          + "... and 2 more in the pull request\n")
    d = post_digest.build_digest(many, 0)
    lines = d.splitlines()
    numbered = [l for l in lines if l[:1].isdigit() and ". [" in l]
    assert len(numbered) == 10
    assert "12. [low] Claim 12" not in lines
    last = lines.index("Pull request: https://example.org/pr/7")
    assert lines[last + 1] == INSTRUCTION
    assert lines[-1] == INSTRUCTION


def test_exactly_ten_proposals_all_copied():
    ten = NORMAL.replace("1. [high] First claim\n2. [medium] Second claim\n",
                         "".join("%d. [low] Claim %d\n" % (i, i) for i in range(1, 11)))
    numbered = [l for l in post_digest.build_digest(ten, 0).splitlines() if l[:1].isdigit() and ". [" in l]
    assert len(numbered) == 10 and numbered[-1] == "10. [low] Claim 10"


# --- build_digest(): failure digest details ---


def test_failure_reason_is_the_line_after_status_run_failed():
    log = "\n".join("log line %d" % i for i in range(1, 31))
    d = post_digest.build_digest(FAILED, 2, log)
    lines = d.splitlines()
    assert lines[0] == "**Knowledge graph nightly run FAILED**"
    assert lines[1] == "git pull failed"
    sent = log.splitlines()[-15:]
    for l in sent:
        assert l in lines
    assert "log line 15" not in lines and "log line 1" not in lines


def test_status_run_failed_at_end_of_report_does_not_crash():
    d = post_digest.build_digest("Nightly run 2026-11-05\nStatus: RUN FAILED", 2, "log\n")
    assert d.splitlines()[0] == "**Knowledge graph nightly run FAILED**"
    assert "log" in d.splitlines()


def test_failure_digest_huge_log_and_huge_report_still_fit_and_keep_header():
    huge_report = "Status: RUN FAILED\n" + "r" * 6000
    huge_log = ("z" * 1900 + "\n") * 3
    d = post_digest.build_digest(huge_report, 2, huge_log)
    assert len(d) <= 1800
    assert d.startswith("**Knowledge graph nightly run FAILED**")


def test_normal_digest_huge_date_line_fits_1800_and_keeps_header():
    report = "Nightly run " + "d" * 6000 + "\nStatus: ok\n"
    d = post_digest.build_digest(report, 0)
    assert len(d) <= 1800
    assert d.startswith("**Knowledge graph nightly run, ")


# --- main(): CLI, env, network behaviour ---


def _write(tmp_path, report=NORMAL, log="last log line\n"):
    r, lg = tmp_path / "nightly.md", tmp_path / "nightly.log"
    if report is not None:
        r.write_text(report)
    lg.write_text(log)
    return ["--report", str(r), "--log", str(lg), "--exit-code", "0"]


def test_main_treats_whitespace_webhook_env_as_unconfigured(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(ENV, "   ")
    boom = AssertionError("network touched")

    def fail(*a, **k):
        raise boom
    monkeypatch.setattr(urllib.request, "urlopen", fail)
    assert post_digest.main(_write(tmp_path)) == 0
    out = capsys.readouterr().out
    assert "Digest: skipped (no webhook configured)" in out


def test_main_never_posts_non_https_webhook_and_hides_address(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(ENV, " http://secret-token.example/hook ")
    boom = AssertionError("network touched")

    def fail(*a, **k):
        raise boom
    monkeypatch.setattr(urllib.request, "urlopen", fail)
    assert post_digest.main(_write(tmp_path)) == 0
    out = capsys.readouterr().out
    assert "Digest: posting FAILED" in out
    assert "secret-token.example" not in out


def test_main_missing_report_and_missing_log_still_exits_0(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(ENV, raising=False)
    argv = ["--report", str(tmp_path / "no.md"), "--log", str(tmp_path / "no.log"), "--exit-code", "2"]
    assert post_digest.main(argv) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "**Knowledge graph nightly run FAILED**"
    assert "Digest: skipped" in out


def test_main_prints_digest_before_the_digest_line(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(ENV, raising=False)
    assert post_digest.main(_write(tmp_path)) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "**Knowledge graph nightly run, 2026-11-05**"
    assert "Digest: skipped" in out[-1]


def test_main_posting_failure_prints_short_reason_not_address(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(ENV, "https://secret-token.example/hook")

    class PanicError(Exception):
        pass

    def fail(req, *a, **k):
        raise PanicError("https://secret-token.example/hook exploded")
    monkeypatch.setattr(urllib.request, "urlopen", fail)
    assert post_digest.main(_write(tmp_path)) == 0
    out = capsys.readouterr().out
    line = [l for l in out.splitlines() if l.startswith("Digest:")][0]
    assert line.startswith("Digest: posting FAILED (")
    assert "secret-token.example" not in out


def test_main_exit_code_2_uses_failure_digest_and_posting_fails_gracefully(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(ENV, "https://secret-token.example/hook")

    def fail(*a, **k):
        raise OSError("down")
    monkeypatch.setattr(urllib.request, "urlopen", fail)
    argv = _write(tmp_path, report=FAILED, log="\n".join("l%d" % i for i in range(20)))[:-1] + ["2"]
    assert post_digest.main(argv) == 0
    out = capsys.readouterr().out
    assert "**Knowledge graph nightly run FAILED**" in out
    assert "git pull failed" in out
    assert "Digest: posting FAILED" in out
    assert "secret-token.example" not in out
