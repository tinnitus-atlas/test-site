"""Tests for the device feed, the regulatory audit rule and the manual quote override."""
import copy
import datetime as dt
import json
import sys
import urllib.parse
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kgkit import apply as ap  # noqa: E402
from kgkit import audit, doi_check, feeds, proposals  # noqa: E402
from kgkit.common import FetchError, Http  # noqa: E402

CFG = yaml.safe_load((ROOT / "kit.tinnitus.yaml").read_text())
REAL = json.loads((ROOT / "records" / "tinnitus.records.json").read_text())["records"]


def standin(routes):
    def fetch(url):
        d = urllib.parse.unquote_plus(url)
        for needle, payload in routes.items():
            if needle in d:
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise FetchError(f"no route {url}")
    return Http(fetcher=fetch)


DEVICE_ROUTES = {
    "classification.json": {"results": [{"product_code": "KLW", "device_name": "Masker, Tinnitus"}]},
    "510k.json": {"results": [
        {"k_number": "K999999", "device_name": "Example Sound Generator", "applicant": "Example Co",
         "decision_date": (dt.date.today() - dt.timedelta(days=10)).isoformat(), "decision_description": "Substantially Equivalent", "product_code": "KLW"}]},
}


# --- device feed ----------------------------------------------------------------

def test_device_feed_discovers_codes_and_candidates(tmp_path):
    rep = feeds.devices(REAL, CFG["feeds"]["devices"], standin(DEVICE_ROUTES))
    assert rep["product_codes"] == ["KLW", "QVN"]
    c = rep["candidates"][0]
    assert c["number"] == "K999999" and c["url"].startswith("https://api.fda.gov/device/510k.json")


def test_device_feed_no_matches_is_empty_not_outage():
    routes = {"classification.json": FetchError("404 for x"), "510k.json": FetchError("404 for y")}
    rep = feeds.devices(REAL, CFG["feeds"]["devices"], standin(routes))
    assert rep["status"] == "ok" and rep["candidates"] == []


def test_device_feed_outage():
    rep = feeds.devices(REAL, CFG["feeds"]["devices"], standin({}))
    assert rep["status"] == "unreachable"


def test_device_feed_ignores_decisions_before_window():
    routes = copy.deepcopy(DEVICE_ROUTES)
    routes["510k.json"]["results"].append({"k_number": "K013827", "device_name": "Old masker", "decision_date": "2002-01-15"})
    rep = feeds.devices(REAL, CFG["feeds"]["devices"], standin(routes))
    assert [c["number"] for c in rep["candidates"]] == ["K999999"]


def test_trial_feed_ignores_trials_not_updated_in_window(tmp_path):
    recent = (dt.date.today() - dt.timedelta(days=3)).isoformat()
    payload = {"studies": [
        {"protocolSection": {"identificationModule": {"nctId": "NCT01111111", "briefTitle": "Old"},
                             "statusModule": {"lastUpdatePostDateStruct": {"date": "2015-05-01"}}}},
        {"protocolSection": {"identificationModule": {"nctId": "NCT02222222", "briefTitle": "Recent"},
                             "conditionsModule": {"conditions": ["Tinnitus"]},
                             "statusModule": {"lastUpdatePostDateStruct": {"date": recent}}}}]}
    rep = feeds.trials(REAL, CFG["feeds"]["trials"], standin({"query.cond=tinnitus": payload}))
    assert [c["nct"] for c in rep["candidates"]] == ["NCT02222222"]


def test_lenire_is_known_so_its_de_novo_is_not_proposed_as_new():
    routes = {"classification.json": FetchError("404 for x"),
              "510k.json": {"results": [{"k_number": "DEN210033", "device_name": "Lenire Tinnitus Treatment Device",
                                         "decision_date": (dt.date.today() - dt.timedelta(days=5)).isoformat()}]}}
    assert feeds.devices(REAL, CFG["feeds"]["devices"], standin(routes))["candidates"] == []


