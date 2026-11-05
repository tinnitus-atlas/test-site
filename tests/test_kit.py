"""Tests for the Knowledge Quality Kit checks. Network calls are replaced by stand-in responses."""
import copy
import datetime as dt
import json
import sys
import urllib.parse
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kgkit import audit, doi_check, factcheck, feeds, freshness, proposals  # noqa: E402
from kgkit import __main__ as cli  # noqa: E402
from kgkit.common import FetchError, Http, normalise, tokens  # noqa: E402

CFG = yaml.safe_load((ROOT / "kit.tinnitus.yaml").read_text())
REAL = json.loads((ROOT / "records" / "tinnitus.records.json").read_text())["records"]
TODAY = dt.date.today().isoformat()


def rec(id_, kind="intervention", **kw):
    base = {"id": id_, "kind": kind, "name": kw.pop("name", id_.split(":")[1].replace("-", " ").title()),
            "tldr": kw.pop("tldr", "Example."), "asOf": kw.pop("asOf", TODAY),
            "sources": kw.pop("sources", [{"url": "https://example.org", "label": "Example"}])}
    base.update(kw)
    return base


def epmc_result(title, abstract="", year=2020, doi=None, pmid=None):
    return {"resultList": {"result": [{"title": title, "abstractText": abstract, "pubYear": str(year), "doi": doi,
                                       "pmid": pmid, "authorString": "A B", "journalInfo": {"journal": {"title": "J"}}}]}}


class StandIn:
    """Routes URLs to canned JSON. Unknown URLs raise FetchError, like an outage."""

    def __init__(self, routes):
        self.routes, self.seen = routes, []

    def __call__(self, url):
        self.seen.append(url)
        decoded = urllib.parse.unquote_plus(url)
        for needle, payload in self.routes.items():
            if needle in decoded:
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise FetchError(f"no route for {url}")


def http(routes):
    return Http(fetcher=StandIn(routes))


# --- helpers -------------------------------------------------------------------

def test_norm_id_variants():
    assert doi_check.norm_id("https://doi.org/10.1/ABC") == ("doi", "10.1/abc")
    assert doi_check.norm_id("doi:10.1/X") == ("doi", "10.1/x")
    assert doi_check.norm_id("PMID:123") == ("pmid", "123")
    assert doi_check.norm_id("123") == ("pmid", "123")
    assert doi_check.norm_id("nonsense") is None


def test_normalise_strips_tags_and_unifies_quotes():
    assert normalise("<p>It’s  <b>fine</b></p>") == "it's fine"
    assert "tinnitu" in tokens("Tinnitus studies")


# --- DOI and quote check ---------------------------------------------------------

def records_for_doi(title_ok=True, quote="reduces tinnitus distress"):
    r = rec("tin:cbt", name="Cognitive behavioural therapy for tinnitus",
            sources=[{"url": "https://x", "label": "CBT for tinnitus (Cochrane, 2020)", "doi": "10.1/cbt"}],
            relations=[{"predicate": "ameliorates", "object": "tin:tinnitus", "quote": quote,
                        "publications": ["doi:10.1/cbt"], "knowledgeLevel": "knowledge_assertion"}])
    return [rec("tin:tinnitus", "condition", name="Tinnitus"), r]


def test_doi_confirmed_and_quote_ok(tmp_path):
    h = http({'DOI:"10.1/cbt"': epmc_result("Cognitive behavioural therapy for tinnitus",
                                            "CBT reduces tinnitus distress in adults.", 2020)})
    rep = doi_check.run(records_for_doi(), h, tmp_path)
    assert {c["class"] for c in rep["citations"]} == {"confirmed"}
    assert rep["quotes"][0]["class"] == "quote_ok" and rep["held_records"] == []


def test_doi_suspect_holds_record(tmp_path):
    h = http({'DOI:"10.1/cbt"': epmc_result("Lunar regolith mineralogy", "Rocks.", 2020)})
    rep = doi_check.run(records_for_doi(), h, tmp_path)
    assert "suspect" in {c["class"] for c in rep["citations"]}
    assert rep["held_records"] == ["tin:cbt"]


def test_quote_missing_holds_record(tmp_path):
    h = http({'DOI:"10.1/cbt"': epmc_result("Cognitive behavioural therapy for tinnitus", "Something else entirely.")})
    rep = doi_check.run(records_for_doi(quote="cures tinnitus completely"), h, tmp_path)
    assert rep["quotes"][0]["class"] == "quote_missing" and rep["held_records"] == ["tin:cbt"]


