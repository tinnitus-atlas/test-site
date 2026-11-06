"""Acceptance test for WP-A5: the digest request carries a User-Agent that Discord accepts (no network)."""
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import post_digest  # noqa: E402


class _Resp:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return b"ok"


def test_digest_request_has_named_user_agent(monkeypatch):
    seen = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, *a, **k: seen.append(req) or _Resp())
    assert post_digest.post("hello", "https://hooks.example.org/x") is True
    ua = seen[0].headers.get("User-agent") or ""
    assert ua and not ua.startswith("Python-urllib")  # Discord answers the default agent with 403, error 1010


def test_http_error_reports_status_code(monkeypatch, capsys):
    import urllib.error

    def refuse(req, *a, **k):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setenv("NIGHTLY_WEBHOOK_URL", "https://hooks.example.org/x")
    assert post_digest.main(["--report", "/nonexistent", "--log", "/nonexistent"]) == 0
    captured = capsys.readouterr()
    assert "Digest: posting FAILED (HTTP 403)" in captured.out
    assert "Digest: posting FAILED (HTTP 403)" in captured.err  # the run log shows the outcome
