"""Tests for the drafting step (WP-C1): a good draft passes the gate and becomes a proposal; invented quotes,
banned wording and bad links fail; a failed draft is retried once then queued; devices are always tier B;
"sampled" review mode is refused; re-running changes nothing; the apply step writes a ticked draft."""
import copy
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kgkit import apply as ap  # noqa: E402
from kgkit import draft, draft_audit  # noqa: E402
from kgkit.common import FetchError, Http, KitError  # noqa: E402

CFG = yaml.safe_load((ROOT / "kit.tinnitus.yaml").read_text())
# The real records minus any bare entries, so these tests stay independent of what the nightly has added.
REAL = [r for r in json.loads((ROOT / "records" / "tinnitus.records.json").read_text())["records"] if not draft.is_bare(r)]

SUMMARY = ("This study tests whether a sound therapy delivered through a phone app reduces how much tinnitus bothers "
           "adults who have had it for at least six months. Tinnitus means hearing a sound, such as ringing, that has "
           "no outside source. People are placed by chance into two groups: one uses the app every day for twelve weeks "
           "and the other waits. The main measure is the change in a standard questionnaire score that rates how much "
           "tinnitus affects daily life.")
BRIEF = ("This randomized trial tests a smartphone sound therapy app in adults with chronic tinnitus. "
         "Participants use the app daily for twelve weeks.")


def bare_trial(nct="NCT06000001"):
    return {"id": f"tin:trial-{nct.lower()}", "kind": "trial", "name": "Sound therapy app for chronic tinnitus",
            "tldr": draft.PLACEHOLDER, "asOf": "2026-11-20", "xrefs": [f"CLINICALTRIALS:{nct}"], "status": "recruiting",
            "sources": [{"url": f"https://clinicaltrials.gov/study/{nct}", "label": "Registry entry"}],
            "relations": [{"predicate": "studies_condition", "object": "tin:tinnitus", "knowledgeLevel": "not_provided",
                           "agentType": "manual_validation_of_automated_agent"}]}


def bare_device(number="K260413"):
    url = f"https://api.fda.gov/device/510k.json?search=k_number%3A{number}"
    return {"id": f"tin:device-{number.lower()}", "kind": "device", "name": "Example tinnitus sound generator",
            "tldr": draft.PLACEHOLDER, "asOf": "2026-11-20",
            "facts": {"fda_submission_number": {"value": number, "source": url},
                      "fda_decision": {"value": "Substantially Equivalent", "source": url}},
            "sources": [{"url": url, "label": "Registry entry"}],
            "relations": [{"predicate": "related_to", "object": "tin:tinnitus", "knowledgeLevel": "not_provided",
                           "agentType": "manual_validation_of_automated_agent"}]}


def registry_page(nct="NCT06000001"):
    return {"protocolSection": {
        "identificationModule": {"nctId": nct, "briefTitle": "Sound therapy app for chronic tinnitus",
                                 "officialTitle": "A randomized trial of an app-based sound therapy for chronic tinnitus"},
        "descriptionModule": {"briefSummary": BRIEF},
        "conditionsModule": {"conditions": ["Tinnitus"]},
        "armsInterventionsModule": {"interventions": [{"name": "Sound therapy app", "description": "Daily listening."}]},
        "outcomesModule": {"primaryOutcomes": [{"measure": "Change in Tinnitus Handicap Inventory score"}]}}}


def http(fail=False):
    def fetch(url):
        if fail:
            raise FetchError("down")
        if "clinicaltrials.gov" in url:
            return registry_page()
        if "510k.json" in url:
            return {"results": [{"k_number": "K260413", "device_name": "Example tinnitus sound generator",
                                 "applicant": "Example Co", "decision_description": "Substantially Equivalent",
                                 "decision_date": "2026-08-13", "product_code": "KLW"}]}
        raise FetchError(url)
    return Http(fetcher=fetch)


def good(**over):
    d = {"tldr": "A trial testing whether a phone app with sound therapy makes chronic tinnitus less bothersome.",
         "summary": SUMMARY,
         "relations": [{"predicate": "studies_condition", "object": "tin:tinnitus",
                        "quote": "tests a smartphone sound therapy app in adults with chronic tinnitus"}]}
    d.update(over)
    return d


class Drafter:
    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []
        self.model = "stand-in-model"

    def __call__(self, messages):
        self.calls.append(copy.deepcopy(messages))
        a = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        return a if isinstance(a, str) else json.dumps(a)