def test_label_drift_when_year_differs(tmp_path):
    h = http({'DOI:"10.1/cbt"': epmc_result("Cognitive behavioural therapy for tinnitus", "CBT reduces tinnitus distress", 2016)})
    rep = doi_check.run(records_for_doi(), h, tmp_path)
    assert "label_drift" in {c["class"] for c in rep["citations"]} and rep["held_records"] == []


def test_not_indexed_and_unreachable_do_not_hold(tmp_path):
    rep = doi_check.run(records_for_doi(), http({'DOI:"10.1/cbt"': {"resultList": {"result": []}}}), tmp_path)
    assert {c["class"] for c in rep["citations"]} == {"not_indexed"}
    assert rep["quotes"][0]["class"] == "quote_unverifiable" and rep["held_records"] == []
    rep = doi_check.run(records_for_doi(), http({}), tmp_path)
    assert {c["class"] for c in rep["citations"]} == {"unreachable"} and rep["held_records"] == []


def test_doi_resolved_once_per_identifier(tmp_path):
    fetch = StandIn({'DOI:"10.1/cbt"': epmc_result("Cognitive behavioural therapy for tinnitus", "CBT reduces tinnitus distress")})
    doi_check.run(records_for_doi(), Http(fetcher=fetch), tmp_path)
    assert len(fetch.seen) == 1


# --- fact-check --------------------------------------------------------------------

def study(status="COMPLETED", phases=("NA",), pcd="2018-05", n=326):
    return {"protocolSection": {"identificationModule": {"briefTitle": "TENT-A"},
                                "statusModule": {"overallStatus": status, "primaryCompletionDateStruct": {"date": pcd, "type": "ACTUAL"}},
                                "designModule": {"phases": list(phases), "enrollmentInfo": {"count": n, "type": "ACTUAL"}}}}


def trial(**kw):
    return rec("tin:trial-x", "trial", xrefs=["CLINICALTRIALS:NCT00000001"], **kw)


def test_factcheck_status_contradiction_is_high(tmp_path):
    rep = factcheck.run([trial(status="recruiting")], CFG, http({"NCT00000001": study()}), tmp_path)
    status = [f for f in rep["findings"] if f["field"] == "status"]
    assert status[0]["severity"] == "high" and status[0]["registry"] == "completed"


def test_factcheck_missing_values_are_low_and_patched(tmp_path):
    rep = factcheck.run([trial()], CFG, http({"NCT00000001": study()}), tmp_path)
    fields = {p["field"]: p for p in rep["patches"]}
    assert fields["facts.enrollment"]["proposed"] == 326 and fields["facts.enrollment"]["severity"] == "low"
    assert fields["status"]["proposed"] == "completed"


def test_factcheck_matching_record_has_no_findings(tmp_path):
    t = trial(status="completed", facts={"phase": {"value": "na", "source": "x"},
                                         "primary_completion_date": {"value": "2018-05", "source": "x"},
                                         "enrollment": {"value": 326, "source": "x"}})
    assert factcheck.run([t], CFG, http({"NCT00000001": study()}), tmp_path)["findings"] == []


def test_factcheck_open_trial_past_completion(tmp_path):
    rep = factcheck.run([trial(status="recruiting")], CFG, http({"NCT00000001": study("RECRUITING", pcd="2020-01")}), tmp_path)
    assert any("has passed" in f["reason"] for f in rep["findings"])


def test_factcheck_outage_and_missing_id(tmp_path):
    rep = factcheck.run([trial(), rec("tin:trial-y", "trial")], CFG, http({}), tmp_path)
    assert rep["unreachable"][0]["nct"] == "NCT00000001"
    assert rep["skipped"][0]["record"] == "tin:trial-y"


# --- audit -----------------------------------------------------------------------------

def test_audit_real_records_have_no_blocking_issues(tmp_path):
    rep = audit.run(REAL, CFG, tmp_path)
    assert rep["held_records"] == [], [i for i in rep["issues"] if i["blocking"]]


@pytest.mark.parametrize("mutate,code", [
    (lambda r: r[1].pop("sources"), "no-source"),
    (lambda r: r[1]["relations"][0].update(object="tin:nowhere"), "dangling-reference"),
    (lambda r: r[1]["relations"][0].pop("quote"), "assertion-without-quote"),
    (lambda r: r[1]["relations"][0].pop("publications"), "assertion-without-source"),
    (lambda r: r[1]["relations"][0].update(predicate="loves"), "unknown-predicate"),
    (lambda r: r[1].update(kind="planet"), "unknown-kind"),
    (lambda r: r[1].update(asOf="31/10/2026"), "bad-date"),
    (lambda r: r[1].pop("tldr"), "missing-field"),
    (lambda r: r.append(copy.deepcopy(r[1])), "duplicate-id"),
])
def test_audit_blocking(tmp_path, mutate, code):
    recs = copy.deepcopy(records_for_doi())
    mutate(recs)
    rep = audit.run(recs, CFG, tmp_path)
    assert any(i["code"] == code and i["blocking"] for i in rep["issues"])
    assert rep["held_records"]


