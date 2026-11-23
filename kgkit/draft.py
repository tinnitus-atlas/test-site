"""Drafting step: turn bare entries (created from a registry feed) into finished ones, behind an automatic gate.

A bare entry still carries the placeholder TL;DR "Draft record from a registry feed; summary still to be written."
For each one (trials and devices, up to --cap per run) this command:
  1. fetches the source text (the trial's registry description, or the FDA record) and stores its hash;
  2. asks the drafter (any OpenAI-compatible chat endpoint, set by environment variables) for a TL;DR, a summary
     and 1 to 3 relationships, each with a quote of fewer than 15 words copied from the source text;
  3. runs the gate: lengths, banned phrases, allowed predicates, existing objects, every quote word for word in
     the source text, and the audit rules (including the regulatory-wording rule);
  4. on failure gives the reasons back to the drafter once; a second failure goes to records/draft_queue.json;
  5. writes every passing draft as a proposal of type "draft" in the nightly format, so a person ticks it in the
     proposals pull request and the existing apply step writes it. Nothing is written to the records here.

Review mode (configuration drafting.review_mode): only "person" is available. "sampled" (automatic merge of
tier A drafts) is refused, because model-written changes never merge by themselves (untrusted-text rule).
Tier B (always a person, and flagged in the proposal): devices, regulatory wording, claims that a treatment
helps or harms.

Drafter settings (environment): DRAFTER_BASE_URL (for example https://openrouter.ai/api/v1 or a local server),
DRAFTER_MODEL, DRAFTER_API_KEY (optional for local servers). Never stored in the repository.

Usage:
  python3 -m kgkit.draft --config kit.yaml --records records/x.json --reports reports [--cap 20] [--dry-run]
Exit codes: 0 done; 2 bad input or no drafter configured.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable

from . import audit, feeds, proposals
from .common import FetchError, Http, KitError, load_config, load_records, normalise, qs, write_report

PLACEHOLDER = "Draft record from a registry feed; summary still to be written."
PROMPT_FILE = Path(__file__).resolve().parents[1] / "prompts" / "draft_v1.md"
PROMPT_VERSION = "draft_v1"
DEFAULTS = {
    "review_mode": "person",
    "cap": 20,
    "allowed_predicates": ["studies_condition", "in_trials_for", "studied_to_treat", "related_to"],
    "banned_phrases": ["cure", "cures", "cured", "proven to", "guaranteed", "miracle", "breakthrough", "you should"],
    "claim_predicates": ["treats", "ameliorates", "causes", "side_effect", "adverse_event", "contributes_to"],
}

Drafter = Callable[[list[dict]], str]


def settings(cfg: dict) -> dict:
    return {**DEFAULTS, **(cfg.get("drafting") or {})}


def is_bare(r: dict) -> bool:
    return r.get("kind") in ("trial", "device") and (r.get("tldr") or "").strip() == PLACEHOLDER


# --- source text --------------------------------------------------------------------------------------------

def nct_of(r: dict) -> str | None:
    for x in r.get("xrefs") or []:
        if str(x).upper().startswith("CLINICALTRIALS:"):
            return str(x).split(":", 1)[1].upper()
    return None


def trial_source(r: dict, http: Http) -> tuple[str, str] | None:
    nct = nct_of(r)
    if not nct:
        return None
    data = http.get_json(f"{feeds.CTGOV}/{nct}?{qs({'format': 'json'})}") or {}
    p = data.get("protocolSection") or {}
    ident, desc = p.get("identificationModule") or {}, p.get("descriptionModule") or {}
    conds = (p.get("conditionsModule") or {}).get("conditions") or []
    arms = (p.get("armsInterventionsModule") or {}).get("interventions") or []
    outcomes = (p.get("outcomesModule") or {}).get("primaryOutcomes") or []
    parts = [ident.get("briefTitle"), ident.get("officialTitle"), desc.get("briefSummary"),
             "Conditions: " + ", ".join(conds) if conds else None,
             *[f"Intervention: {a.get('name')}. {a.get('description') or ''}" for a in arms],
             *[f"Primary outcome: {o.get('measure')}. {o.get('description') or ''}" for o in outcomes]]
    text = "\n".join(x.strip() for x in parts if x and x.strip())
    return (text, f"https://clinicaltrials.gov/study/{nct}") if text else None


def device_source(r: dict, http: Http) -> tuple[str, str] | None:
    fact = (r.get("facts") or {}).get("fda_submission_number")
    number = fact.get("value") if isinstance(fact, dict) else fact
    if not number:
        return None
    url = f"{feeds.OPENFDA}/510k.json?{qs({'search': f'k_number:{number}'})}"
    rows = feeds._openfda(http, "510k", {"search": f"k_number:{number}"})
    if not rows:
        return None
    row = rows[0]
    fields = [("Device", "device_name"), ("Applicant", "applicant"), ("Decision", "decision_description"),
              ("Decision date", "decision_date"), ("Product code", "product_code"), ("Summary", "statement_or_summary")]
    text = "\n".join(f"{label}: {row[k]}" for label, k in fields if row.get(k))
    return (text, url) if text else None


def source_text(r: dict, http: Http) -> tuple[str, str] | None:
    return trial_source(r, http) if r["kind"] == "trial" else device_source(r, http)


# --- drafter ------------------------------------------------------------------------------------------------

def openai_compatible() -> Drafter | None:
    base, model = os.environ.get("DRAFTER_BASE_URL"), os.environ.get("DRAFTER_MODEL")
    if not (base and model):
        return None
    key = os.environ.get("DRAFTER_API_KEY")

    def call(messages: list[dict]) -> str:
        body = json.dumps({"model": model, "messages": messages, "temperature": 0,
                           "response_format": {"type": "json_object"}}).encode()
        headers = {"Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})}
        req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())["choices"][0]["message"]["content"]
    call.model = model  # type: ignore[attr-defined]
    return call


def prompt(record: dict, records: list[dict], text: str, allowed: list[str]) -> str:
    targets = "\n".join(f"- {r['id']}: {r.get('name')} ({r.get('kind')})" for r in records if r["id"] != record["id"])
    return (PROMPT_FILE.read_text(encoding="utf-8")
            .replace("{name}", str(record.get("name"))).replace("{kind}", str(record.get("kind")))
            .replace("{predicates}", ", ".join(allowed)).replace("{records}", targets).replace("{source}", text))


def parse(raw: str) -> dict:
    raw = (raw or "").strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("the answer is not JSON")
    d = json.loads(m.group(0))
    if not isinstance(d, dict):
        raise ValueError("the answer is not a JSON object")
    return d


# --- gate ---------------------------------------------------------------------------------------------------

def words(s: str) -> int:
    return len(re.findall(r"\S+", s or ""))


def gate(d: dict, record: dict, text: str, records: list[dict], cfg: dict) -> list[str]:
    st = settings(cfg)
    reasons = []
    tldr, summary, rels = d.get("tldr"), d.get("summary"), d.get("relations")
    if not isinstance(tldr, str) or not tldr.strip():
        reasons.append("tldr is missing")
    elif words(tldr) > 30:
        reasons.append(f"tldr has {words(tldr)} words; at most 30")
    if not isinstance(summary, str) or not summary.strip():
        reasons.append("summary is missing")
    elif not 60 <= words(summary) <= 120:
        reasons.append(f"summary has {words(summary)} words; it must have 60 to 120")
    joined = f" {normalise((tldr or '') + ' ' + (summary or ''))} "
    for phrase in st["banned_phrases"]:
        if re.search(r"\b" + re.escape(phrase.lower()) + r"\b", joined):
            reasons.append(f"banned phrase '{phrase}'")
    ids = {r["id"] for r in records}
    allowed = set(st["allowed_predicates"]) & set(cfg.get("predicates") or {})
    if not isinstance(rels, list) or not 1 <= len(rels) <= 3:
        reasons.append("relations must be a list of 1 to 3 items")
        rels = rels if isinstance(rels, list) else []
    source = normalise(text)
    for i, rel in enumerate(rels):
        rel = rel if isinstance(rel, dict) else {}
        if rel.get("predicate") not in allowed:
            reasons.append(f"relation {i + 1}: predicate '{rel.get('predicate')}' is not allowed")
        if rel.get("object") not in ids or rel.get("object") == record["id"]:
            reasons.append(f"relation {i + 1}: object '{rel.get('object')}' is not an existing record")
        q = rel.get("quote")
        if not isinstance(q, str) or not q.strip():
            reasons.append(f"relation {i + 1}: quote is missing")
        elif words(q) >= 15:
            reasons.append(f"relation {i + 1}: quote has {words(q)} words; fewer than 15")
        elif normalise(q).strip(" .\"'") not in source:
            reasons.append(f"relation {i + 1}: quote is not word for word in the source text")
    if not reasons:
        candidate = finished(record, d, "gate", "-", today_iso(), url_hint=None)
        others = [r for r in records if r["id"] != record["id"]]
        with tempfile.TemporaryDirectory() as tmp:
            res = audit.run(others + [candidate], cfg, tmp)
        for issue in res.get("issues") or []:
            if issue["record"] == record["id"] and issue["blocking"]:
                reasons.append(f"audit: {issue['message']}")
    return reasons


def today_iso() -> str:
    return dt.date.today().isoformat()


def finished(record: dict, d: dict, model: str, source_hash: str, day: str, url_hint: str | None) -> dict:
    rec = copy.deepcopy(record)
    rec["tldr"], rec["summary"] = d["tldr"].strip(), d["summary"].strip()
    rec["asOf"] = day
    url = url_hint or next((s.get("url") for s in rec.get("sources") or [] if s.get("url")), None)
    for rel in d.get("relations") or []:
        rec.setdefault("relations", []).append({
            "predicate": rel["predicate"], "object": rel["object"], "quote": rel["quote"].strip(),
            **({"sourceUrl": url} if url else {}),
            "knowledgeLevel": "knowledge_assertion", "agentType": "automated_agent"})
    rec["provenance"] = {"drafted_by": model, "prompt": PROMPT_VERSION, "drafted_on": day, "source_hash": source_hash}
    return rec


def tier(record: dict, d: dict, cfg: dict) -> str:
    st = settings(cfg)
    terms = ((cfg.get("regulatory") or {}).get("claim_terms") or [])
    text = normalise(f"{d.get('tldr', '')} {d.get('summary', '')}")
    if record["kind"] == "device":
        return "B"
    if any(re.search(r"\b" + re.escape(t.lower()) + r"\b", text) for t in terms):
        return "B"
    if any((r or {}).get("predicate") in st["claim_predicates"] for r in d.get("relations") or []):
        return "B"
    return "A"


# --- run ----------------------------------------------------------------------------------------------------

def to_proposal(record: dict, d: dict, url: str, model: str, h: str, t: str) -> dict:
    quotes = "; ".join(f"{r['predicate']} {r['object']}: \"{r['quote']}\"" for r in d["relations"])
    return {
        "type": "draft", "record": record["id"],
        "claim": f"Finish entry {record['id']}: {record.get('name')}",
        "why": "The drafting step wrote a summary and sourced links from the source text; the automatic checks passed"
               + (" (tier B: a person must read it closely)" if t == "B" else ""),
        "evidence": f"TL;DR: {d['tldr']} Summary: {d['summary']} Quotes: {quotes}",
        "source": url,
        "wrong_if": "a sentence says something the source does not say, or a quote is cut in a way that changes its meaning",
        "confidence": "medium",
        "apply": {"record": record["id"], "expect_tldr": PLACEHOLDER, "tldr": d["tldr"], "summary": d["summary"],
                  "relations": d["relations"], "source_url": url,
                  "provenance": {"drafted_by": model, "prompt": PROMPT_VERSION, "drafted_on": today_iso(), "source_hash": h}},
        "origin": "drafting_step", "tier": t, "auto_apply": False,
    }


def run(records: list[dict], cfg: dict, http: Http, drafter: Drafter, model: str, reports_dir, queue_path: Path,
        cap: int) -> dict:
    st = settings(cfg)
    if st["review_mode"] != "person":
        raise KitError("drafting.review_mode 'sampled' is not available: model-written changes never merge by "
                       "themselves (untrusted-text rule). Use 'person'.")
    queue = json.loads(queue_path.read_text()) if queue_path.exists() else []
    queued_ids = {q["record"] for q in queue}
    allowed = [p for p in st["allowed_predicates"] if p in (cfg.get("predicates") or {})]
    props, report = [], {"drafted": [], "queued": [], "skipped_queued_before": []}
    bare = [r for r in records if is_bare(r)]
    for r in bare[:cap]:
        if r["id"] in queued_ids:
            report["skipped_queued_before"].append(r["id"])
            continue
        try:
            src = source_text(r, http)
        except FetchError as exc:
            src, err = None, f"source unreachable: {exc}"
        else:
            err = "no usable source text"
        if not src:
            queue.append({"record": r["id"], "reasons": [err], "on": today_iso()})
            report["queued"].append({"record": r["id"], "reasons": [err]})
            continue
        text, url = src
        h = hashlib.sha256(text.encode()).hexdigest()
        messages = [{"role": "user", "content": prompt(r, records, text, allowed)}]
        reasons: list[str] = []
        d: dict = {}
        for attempt in range(2):
            try:
                d = parse(drafter(messages))
                reasons = gate(d, r, text, records, cfg)
            except (ValueError, json.JSONDecodeError) as exc:
                reasons = [f"answer could not be read: {exc}"]
            except Exception as exc:  # noqa: BLE001 - a drafter outage must not stop the run
                reasons = [f"drafter error: {exc}"]
                break
            if not reasons:
                break
            messages = messages + [{"role": "assistant", "content": json.dumps(d) if d else ""},
                                   {"role": "user", "content": "The draft failed these checks; fix them and answer with JSON only:\n- "
                                    + "\n- ".join(reasons)}]
        if reasons:
            queue.append({"record": r["id"], "reasons": reasons, "on": today_iso()})
            report["queued"].append({"record": r["id"], "reasons": reasons})
            continue
        t = tier(r, d, cfg)
        props.append(to_proposal(r, d, url, model, h, t))
        report["drafted"].append({"record": r["id"], "tier": t})
    reports = Path(reports_dir)
    reports.mkdir(parents=True, exist_ok=True)
    write_report(reports, "proposals", {"check": "proposals", "mode": "drafts", "count": len(props), "auto_apply": 0,
                                        "already_reviewed_skipped": 0, "proposals": props})
    (reports / "proposals.md").write_text(proposals.to_markdown(props), encoding="utf-8")
    queue_path.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report.update({"bare": len(bare), "cap": cap, "model": model})
    lines = [f"# Drafting run {today_iso()}", "",
             f"Bare entries: {len(bare)} (cap per run {cap})",
             f"Drafted and passed the gate: {len(report['drafted'])} "
             f"(tier A {sum(1 for x in report['drafted'] if x['tier'] == 'A')}, tier B {sum(1 for x in report['drafted'] if x['tier'] == 'B')})",
             f"Queued with reasons: {len(report['queued'])}"]
    for q in report["queued"]:
        lines.append(f"- {q['record']}: " + "; ".join(q["reasons"]))
    (reports / "draft_run.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_report(reports, "draft_run", report)
    return report


def main(argv: list[str] | None = None, drafter: Drafter | None = None, http: Http | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kgkit.draft", description="Draft finished entries for bare records")
    ap.add_argument("--config", required=True)
    ap.add_argument("--records", required=True)
    ap.add_argument("--reports", default="reports")
    ap.add_argument("--cap", type=int)
    ap.add_argument("--cache", default=".cache/http")
    args = ap.parse_args(argv)
    try:
        cfg = load_config(args.config)
        records = load_records(args.records)
    except KitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    drafter = drafter or openai_compatible()
    if drafter is None:
        print("error: no drafter configured; set DRAFTER_BASE_URL and DRAFTER_MODEL", file=sys.stderr)
        return 2
    model = getattr(drafter, "model", "stand-in")
    queue_path = Path(args.records).parent / "draft_queue.json"
    try:
        run(records, cfg, http or Http(cache_dir=args.cache), drafter, model, args.reports, queue_path,
            args.cap if args.cap is not None else int(settings(cfg)["cap"]))
    except KitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print((Path(args.reports) / "draft_run.md").read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
