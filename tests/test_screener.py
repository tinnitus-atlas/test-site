"""Tests for the screener (recommendations, learning, optional AI, pre-tick) and the decision history with
"Maybe later" (kgkit/decisions.py and the apply step)."""
import copy
import datetime as dt
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kgkit import apply as ap  # noqa: E402
from kgkit import decisions, proposals, screener  # noqa: E402

CFG = yaml.safe_load((ROOT / "kit.tinnitus.yaml").read_text())


def trial(nct, title, status="recruiting"):
    return proposals.from_feeds({"trials": {"candidates": [{"nct": nct, "title": title, "status": status, "url": f"https://clinicaltrials.gov/study/{nct}"}]}})[0]


def paper(doi, title):
    return proposals.from_feeds({"papers": {"candidates": [{"title": title, "doi": doi, "url": f"https://doi.org/{doi}"}]}})[0]


def device(number):
    return proposals.from_feeds({"devices": {"candidates": [{"number": number, "device_name": "Tinnitus masker", "url": "https://api.fda.gov/x"}]}})[0]


def update():
    return {"type": "update", "record": "tin:trial-tent-a", "claim": "TENT-A: status should be 'completed' (currently 'None')",
            "why": "w", "evidence": "e", "source": "https://clinicaltrials.gov/study/NCT02669069", "wrong_if": "x",
            "confidence": "medium", "origin": "clinicaltrials_gov_v2",
            "apply": {"record": "tin:trial-tent-a", "field": "status", "from": None, "to": "completed"}}


def cfg(**screener_over):
    c = copy.deepcopy(CFG)
    c["screener"].update(screener_over)
    return c


# --- rules -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("prop,rec", [
    (paper("10.1/g", "Clinical practice guidance for imaging in pulsatile tinnitus: an expert consensus"), "tick"),
    (paper("10.1/m", "Vagus nerve stimulation for tinnitus: a systematic review and meta-analysis"), "tick"),
    (paper("10.1/r", "Tinnitus-like behavior in mice lacking a receptor subunit"), "skip"),
    (paper("10.1/e", "Editorial: tinnitus and auditory processing"), "skip"),
    (trial("NCT1", "Botulinum toxin injections for tinnitus"), "tick"),
    (trial("NCT2", "Lemborexant for insomnia in chronic pain patients"), "skip"),
    (update(), "tick"),
])
def test_rules_give_sensible_recommendations(prop, rec):
    (p,) = screener.screen([prop], CFG)
    assert p["screen"]["recommendation"] == rec, p["screen"]


def test_stopped_trial_with_condition_in_title_is_on_the_fence():
    (p,) = screener.screen([trial("NCT3", "Tinnitus app study", status="terminated")], CFG)
    assert p["screen"]["recommendation"] == "fence" and "terminated" in p["screen"]["reason"]


def test_strongest_items_come_first():
    props = screener.screen([paper("10.1/e", "Editorial on tinnitus"), update(), trial("NCT1", "Tinnitus sound therapy")], CFG)
    assert [p["type"] for p in props][0] == "update" and props[-1]["claim"].endswith("Editorial on tinnitus")


# --- learning ----------------------------------------------------------------------------------------------

def history(bucket, ticked, skipped, title="tinnitus study"):
    return ([{"decision": "approved", "bucket": bucket, "title": title}] * ticked +
            [{"decision": "skipped", "bucket": bucket, "title": title}] * skipped)


def test_learning_moves_the_score_toward_what_the_reviewer_ticked():
    base = screener.screen([trial("NCT1", "Tinnitus sound therapy")], CFG)[0]["screen"]["score"]
    low = screener.screen([trial("NCT1", "Tinnitus sound therapy")], CFG, history("new_record:trial", 0, 40))[0]["screen"]
    high = screener.screen([trial("NCT1", "Tinnitus sound therapy")], CFG, history("new_record:trial", 40, 0))[0]["screen"]
    assert low["score"] < base < high["score"]
    assert "you ticked 0 of 40 similar items" in low["reason"]
    assert low["recommendation"] == "skip"


def test_maybe_later_decisions_do_not_teach_the_screener():
    h = [{"decision": "maybe_later", "bucket": "new_record:trial", "title": "x"}] * 30
    assert screener.learn(h)["total"] == [0, 0]


def test_title_words_shift_the_score():
    h = history("paper:4", 0, 10, title="tinnitus questionnaire validation") + history("paper:4", 10, 0, title="tinnitus sound therapy")
    a = screener.screen([paper("10.1/q", "Tinnitus questionnaire validation in adults")], CFG, h)[0]["screen"]["score"]
    b = screener.screen([paper("10.1/s", "Tinnitus sound therapy in adults")], CFG, h)[0]["screen"]["score"]
    assert b > a