def records_with(*extra):
    return copy.deepcopy(REAL) + list(extra)


def run(tmp_path, recs, drafter, cfg=CFG, cap=20, fail=False):
    return draft.run(recs, cfg, http(fail), drafter, drafter.model, tmp_path / "reports", tmp_path / "queue.json", cap)


def props(tmp_path):
    return json.loads((tmp_path / "reports" / "proposals.json").read_text())["proposals"]


def test_good_trial_draft_passes_and_becomes_a_tier_a_proposal(tmp_path):
    d = Drafter(good())
    rep = run(tmp_path, records_with(bare_trial()), d)
    assert rep["drafted"] == [{"record": "tin:trial-nct06000001", "tier": "A"}]
    (p,) = props(tmp_path)
    assert p["type"] == "draft" and p["tier"] == "A" and p["auto_apply"] is False
    assert p["apply"]["provenance"]["drafted_by"] == "stand-in-model" and len(p["apply"]["provenance"]["source_hash"]) == 64
    assert "- [ ] Approved" in (tmp_path / "reports" / "proposals.md").read_text()
    prompt = d.calls[0][0]["content"]
    assert BRIEF in prompt and "tin:tinnitus" in prompt and "studies_condition" in prompt


def test_invented_quote_fails_then_is_queued_after_one_retry(tmp_path):
    bad = good(relations=[{"predicate": "studies_condition", "object": "tin:tinnitus", "quote": "the app cures tinnitus in weeks"}])
    d = Drafter(bad)
    rep = run(tmp_path, records_with(bare_trial()), d)
    assert len(d.calls) == 2  # first try plus one retry with the reasons
    assert "not word for word" in d.calls[1][-1]["content"]
    assert rep["drafted"] == [] and props(tmp_path) == []
    queue = json.loads((tmp_path / "queue.json").read_text())
    assert queue[0]["record"] == "tin:trial-nct06000001" and any("word for word" in r for r in queue[0]["reasons"])


def test_retry_that_fixes_the_draft_passes(tmp_path):
    bad = good(tldr="A trial that is a breakthrough for tinnitus.")
    d = Drafter(bad, good())
    rep = run(tmp_path, records_with(bare_trial()), d)
    assert len(d.calls) == 2 and rep["drafted"][0]["tier"] == "A"
    assert "banned phrase 'breakthrough'" in d.calls[1][-1]["content"]


@pytest.mark.parametrize("over,needle", [
    ({"summary": "Too short to be a summary."}, "summary has"),
    ({"tldr": " ".join(["word"] * 31)}, "tldr has 31 words"),
    ({"relations": [{"predicate": "cures_everything", "object": "tin:tinnitus", "quote": "adults with chronic tinnitus"}]}, "not allowed"),
    ({"relations": [{"predicate": "related_to", "object": "tin:no-such-record", "quote": "adults with chronic tinnitus"}]}, "not an existing record"),
    ({"relations": [{"predicate": "related_to", "object": "tin:tinnitus",
                     "quote": "This randomized trial tests a smartphone sound therapy app in adults with chronic tinnitus. Participants use"}]}, "fewer than 15"),
    ({"relations": []}, "1 to 3"),
])
def test_gate_reasons(over, needle):
    reasons = draft.gate(good(**over), bare_trial(), BRIEF, records_with(bare_trial()), CFG)
    assert any(needle in r for r in reasons), reasons


def test_regulatory_wording_without_regulator_source_fails_the_audit_part_of_the_gate():
    d = good(tldr="A trial of an approved app for chronic tinnitus.")
    reasons = draft.gate(d, bare_trial(), BRIEF, records_with(bare_trial()), CFG)
    assert any(r.startswith("audit:") and "approved" in r for r in reasons), reasons


def test_device_drafts_are_always_tier_b(tmp_path):
    dev = bare_device()
    d = Drafter(good(tldr="A sound generator device for tinnitus.",
                     relations=[{"predicate": "related_to", "object": "tin:tinnitus", "quote": "Example tinnitus sound generator"}]))
    rep = run(tmp_path, records_with(dev), d)
    assert rep["drafted"] == [{"record": dev["id"], "tier": "B"}]
    assert "tier B" in props(tmp_path)[0]["why"]


def test_claim_predicates_route_to_tier_b():
    assert draft.tier(bare_trial(), good(relations=[{"predicate": "ameliorates"}]), CFG) == "B"