def test_device_feed_skips_known_numbers():
    recs = copy.deepcopy(REAL)
    recs.append({"id": "tin:device-k999999", "kind": "device", "name": "x", "tldr": "x", "asOf": "2026-11-01",
                 "sources": [{"url": "https://api.fda.gov"}], "facts": {"fda_submission_number": {"value": "K999999", "source": "https://api.fda.gov/x"}}})
    rep = feeds.devices(recs, CFG["feeds"]["devices"], standin(DEVICE_ROUTES))
    assert rep["candidates"] == []


def test_device_proposal_applies_and_passes_regulatory_rule(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "feeds.json").write_text(json.dumps({"devices": feeds.devices(REAL, CFG["feeds"]["devices"], standin(DEVICE_ROUTES))}))
    props = proposals.run(REAL, CFG, reports)["proposals"]
    assert props[0]["type"] == "new_record" and "K999999" in props[0]["claim"]
    recs = copy.deepcopy(REAL)
    res = ap.apply_selected(recs, props, {1: props[0]["claim"]}, CFG, [], "2026-11-01")
    new = next(r for r in recs if r["id"] == "tin:device-k999999")
    assert res["applied"][0]["created"] and new["facts"]["fda_decision"]["value"] == "Substantially Equivalent"
    assert new["relations"][0]["predicate"] == "related_to"
    assert audit.run(recs, CFG, tmp_path / "a")["held_records"] == []
    again = ap.apply_selected(recs, props, {1: props[0]["claim"]}, CFG, [], "2026-11-01")
    assert again["skipped"]


# --- regulatory rule ---------------------------------------------------------------

def base(**kw):
    r = {"id": "tin:device-x", "kind": "device", "name": "Device X", "tldr": "A device.", "asOf": "2026-11-01",
         "sources": [{"url": "https://maker.example.com/news"}]}
    r.update(kw)
    return r


def codes(recs, tmp_path):
    return {i["code"] for i in audit.run(recs, CFG, tmp_path)["issues"] if i["blocking"]}


def test_claim_word_without_regulator_source_blocks(tmp_path):
    assert "regulatory-claim-without-regulator-source" in codes([base(tldr="FDA cleared hearing device.")], tmp_path)


def test_claim_word_with_regulator_source_passes(tmp_path):
    r = base(tldr="FDA cleared hearing device.", sources=[{"url": "https://www.accessdata.fda.gov/x"}])
    assert "regulatory-claim-without-regulator-source" not in codes([r], tmp_path)


def test_lookalike_domain_is_not_a_regulator(tmp_path):
    r = base(tldr="Approved in 2024.", sources=[{"url": "https://fda.gov.example.com/x"}])
    assert "regulatory-claim-without-regulator-source" in codes([r], tmp_path)


def test_regulatory_fact_needs_its_own_regulator_source(tmp_path):
    r = base(sources=[{"url": "https://www.fda.gov/x"}], facts={"fda_decision_date": {"value": "2023-01-01", "source": "https://maker.example.com"}})
    assert "regulatory-fact-without-regulator-source" in codes([r], tmp_path)


def test_no_claim_no_rule(tmp_path):
    assert not {c for c in codes([base()], tmp_path) if c.startswith("regulatory")}


def test_real_records_pass_regulatory_rule(tmp_path):
    assert not {c for c in codes(REAL, tmp_path) if c.startswith("regulatory")}


# --- manual quote override -------------------------------------------------------------

def test_manual_quote_override(tmp_path):
    recs = [{"id": "tin:t", "kind": "condition", "name": "Tinnitus", "tldr": "x", "asOf": "2026-11-01", "sources": [{"url": "u"}]},
            {"id": "tin:cbt", "kind": "intervention", "name": "CBT for tinnitus", "tldr": "x", "asOf": "2026-11-01",
             "sources": [{"url": "u", "label": "CBT tinnitus", "doi": "10.1/cbt"}],
             "relations": [{"predicate": "ameliorates", "object": "tin:t", "quote": "words only in the full text",
                            "publications": ["doi:10.1/cbt"], "knowledgeLevel": "knowledge_assertion",
                            "quoteVerified": {"by": "editor", "on": "2026-11-01"}}]}]
    h = Http(fetcher=lambda url: {"resultList": {"result": [{"title": "CBT for tinnitus", "abstractText": "Other text."}]}})
    rep = doi_check.run(recs, h, tmp_path)
    assert rep["quotes"][0]["class"] == "quote_manual_ok" and rep["held_records"] == []