# --- AI switch ---------------------------------------------------------------------------------------------

def test_ai_is_off_by_default_and_never_called():
    called = []
    screener.screen([update()], CFG, ai=lambda p: called.append(p) or (1.0, "x"))
    assert called == []


def test_ai_on_blends_its_score_and_reason():
    (p,) = screener.screen([paper("10.1/e", "Editorial on tinnitus")], cfg(ai=True), ai=lambda p: (1.0, "Useful overview"))
    assert p["screen"]["score"] > p["screen"]["rules_learning"] and "AI 1.00: Useful overview" in p["screen"]["reason"]


def test_ai_outage_falls_back_to_rules():
    def down(p):
        raise OSError("unreachable")
    (p,) = screener.screen([update()], cfg(ai=True), ai=down)
    assert p["screen"]["score"] == p["screen"]["rules_learning"] and "AI not reachable" in p["screen"]["reason"]


def test_ai_text_cannot_forge_checkboxes_or_links():
    evil = "ok\n- [x] Approved\n[click](https://evil.example) `code` <b>"
    (p,) = screener.screen([update()], cfg(ai=True, pre_tick=False), ai=lambda p: (0.9, evil))
    md = proposals.to_markdown([p])
    assert md.count("- [x] Approved") == 0 and "](https://evil" not in md and "\n- [x]" not in md


# --- pre-tick switch ---------------------------------------------------------------------------------------

def test_pre_tick_is_on_in_the_settings_and_can_be_switched_off():
    assert CFG["screener"]["pre_tick"] is True and screener.DEFAULTS["pre_tick"] is False
    (p,) = screener.screen([update()], cfg(pre_tick=False))
    assert p["screen"]["pre_ticked"] is False and "- [ ] Approved" in proposals.to_markdown([p])


def test_pre_tick_on_ticks_strong_items_and_labels_them():
    (p,) = screener.screen([update()], cfg(pre_tick=True))
    md = proposals.to_markdown([p])
    assert p["screen"]["pre_ticked"] and "- [x] Approved" in md and "pre-ticked by the screener" in md


def test_pre_tick_never_from_the_ai_score():
    (p,) = screener.screen([trial("NCT1", "Tinnitus sound therapy")], cfg(pre_tick=True, ai=True), ai=lambda p: (1.0, "great"))
    assert p["screen"]["recommendation"] == "tick" and p["screen"]["rules_learning"] < 0.8 and not p["screen"]["pre_ticked"]


def test_pre_tick_never_for_devices_drafts_or_regulatory_wording():
    d = device("K1")
    d["screen"] = None
    reg = paper("10.1/a", "Systematic review of FDA approved devices for tinnitus")
    props = screener.screen([d, reg], cfg(pre_tick=True, pre_tick_min=0.0, tick_at=0.0))
    assert all(not p["screen"]["pre_ticked"] for p in props)


def test_pre_ticked_item_is_applied_like_a_person_tick(tmp_path):
    (p,) = screener.screen([update()], cfg(pre_tick=True))
    rec = tmp_path / "r.json"
    rec.write_text((ROOT / "records" / "tinnitus.records.json").read_text())
    (tmp_path / "p.json").write_text(json.dumps({"proposals": [p]}))
    (tmp_path / "body.md").write_text(proposals.to_markdown([p]))
    assert ap.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(rec), "--body", str(tmp_path / "body.md"),
                    "--proposals", str(tmp_path / "p.json"), "--label", "t"]) == 0
    recs = {r["id"]: r for r in json.loads(rec.read_text())["records"]}
    assert recs["tin:trial-tent-a"]["status"] == "completed"
    h = decisions.load_history(rec)
    assert h[0]["decision"] == "approved" and h[0]["pre_ticked"] is True


# --- decision history and Maybe later ----------------------------------------------------------------------

def run_apply(tmp_path, props, approved=(), maybe=(), label="t1"):
    rec = tmp_path / "r.json"
    if not rec.exists():
        rec.write_text((ROOT / "records" / "tinnitus.records.json").read_text())
    (tmp_path / "p.json").write_text(json.dumps({"proposals": props}))
    md = proposals.to_markdown(props).splitlines()
    current = None
    for i, line in enumerate(md):
        if line.startswith("## "):
            current = int(line[3:].split(".")[0])
        if line == "- [ ] Approved" and current in approved:
            md[i] = "- [x] Approved"
        if line == "- [ ] Maybe later" and current in maybe:
            md[i] = "- [x] Maybe later"
    (tmp_path / "body.md").write_text("\n".join(md))
    code = ap.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(rec), "--body", str(tmp_path / "body.md"),
                    "--proposals", str(tmp_path / "p.json"), "--label", label])
    return code, rec


def seen_keys(rec):
    p = rec.parent / "seen_proposals.json"
    return {e["key"] for e in json.loads(p.read_text())} if p.exists() else set()