def test_audit_warnings_do_not_hold(tmp_path):
    recs = records_for_doi() + [rec("tin:lonely", name="Lonely record"),
                                rec("tin:cbt-2", name="Cognitive behavioural therapy for tinnitusx")]
    recs[1]["facts"] = {"cost": 100}
    rep = audit.run(recs, CFG, tmp_path)
    codes = {i["code"] for i in rep["issues"]}
    assert {"orphan", "near-duplicate-name", "unsourced-number"} <= codes
    assert rep["held_records"] == []


def test_audit_event_after_asof(tmp_path):
    r = rec("tin:x", asOf="2020-01-01", facts={"primary_completion_date": {"value": "2021-06-01", "source": "s"}})
    rep = audit.run([r], CFG, tmp_path)
    assert any(i["code"] == "asof-before-event" for i in rep["issues"])


# --- freshness ---------------------------------------------------------------------------

def test_freshness_breach(tmp_path):
    old = (dt.date.today() - dt.timedelta(days=400)).isoformat()
    recs = [rec(f"tin:i{i}", asOf=old) for i in range(3)] + [rec(f"tin:j{i}") for i in range(7)]
    rep = freshness.run(recs, CFG, tmp_path)
    assert rep["critical_stale"] == 3 and rep["breach"] is True


def test_freshness_status_rule_comes_first(tmp_path):
    age = (dt.date.today() - dt.timedelta(days=200)).isoformat()
    rep = freshness.run([trial(status="recruiting", asOf=age), rec("tin:t2", "trial", status="completed", asOf=age)], CFG, tmp_path)
    stale = {s["record"]: s for s in rep["stale"]}
    assert stale["tin:trial-x"]["limit_days"] == 120 and stale["tin:trial-x"]["critical"]
    assert "tin:t2" not in stale


def test_freshness_real_records_are_fresh(tmp_path):
    assert freshness.run(REAL, CFG, tmp_path)["stale"] == []


# --- feeds -------------------------------------------------------------------------------

def test_trial_feed_skips_known(tmp_path):
    payload = {"studies": [
        {"protocolSection": {"identificationModule": {"nctId": "NCT02669069", "briefTitle": "TENT-A"}}},
        {"protocolSection": {"identificationModule": {"nctId": "NCT09999999", "briefTitle": "New"},
                              "conditionsModule": {"conditions": ["Tinnitus"]},
                             "statusModule": {"overallStatus": "RECRUITING"}, "designModule": {"phases": ["PHASE2"]}}}]}
    rep = feeds.run(REAL, CFG, http({"query.cond=tinnitus": payload, "europepmc": {"resultList": {"result": []}}}), tmp_path)
    assert [c["nct"] for c in rep["trials"]["candidates"]] == ["NCT09999999"]
    assert rep["trials"]["candidates"][0]["phase"] == "phase2"


def test_paper_feed_skips_cited(tmp_path):
    payload = {"resultList": {"result": [
        {"title": "Cochrane CBT", "doi": "10.1002/14651858.CD012614.pub2"},
        {"title": "Brand new paper.", "doi": "10.9/new", "journalTitle": "J", "firstPublicationDate": TODAY}]}}
    rep = feeds.run(REAL, CFG, http({"europepmc": payload, "query.cond": {"studies": []}}), tmp_path)
    assert [c["doi"] for c in rep["papers"]["candidates"]] == ["10.9/new"]


def test_feeds_outage_is_reported(tmp_path):
    rep = feeds.run(REAL, CFG, http({}), tmp_path)
    assert rep["trials"]["status"] == "unreachable" and rep["papers"]["status"] == "unreachable"


# --- proposals ---------------------------------------------------------------------------

def test_proposals_from_reports(tmp_path):
    factcheck.run([trial(status="recruiting")], CFG, http({"NCT00000001": study()}), tmp_path)
    feeds.run([trial()], CFG, http({"query.cond": {"studies": [{"protocolSection": {"identificationModule": {"nctId": "NCT05555555", "briefTitle": "X"}, "conditionsModule": {"conditions": ["Tinnitus"]}}}]},
                                    "europepmc": {"resultList": {"result": []}}}), tmp_path)
    rep = proposals.run([trial(status="recruiting")], CFG, tmp_path)
    types = [p["type"] for p in rep["proposals"]]
    assert types[0] == "update" and "new_record" in types
    assert rep["auto_apply"] == 0
    md = (tmp_path / "proposals.md").read_text()
    assert "Wrong if" in md and "- [ ] Approved" in md