def test_sampled_mode_is_refused(tmp_path):
    cfg = copy.deepcopy(CFG)
    cfg["drafting"]["review_mode"] = "sampled"
    with pytest.raises(KitError, match="never merge by themselves"):
        run(tmp_path, records_with(bare_trial()), Drafter(good()), cfg=cfg)


def test_unreachable_source_is_queued_without_asking_the_drafter(tmp_path):
    d = Drafter(good())
    rep = run(tmp_path, records_with(bare_trial()), d, fail=True)
    assert d.calls == [] and rep["queued"][0]["reasons"][0].startswith("source unreachable")


def test_rerun_changes_nothing_for_finished_or_queued_entries(tmp_path):
    finished = copy.deepcopy(bare_trial("NCT06000002"))
    finished["tldr"] = "Already written."
    d = Drafter("not json at all")
    run(tmp_path, records_with(bare_trial(), finished), d)
    assert len(d.calls) == 2  # only the bare one, tried twice, then queued
    d2 = Drafter(good())
    rep = run(tmp_path, records_with(bare_trial(), finished), d2)
    assert d2.calls == [] and rep["skipped_queued_before"] == ["tin:trial-nct06000001"]


def test_cap_limits_the_run(tmp_path):
    recs = records_with(bare_trial("NCT06000001"), bare_trial("NCT06000003"))
    d = Drafter(good())
    rep = run(tmp_path, recs, d, cap=1)
    assert len(rep["drafted"]) + len(rep["queued"]) == 1


def test_ticked_draft_is_written_by_the_apply_step_and_passes_the_audit(tmp_path):
    from kgkit import audit
    trial = bare_trial()
    run(tmp_path, records_with(trial), Drafter(good()))
    rec_file = tmp_path / "records.json"
    rec_file.write_text(json.dumps({"records": records_with(trial)}))
    body = tmp_path / "body.md"
    body.write_text((tmp_path / "reports" / "proposals.md").read_text().replace("- [ ] Approved", "- [x] Approved"))
    assert ap.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(rec_file), "--body", str(body),
                    "--proposals", str(tmp_path / "reports" / "proposals.json"), "--label", "drafts-1"]) == 0
    recs = json.loads(rec_file.read_text())["records"]
    rec = next(r for r in recs if r["id"] == trial["id"])
    assert rec["tldr"] == good()["tldr"] and rec["summary"] == SUMMARY
    rel = rec["relations"][-1]
    assert rel["knowledgeLevel"] == "knowledge_assertion" and rel["sourceUrl"].startswith("https://clinicaltrials.gov/")
    assert rec["provenance"]["drafted_by"] == "stand-in-model" and rec["provenance"]["approved_on"]
    assert trial["id"] not in audit.run(recs, CFG, tmp_path)["held_records"]


def test_apply_refuses_a_draft_when_the_entry_changed_since(tmp_path):
    trial = bare_trial()
    run(tmp_path, records_with(trial), Drafter(good()))
    changed = copy.deepcopy(trial)
    changed["tldr"] = "Someone already wrote this."
    rec_file = tmp_path / "records.json"
    rec_file.write_text(json.dumps({"records": records_with(changed)}))
    body = tmp_path / "body.md"
    body.write_text((tmp_path / "reports" / "proposals.md").read_text().replace("- [ ] Approved", "- [x] Approved"))
    ap.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(rec_file), "--body", str(body),
             "--proposals", str(tmp_path / "reports" / "proposals.json"), "--label", "drafts-1"])
    rec = next(r for r in json.loads(rec_file.read_text())["records"] if r["id"] == trial["id"])
    assert rec["tldr"] == "Someone already wrote this." and "summary" not in rec


def test_cli_without_a_drafter_exits_2(tmp_path, monkeypatch):
    monkeypatch.delenv("DRAFTER_BASE_URL", raising=False)
    monkeypatch.delenv("DRAFTER_MODEL", raising=False)
    assert draft.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(ROOT / "records" / "tinnitus.records.json"),
                       "--reports", str(tmp_path)]) == 2


def test_prompt_is_versioned_and_states_the_rules():
    text = draft.PROMPT_FILE.read_text()
    for needle in ("Use only the SOURCE TEXT", "fewer than 15 words", "regulatory words", "JSON only"):
        assert needle in text