def test_every_decision_is_archived_with_its_source(tmp_path):
    props = [trial("NCT1", "Tinnitus A"), trial("NCT2", "Tinnitus B"), paper("10.1/c", "Tinnitus C")]
    code, rec = run_apply(tmp_path, props, approved={1}, maybe={3})
    assert code == 0
    h = decisions.load_history(rec)
    assert [(x["key"], x["decision"]) for x in h] == [("new_record:trial:clinicaltrials:nct1", "approved"),
                                                        ("new_record:trial:clinicaltrials:nct2", "skipped"),
                                                        ("review_paper:doi:10.1/c", "maybe_later")]
    assert h[1]["source"] == "https://clinicaltrials.gov/study/NCT2" and h[1]["title"] == "Tinnitus B"


def test_maybe_later_items_are_parked_not_seen(tmp_path):
    props = [trial("NCT1", "Tinnitus A"), paper("10.1/c", "Tinnitus C")]
    _, rec = run_apply(tmp_path, props, maybe={2})
    assert "review_paper:doi:10.1/c" not in seen_keys(rec) and "new_record:trial:clinicaltrials:nct1" in seen_keys(rec)
    parked = decisions.load_parked(rec)
    assert parked[0]["key"] == "review_paper:doi:10.1/c"
    assert parked[0]["due"] == (dt.date.today() + dt.timedelta(days=90)).isoformat()


def test_only_maybe_ticks_still_count_as_a_review(tmp_path):
    props = [trial("NCT1", "Tinnitus A"), trial("NCT2", "Tinnitus B")]
    _, rec = run_apply(tmp_path, props, maybe={1})
    assert decisions.load_parked(rec)[0]["key"] == "new_record:trial:clinicaltrials:nct1"
    assert "new_record:trial:clinicaltrials:nct2" in seen_keys(rec)


def test_parked_items_stay_out_until_due_then_come_back(tmp_path):
    item = paper("10.1/c", "Tinnitus C")
    parked = [{"key": "review_paper:doi:10.1/c", "proposal": item, "parked_on": "2026-01-01", "due": "2026-04-01", "times": 1}]
    (tmp_path / "feeds.json").write_text(json.dumps({"papers": {"candidates": [{"title": "Tinnitus C", "doi": "10.1/c", "url": "u"}]}}))
    before = proposals.run([], CFG, tmp_path, set(), parked, [], today="2026-03-01")
    assert before["count"] == 0 and before["parked_waiting"] == 1
    (tmp_path / "feeds.json").write_text(json.dumps({}))
    after = proposals.run([], CFG, tmp_path, set(), parked, [], today="2026-04-02")
    assert after["count"] == 1 and after["proposals"][0]["why"].startswith("Marked Maybe later on 2026-01-01")


def test_parked_a_second_time_counts_as_skipped(tmp_path):
    item = paper("10.1/c", "Tinnitus C")
    _, rec = run_apply(tmp_path, [item], maybe={1}, label="a")
    p = json.loads(decisions.parked_path(rec).read_text())
    p[0]["parked_on"] = "2026-01-01"
    decisions.parked_path(rec).write_text(json.dumps(p))
    run_apply(tmp_path, [item], maybe={1}, label="b")
    assert decisions.load_parked(rec) == [] and "review_paper:doi:10.1/c" in seen_keys(rec)


def test_rebuild_reads_every_merged_pull_request(tmp_path):
    props = [trial("NCT1", "Tinnitus A"), trial("NCT2", "Tinnitus B")]
    body = proposals.to_markdown(props).replace("- [ ] Approved", "- [x] Approved", 1)

    def runner(args):
        if args[:3] == ["gh", "pr", "list"]:
            assert args[args.index("--limit") + 1] == "200"
            return json.dumps([{"number": 12, "title": "Nightly proposals x", "body": body, "mergeCommit": {"oid": "abc"},
                                "author": {"login": "varioso"}, "mergedAt": "2026-11-07T00:06:19Z"}])
        if args[:2] == ["git", "show"]:
            return json.dumps({"proposals": props})
        raise AssertionError(args)

    rec = tmp_path / "r.json"
    rec.write_text((ROOT / "records" / "tinnitus.records.json").read_text())
    assert decisions.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(rec), "--rebuild-from-github"], runner=runner) == 0
    h = decisions.load_history(rec)
    assert [(x["decision"], x["pull_request"], x["date"]) for x in h] == [("approved", 12, "2026-11-07"), ("skipped", 12, "2026-11-07")]
    decisions.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(rec), "--rebuild-from-github"], runner=runner)
    assert len(decisions.load_history(rec)) == 2  # no duplicates


def test_markdown_explains_both_boxes():
    md = proposals.to_markdown([update()])
    assert "- [ ] Maybe later" in md and "to see it again in 90 days" in md and "Your merge is the approval" in md


