"""Tests for the nightly retraction check (kgkit/retractions.py) and its place in the digest and the held list."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kgkit import retractions  # noqa: E402
from kgkit.__main__ import summarise  # noqa: E402
from kgkit.common import FetchError, Http  # noqa: E402


def recs():
    return [{"id": "tin:a", "sources": [{"url": "u", "doi": "10.1/RETRACTED"}]},
            {"id": "tin:b", "relations": [{"predicate": "treats", "object": "tin:a", "publications": ["doi:10.1/concern", "PMID:123"]}]},
            {"id": "tin:c", "sources": [{"url": "u", "doi": "10.1/fine"}]}]


def http(routes, calls=None):
    def fetch(url):
        if calls is not None:
            calls.append(url)
        for k, v in routes.items():
            if k in url:
                if isinstance(v, Exception):
                    raise v
                return v
        return {"message": {}}
    return Http(fetcher=fetch)


ROUTES = {"10.1/retracted": {"message": {"updated-by": [{"DOI": "10.1/notice", "type": "retraction", "source": "retraction-watch"}]}},
          "10.1/concern": {"message": {"updated-by": [{"DOI": "10.1/eoc", "type": "expression_of_concern", "source": "publisher"}]}}}


def test_retracted_paper_holds_back_the_record_that_cites_it(tmp_path):
    calls = []
    rep = retractions.run(recs(), http(ROUTES, calls), tmp_path)
    assert rep["held_records"] == ["tin:a"] and rep["counts"] == {"retracted": 1, "flagged": 1, "unreachable": 0}
    assert {f["status"] for f in rep["found"]} == {"retracted", "flagged"}
    assert len(calls) == 3 and all(c.startswith("https://api.crossref.org/v1/works/10.1/") for c in calls)  # PMIDs are not sent
    assert json.loads((tmp_path / "retractions.json").read_text())["papers"] == 3


def test_not_found_is_quiet_and_outage_is_reported(tmp_path):
    rep = retractions.run(recs(), http({"10.1/retracted": FetchError("HTTP 404"), "10.1/concern": FetchError("timeout")}), tmp_path)
    assert rep["held_records"] == [] and rep["unreachable"] == ["10.1/concern"]


def test_digest_names_the_paper_and_the_held_entry(tmp_path):
    rep = retractions.run(recs(), http(ROUTES), tmp_path)
    s, text = summarise({"retractions": rep})
    assert s["blocking"] and s["held_records"] == ["tin:a"]
    assert "Retraction check: 3 cited papers, 1 retracted, 1 flagged; 10.1/retracted (retraction, cited by tin:a)" in text