def test_draft_audit_samples_only_drafted_entries(tmp_path):
    done = copy.deepcopy(bare_trial())
    done.update(tldr="t", summary="s", provenance={"drafted_by": "m"})
    rec_file = tmp_path / "records.json"
    rec_file.write_text(json.dumps({"records": records_with(done)}))
    assert draft_audit.main(["--records", str(rec_file), "--reports", str(tmp_path), "--n", "30", "--seed", "1"]) == 0
    md = (tmp_path / "draft_audit.md").read_text()
    assert "Sample: 1 of 1 drafted entries" in md and done["id"] in md and "| Verdict |" in md


def test_sources_only_needs_no_drafter_and_writes_text_and_prompt(tmp_path, monkeypatch):
    monkeypatch.delenv("DRAFTER_BASE_URL", raising=False)
    rec_file = tmp_path / "records.json"
    rec_file.write_text(json.dumps({"records": records_with()}))
    code = draft.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(rec_file), "--reports", str(tmp_path),
                       "--sources-only", "--trial", "NCT06000001"], http=http())
    assert code == 0
    (e,) = json.loads((tmp_path / "draft_sources.json").read_text())
    assert e["record"] == "tin:trial-nct06000001" and BRIEF in e["source_text"] and BRIEF in e["prompt"]
    assert len(e["source_hash"]) == 64
    assert json.loads(rec_file.read_text()) == {"records": records_with()}  # nothing saved


def test_trial_option_rejects_bad_numbers(tmp_path):
    assert draft.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(ROOT / "records" / "tinnitus.records.json"),
                       "--reports", str(tmp_path), "--sources-only", "--trial", "NCT1; rm -rf /"]) == 2


def test_drafting_workflow_is_manual_and_keeps_secrets_in_env():
    text = (ROOT / ".github" / "workflows" / "drafting.yml").read_text()
    wf = yaml.safe_load(text)
    on = wf.get("on", wf.get(True))
    assert set(on) == {"workflow_dispatch"}
    run = wf["jobs"]["drafting"]["steps"][-1]["run"]
    assert "${{" not in run  # inputs and secrets reach the shell only through env


def test_quote_of_a_section_label_fails():
    d = good(relations=[{"predicate": "studies_condition", "object": "tin:tinnitus", "quote": "Conditions: Tinnitus"}])
    reasons = draft.gate(d, bare_trial(), BRIEF + "\nConditions: Tinnitus", records_with(bare_trial()), CFG)
    assert any("section label" in r for r in reasons), reasons


def test_source_text_says_whether_results_are_posted_and_that_line_is_not_quotable():
    page = registry_page()
    page["hasResults"] = True
    h = Http(fetcher=lambda url: page)
    text, _ = draft.trial_source(bare_trial(), h)
    assert text.endswith("Results posted in the registry: yes")
    d = good(relations=[{"predicate": "studies_condition", "object": "tin:tinnitus", "quote": "Results posted in the registry: yes"}])
    assert any("section label" in r for r in draft.gate(d, bare_trial(), text, records_with(bare_trial()), CFG))


def test_links_to_other_entries_are_tier_b():
    d = good(relations=[{"predicate": "related_to", "object": "tin:tinnitus-handicap-inventory", "quote": "x"}])
    assert draft.tier(bare_trial(), d, CFG) == "B"
    assert draft.tier(bare_trial(), good(), CFG) == "A"


def test_prompt_forbids_background_links_and_guessing_results():
    text = draft.PROMPT_FILE.read_text()
    assert "Never link from" in text and "Results posted in the registry" in text


def test_studio_job_files_are_valid_and_generic():
    import plistlib
    import re
    import subprocess
    job = ROOT / "tools" / "studio" / "drafting-job.sh"
    assert subprocess.run(["bash", "-n", str(job)]).returncode == 0
    plist = plistlib.loads((ROOT / "tools" / "studio" / "drafting.plist.template").read_bytes())
    assert plist["RunAtLoad"] is True and plist["StartCalendarInterval"] == {"Hour": 9, "Minute": 15}
    for f in (job, ROOT / "docs" / "studio-drafting.md"):
        assert not re.search(r"/Users/[a-z]|/home/[a-z]", f.read_text())


def test_studio_job_stops_quietly_when_the_model_server_is_down(tmp_path):
    import subprocess
    env_file = tmp_path / "kg.env"
    env_file.write_text(f"REPO_DIR={tmp_path}\nDRAFTER_BASE_URL=http://127.0.0.1:9/v1\nDRAFTER_MODEL=m\n")
    r = subprocess.run(["bash", str(ROOT / "tools" / "studio" / "drafting-job.sh")], capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "KG_DRAFTING_ENV": str(env_file)})
    assert r.returncode == 0 and "will try again" in r.stdout