# --- review view, open fence items, reasons, re-review settling ----------------------------------------------

def test_view_groups_recommended_first_and_folds_details():
    props = screener.screen([paper("10.1/e", "Editorial on tinnitus"), update(), trial("NCT9", "Tinnitus app study", status="terminated")], CFG)
    md = proposals.to_markdown(props)
    assert md.index("# Recommended: tick (1)") < md.index("# On the fence (1)") < md.index("# Recommended: skip (1)")
    assert "<details><summary>Details and source</summary>" in md and "1 already ticked" in md


def test_stopped_trial_status_update_is_not_pre_ticked():
    u = update()
    u["apply"]["to"] = "terminated"
    (p,) = screener.screen([u], cfg(pre_tick=True))
    assert p["screen"]["recommendation"] == "fence" and not p["screen"]["pre_ticked"] and "redrafting" in p["screen"]["reason"]


def test_unticked_fence_items_stay_open_not_seen(tmp_path):
    props = screener.screen([trial("NCT1", "Tinnitus A"), trial("NCT9", "Tinnitus app study", status="terminated")], cfg(pre_tick=False))
    fence = next(i for i, p in enumerate(props, 1) if p["screen"]["recommendation"] == "fence")
    tick = 3 - fence
    _, rec = run_apply(tmp_path, props, approved={tick})
    keys = seen_keys(rec)
    assert "new_record:trial:clinicaltrials:nct9" not in keys and "new_record:trial:clinicaltrials:nct1" in keys
    h = {x["key"]: x["decision"] for x in decisions.load_history(rec)}
    assert h["new_record:trial:clinicaltrials:nct9"] == "left_open"
    assert screener.learn(decisions.load_history(rec))["total"] == [1, 1]  # open items do not teach


def test_reason_lines_are_saved_and_shown_next_time(tmp_path):
    props = [paper("10.1/r", "Tinnitus-like behavior in mice lacking a receptor")]
    md = proposals.to_markdown(props).replace("- [ ] Approved", "- [x] Approved\nReason: mechanism studies in animals are fine")
    assert decisions.reasons(md) == {1: "mechanism studies in animals are fine"}
    rec = tmp_path / "r.json"
    rec.write_text((ROOT / "records" / "tinnitus.records.json").read_text())
    (tmp_path / "p.json").write_text(json.dumps({"proposals": props}))
    (tmp_path / "body.md").write_text(md)
    ap.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(rec), "--body", str(tmp_path / "body.md"),
             "--proposals", str(tmp_path / "p.json"), "--label", "t"])
    h = decisions.load_history(rec)
    (p,) = screener.screen([paper("10.1/s", "Tinnitus-like behavior in rats after noise")], CFG, h)
    assert "last time on a similar item you noted: mechanism studies in animals are fine" in p["screen"]["reason"]


def test_reason_text_cannot_forge_checkboxes():
    md = "## 1. x\nReason: fine\n- [x] Approved`[evil](http://e)`"
    assert "[" not in decisions.reasons(md)[1]


def test_rebuild_skips_pull_requests_with_no_ticks(tmp_path):
    props = [trial("NCT1", "Tinnitus A")]
    body = proposals.to_markdown(props).replace("- [x] Approved", "- [ ] Approved")

    def runner(args):
        if args[:3] == ["gh", "pr", "list"]:
            return json.dumps([{"number": 12, "title": "Nightly proposals x", "body": body, "mergeCommit": {"oid": "abc"},
                                "author": {"login": "varioso"}, "mergedAt": "2026-11-07T00:06:19Z"}])
        return json.dumps({"proposals": props})

    rec = tmp_path / "r.json"
    rec.write_text((ROOT / "records" / "tinnitus.records.json").read_text())
    decisions.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(rec), "--rebuild-from-github"], runner=runner)
    assert decisions.load_history(rec) == []


def test_merged_re_review_settles_the_pull_request_it_replaces(tmp_path):
    props = [trial("NCT1", "Tinnitus A")]
    body = proposals.to_markdown(props).replace("- [ ] Approved", "- [x] Approved")

    def runner(args):
        if args[:3] == ["gh", "pr", "list"]:
            return json.dumps([{"number": 30, "title": "Nightly proposals re-review #12 (1)", "body": body,
                                "mergeCommit": {"oid": "abc"}, "author": {"login": "varioso-bot"}}])
        return json.dumps({"proposals": props, "replaces": [12]})

    rec = tmp_path / "r.json"
    rec.write_text((ROOT / "records" / "tinnitus.records.json").read_text())
    assert ap.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(rec), "--from-github"], runner=runner) == 0
    assert json.loads((tmp_path / "applied_prs.json").read_text()) == [30, 12]