def test_applied_change_is_not_proposed_again(tmp_path):
    factcheck.run([trial(status="recruiting")], CFG, http({"NCT00000001": study()}), tmp_path)
    rep = proposals.run([trial(status="completed")], CFG, tmp_path)
    assert not any(p["apply"].get("field") == "status" for p in rep["proposals"])


def test_auto_apply_only_for_named_sources(tmp_path):
    cfg = copy.deepcopy(CFG)
    cfg["proposals"] = {"auto_apply_sources": ["clinicaltrials_gov_v2"]}
    factcheck.run([trial(status="recruiting")], cfg, http({"NCT00000001": study()}), tmp_path)
    rep = proposals.run([trial(status="recruiting")], cfg, tmp_path)
    assert rep["auto_apply"] >= 1


# --- command line --------------------------------------------------------------------------

def test_cli_offline_on_real_records(tmp_path):
    code = cli.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(ROOT / "records" / "tinnitus.records.json"),
                     "--reports", str(tmp_path), "--offline"])
    assert code == 0
    for name in ("audit.json", "freshness.json", "proposals.json", "summary.json", "summary.md", "held_records.json"):
        assert (tmp_path / name).exists()
    assert "Not run: feeds, factcheck, doi" in (tmp_path / "summary.md").read_text()


def test_summary_reports_outages():
    results = {"doi": {"counts": {"unreachable": 7}, "held_records": []},
               "factcheck": {"unreachable": [{"nct": "NCT1"}], "counts": {"high": 0, "medium": 0, "low": 0}},
               "feeds": {"trials": {"status": "unreachable"}, "papers": {"status": "ok"}}}
    s, text = cli.summarise(results)
    assert "INCOMPLETE" in text and "Europe PMC (7" in text and "trials feed" in text
    assert s["blocking"] is False and len(s["unreachable"]) == 3


def test_cli_blocking_exit_1(tmp_path):
    bad = tmp_path / "bad.json"
    recs = copy.deepcopy(REAL)
    recs[2]["relations"][0].pop("quote")
    bad.write_text(json.dumps({"records": recs}))
    code = cli.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(bad), "--reports", str(tmp_path / "r"), "--offline"])
    assert code == 1
    assert "tin:cbt" in json.loads((tmp_path / "r" / "held_records.json").read_text())["held_records"]


def test_cli_bad_input_exit_2(tmp_path, capsys):
    code = cli.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(tmp_path / "missing.json"), "--reports", str(tmp_path)])
    assert code == 2 and "not found" in capsys.readouterr().err


def test_cli_only_flag(tmp_path):
    code = cli.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(ROOT / "records" / "tinnitus.records.json"),
                     "--reports", str(tmp_path), "--only", "audit"])
    assert code == 0 and (tmp_path / "audit.json").exists() and not (tmp_path / "freshness.json").exists()


def test_real_records_doi_and_quotes_with_standin(tmp_path):
    """The real starter records against stand-in Europe PMC entries carrying the quoted sentences."""
    routes = {
        'DOI:"10.1002/14651858.cd012614.pub2"': epmc_result("Cognitive behavioural therapy for tinnitus",
            "CBT may be effective in reducing the negative impact that tinnitus can have on quality of life.", 2020),
        'DOI:"10.1002/14651858.cd013094.pub2"': epmc_result("Sound therapy (using amplification devices and/or sound generators) for tinnitus",
            "Sound therapy might result in little or no difference in tinnitus symptom severity.", 2018),
        'DOI:"10.1126/scitranslmed.abb2830"': epmc_result("Bimodal neuromodulation combining sound and tongue stimulation reduces tinnitus symptoms in a large randomized clinical study",
            "Participants achieved a statistically significant reduction in tinnitus symptom severity.", 2020),
        'DOI:"10.1136/bmjopen-2017-018465"': epmc_result("Bi-modal stimulation in the treatment of tinnitus: a study protocol", "", 2017),
        "EXT_ID:8630207": epmc_result("Development of the Tinnitus Handicap Inventory", "The total scale yielded excellent internal consistency reliability.", 1996),
        "EXT_ID:25273878": epmc_result("Clinical practice guideline: tinnitus", "", 2014),
        "EXT_ID:29074518": epmc_result("Bi-modal stimulation in the treatment of tinnitus: a study protocol", "", 2017),
    }
    rep = doi_check.run(REAL, http(routes), tmp_path)
    assert rep["held_records"] == [], rep
    assert {q["class"] for q in rep["quotes"]} <= {"quote_ok", "quote_unverifiable"}
    assert sum(q["class"] == "quote_ok" for q in rep["quotes"]) == 5