# --- trial relevance filter and seen list -------------------------------------------

def _study(nct, title, conditions, official=None):
    recent = (dt.date.today() - dt.timedelta(days=3)).isoformat()
    return {"protocolSection": {
        "identificationModule": {"nctId": nct, "briefTitle": title, **({"officialTitle": official} if official else {})},
        "conditionsModule": {"conditions": conditions},
        "statusModule": {"lastUpdatePostDateStruct": {"date": recent}}}}


def test_trial_feed_drops_studies_that_only_mention_the_condition():
    payload = {"studies": [
        _study("NCT03000001", "Sleep aid in chronic pain", ["Insomnia", "Chronic Pain"]),
        _study("NCT03000002", "Sound therapy trial", ["Tinnitus"]),
        _study("NCT03000003", "Bimodal stimulation for Tinnitus", ["Hearing Disorder"]),
        _study("NCT03000004", "Device study", ["Hearing Disorder"], official="A trial of masking in chronic TINNITUS")]}
    rep = feeds.trials(REAL, CFG["feeds"]["trials"], standin({"query.cond=tinnitus": payload}))
    assert [c["nct"] for c in rep["candidates"]] == ["NCT03000002", "NCT03000003", "NCT03000004"]
    assert rep["off_topic_skipped"] == ["NCT03000001"]


def test_trial_feed_relevance_terms_are_configurable():
    payload = {"studies": [_study("NCT03000005", "Ringing in the ears study", ["Hearing Disorder"])]}
    conf = {**CFG["feeds"]["trials"], "relevance_terms": ["ringing in the ears"]}
    rep = feeds.trials(REAL, conf, standin({"query.cond=tinnitus": payload}))
    assert [c["nct"] for c in rep["candidates"]] == ["NCT03000005"]


def _feed_report():
    return {"trials": {"candidates": [{"nct": "NCT03000002", "title": "T", "url": "u"}]},
            "papers": {"candidates": [{"title": "P", "doi": "10.1/abc", "url": "u2"}]},
            "devices": {"candidates": []}}


def test_proposal_keys_are_stable():
    props = proposals.from_feeds(_feed_report())
    assert sorted(proposals.proposal_key(p) for p in props) == ["new_record:trial:clinicaltrials:nct03000002",
                                                                  "review_paper:doi:10.1/abc"]


def test_seen_proposals_are_not_proposed_again(tmp_path):
    from kgkit.common import write_report
    write_report(tmp_path, "feeds", _feed_report())
    first = proposals.run(REAL, CFG, tmp_path)
    assert first["count"] == 2
    seen = {proposals.proposal_key(p) for p in first["proposals"]}
    second = proposals.run(REAL, CFG, tmp_path, seen)
    assert second["count"] == 0 and second["already_reviewed_skipped"] == 2


def test_merged_unticked_feed_proposals_land_in_seen_list(tmp_path):
    import shutil
    rec = tmp_path / "records.json"
    shutil.copy(ROOT / "records" / "tinnitus.records.json", rec)
    props = proposals.from_feeds(_feed_report())
    (tmp_path / "proposals.json").write_text(json.dumps({"proposals": props}))
    body = proposals.to_markdown(props)  # nothing ticked
    (tmp_path / "body.md").write_text(body)
    code = ap.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(rec), "--body", str(tmp_path / "body.md"),
                    "--proposals", str(tmp_path / "proposals.json"), "--label", "t1"])
    assert code == 0
    seen = json.loads((tmp_path / "seen_proposals.json").read_text())
    assert {e["key"] for e in seen} == {"new_record:trial:clinicaltrials:nct03000002", "review_paper:doi:10.1/abc"}
    code = ap.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(rec), "--body", str(tmp_path / "body.md"),
                    "--proposals", str(tmp_path / "proposals.json"), "--label", "t2"])
    assert len(json.loads((tmp_path / "seen_proposals.json").read_text())) == 2  # no duplicates
