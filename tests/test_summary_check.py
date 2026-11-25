"""Tests for the summary check (offline: stand-in model and stand-in web)."""
import datetime as dt
import json
from pathlib import Path

from kgkit import summary_check as sc
from kgkit.common import summary_hash

TODAY = dt.date(2026, 11, 25)
ABSTRACT = "Cognitive behavioural therapy reduced tinnitus distress compared with no treatment. It did not change loudness."


class Web:
    """Stand-in for the web: Europe PMC knows one paper; everything else is empty."""
    def __init__(self):
        self.calls = 0

    def get_json(self, url):
        self.calls += 1
        if "europepmc" in url and "10.1000%2Fcbt" in url.replace("/", "%2F"):
            return {"resultList": {"result": [{"title": "CBT for tinnitus", "abstractText": ABSTRACT}]}}
        return {}


def rec(**kw):
    r = {"id": "t:cbt", "kind": "intervention", "name": "CBT", "tldr": "CBT reduces tinnitus distress but not loudness.",
         "sources": [{"url": "https://doi.org/10.1000/cbt", "doi": "10.1000/cbt"}], "relations": []}
    r.update(kw)
    return r


def model(answer):
    calls = []

    def call(messages):
        calls.append(messages)
        return json.dumps(answer)
    call.model = "google/gemini-2.5-flash"
    call.calls = calls
    return call


def run(records, checker, state=None, tmp=None, today=TODAY, cfg=None):
    state = {} if state is None else state
    report = sc.run(records, cfg or {}, Web(), checker, getattr(checker, "model", None), state, tmp, today)
    return report, state


def test_family_names():
    assert sc.family("google/gemini-2.5-flash") == "google"
    assert sc.family("qwen2.5-14b-instruct") == "qwen"
    assert sc.family("deepseek/deepseek-chat") == "deepseek"
    assert sc.family("meta-llama/llama-3.3-70b") == "meta"
    assert sc.family("mistralai/mistral-small") == "mistral"
    assert sc.family("anthropic/claude-sonnet") == "anthropic"
    assert sc.family("my-own-model") is None


def test_supported_summary_is_ok(tmp_path):
    m = model({"claims": [{"claim": "CBT reduces distress", "verdict": "supported"},
                          {"claim": "not loudness", "verdict": "supported"}]})
    report, state = run([rec()], m, tmp=tmp_path)
    assert state["t:cbt"]["status"] == "ok" and state["t:cbt"]["summary_hash"] == summary_hash(rec())
    assert "reduced tinnitus distress" in m.calls[0][1]["content"]  # the abstract was sent as source text


def test_contradiction_needs_a_real_quote(tmp_path):
    real = model({"claims": [{"claim": "CBT reduces loudness", "verdict": "contradicted",
                              "evidence": "It did not change loudness."}]})
    _, state = run([rec(tldr="CBT reduces tinnitus loudness.")], real, tmp=tmp_path)
    assert state["t:cbt"]["status"] == "flagged"
    made_up = model({"claims": [{"claim": "CBT reduces loudness", "verdict": "contradicted",
                                 "evidence": "CBT made loudness worse in every patient."}]})
    _, state = run([rec(tldr="CBT reduces tinnitus loudness.")], made_up, tmp=tmp_path)
    assert state["t:cbt"]["status"] == "unclear"  # an invented quote cannot put a warning on the site


def test_same_family_as_drafter_is_never_checked(tmp_path):
    m = model({"claims": []})
    report, state = run([rec(provenance={"drafted_by": "gemini-2.0-pro"})], m, tmp=tmp_path)
    assert state == {} and report["skipped"][0]["reason"].startswith("same")
    assert m.calls == []


def test_unknown_checker_family_checks_nothing(tmp_path):
    m = model({"claims": []})
    m.model = "house-model"
    report, state = run([rec()], m, tmp=tmp_path)
    assert state == {} and "unknown" in report["note"]


def test_unchanged_records_are_not_sent_again_until_recheck(tmp_path):
    m = model({"claims": [{"claim": "x", "verdict": "supported"}]})
    _, state = run([rec()], m, tmp=tmp_path)
    run([rec()], m, state, tmp=tmp_path, today=TODAY + dt.timedelta(days=3))
    assert len(m.calls) == 1
    run([rec(tldr="CBT changes how people react to tinnitus.")], m, state, tmp=tmp_path, today=TODAY + dt.timedelta(days=3))
    assert len(m.calls) == 2  # summary changed
    run([rec(tldr="CBT changes how people react to tinnitus.")], m, state, tmp=tmp_path, today=TODAY + dt.timedelta(days=40))
    assert len(m.calls) == 3  # recheck after 30 days


def test_nightly_limit_and_no_source(tmp_path):
    m = model({"claims": [{"claim": "x", "verdict": "supported"}]})
    recs = [rec(id=f"t:{i}") for i in range(3)] + [rec(id="t:none", sources=[{"url": "https://example.org/page"}])]
    report, state = run(recs, m, tmp=tmp_path, cfg={"summary_check": {"max_per_night": 2}})
    assert len(m.calls) == 2
    assert state["t:none"]["status"] == "no_source"
    assert any(s["reason"].startswith("nightly limit") for s in report["skipped"])


def test_bad_answer_keeps_old_result(tmp_path):
    def broken(messages):
        return "not json"
    broken.model = "openai/gpt-4o-mini"
    old = {"t:cbt": {"status": "ok", "summary_hash": "x", "source_hash": "y", "checked_on": "2026-01-01"}}
    report, state = run([rec()], broken, dict(old), tmp=tmp_path)
    assert state == old and "checker failed" in report["skipped"][0]["reason"]


def test_cli_without_checker_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("CHECKER_BASE_URL", raising=False)
    root = Path(__file__).resolve().parents[1]
    state = tmp_path / "summary_checks.json"
    code = sc.main(["--config", str(root / "kit.tinnitus.yaml"), "--records", str(root / "records/tinnitus.records.json"),
                    "--state", str(state), "--reports", str(tmp_path)], http=Web())
    assert code == 0 and not state.exists()
