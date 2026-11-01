"""Fact-check records against public registries. Never edits a record; mismatches feed the proposals check.

Supported registry: ClinicalTrials.gov API v2 (source: clinicaltrials_gov_v2). A trial record names its
registry entry with an xref such as CLINICALTRIALS:NCT01234567 and may hold these comparable values:
  status                         recruitment status, lower snake case (recruiting, completed, ...)
  facts.phase                    e.g. phase2, phase2/phase3, na
  facts.primary_completion_date  YYYY-MM or YYYY-MM-DD
  facts.enrollment               integer
Severity: high = the record states something the registry contradicts; medium = a stale or mismatched
value; low = the record is missing a value the registry has.
"""
from __future__ import annotations

from .common import FetchError, Http, fact_value, parse_date, today, write_report

CTGOV = "https://clinicaltrials.gov/api/v2/studies"
FIELDS = ",".join([
    "protocolSection.identificationModule.briefTitle",
    "protocolSection.statusModule.overallStatus",
    "protocolSection.statusModule.whyStopped",
    "protocolSection.statusModule.primaryCompletionDateStruct",
    "protocolSection.statusModule.lastUpdatePostDateStruct",
    "protocolSection.designModule.phases",
    "protocolSection.designModule.enrollmentInfo",
])
OPEN = {"recruiting", "not_yet_recruiting", "enrolling_by_invitation", "active_not_recruiting"}


def nct_of(record: dict, prefix: str = "CLINICALTRIALS") -> str | None:
    for x in record.get("xrefs") or []:
        if x.upper().startswith(prefix.upper() + ":"):
            return x.split(":", 1)[1].strip().upper()
    return None


def registry_url(nct: str) -> str:
    return f"https://clinicaltrials.gov/study/{nct}"


def parse_study(data: dict) -> dict:
    ps = (data or {}).get("protocolSection") or {}
    st, des = ps.get("statusModule") or {}, ps.get("designModule") or {}
    phases = des.get("phases") or []
    return {
        "title": (ps.get("identificationModule") or {}).get("briefTitle"),
        "status": (st.get("overallStatus") or "UNKNOWN").lower(),
        "why_stopped": st.get("whyStopped"),
        "primary_completion_date": (st.get("primaryCompletionDateStruct") or {}).get("date"),
        "primary_completion_type": (st.get("primaryCompletionDateStruct") or {}).get("type"),
        "last_update": (st.get("lastUpdatePostDateStruct") or {}).get("date"),
        "phase": "/".join(p.lower() for p in phases) if phases else None,
        "enrollment": (des.get("enrollmentInfo") or {}).get("count"),
        "enrollment_type": (des.get("enrollmentInfo") or {}).get("type"),
    }


def compare(record: dict, reg: dict, url: str, now) -> tuple[list, list]:
    findings, patches = [], []

    def add(field, current, proposed, severity, reason):
        findings.append({"record": record["id"], "name": record.get("name"), "field": field, "recorded": current,
                         "registry": proposed, "severity": severity, "reason": reason, "source": url})
        patches.append({"record": record["id"], "field": field, "current": current, "proposed": proposed,
                        "reason": reason, "source": url, "severity": severity})

    status = record.get("status")
    if status is None:
        add("status", None, reg["status"], "low", "Record has no status; registry has one")
    elif status != reg["status"]:
        sev = "high" if (status in OPEN) != (reg["status"] in OPEN) else "medium"
        why = f" ({reg['why_stopped'][:120]})" if reg.get("why_stopped") else ""
        add("status", status, reg["status"], sev, f"ClinicalTrials.gov overall status is {reg['status']}{why}")

    phase = fact_value(record, "phase")
    if reg["phase"] and phase is None:
        add("facts.phase", None, reg["phase"], "low", "Record has no phase; registry has one")
    elif reg["phase"] and phase != reg["phase"]:
        add("facts.phase", phase, reg["phase"], "medium", f"ClinicalTrials.gov lists phase {reg['phase']}")

    pcd = fact_value(record, "primary_completion_date")
    if reg["primary_completion_date"] and pcd != reg["primary_completion_date"]:
        sev = "low" if pcd is None else "medium"
        add("facts.primary_completion_date", pcd, reg["primary_completion_date"], sev,
            f"Registry primary completion date is {reg['primary_completion_date']} ({reg.get('primary_completion_type') or 'type not given'})")

    enrol = fact_value(record, "enrollment")
    if reg["enrollment"] is not None and enrol != reg["enrollment"]:
        sev = "low" if enrol is None else "medium"
        add("facts.enrollment", enrol, reg["enrollment"], sev,
            f"Registry enrolment is {reg['enrollment']} ({reg.get('enrollment_type') or 'type not given'})")

    done = parse_date(reg["primary_completion_date"])
    if status in OPEN and reg["status"] in OPEN and done and done < now:
        findings.append({"record": record["id"], "name": record.get("name"), "field": "status", "recorded": status,
                         "registry": reg["status"], "severity": "medium", "source": url,
                         "reason": "Primary completion date has passed but the trial is still listed as open"})
    return findings, patches


def run(records: list[dict], cfg: dict, http: Http, reports_dir) -> dict:
    now = today()
    registries = [r for r in cfg.get("registries") or [] if r.get("enabled", True)]
    findings, patches, checked, unreachable, skipped = [], [], 0, [], []
    for reg_cfg in registries:
        if reg_cfg.get("source") != "clinicaltrials_gov_v2":
            skipped.append({"source": reg_cfg.get("source"), "reason": "registry not supported in this version"})
            continue
        for rec in records:
            if rec.get("kind") != reg_cfg.get("kind"):
                continue
            nct = nct_of(rec, reg_cfg.get("id_prefix", "CLINICALTRIALS"))
            if not nct:
                skipped.append({"record": rec["id"], "reason": "no registry identifier in xrefs"})
                continue
            try:
                data = http.get_json(f"{CTGOV}/{nct}?fields={FIELDS}")
            except FetchError as exc:
                unreachable.append({"record": rec["id"], "nct": nct, "error": str(exc)})
                continue
            checked += 1
            f, p = compare(rec, parse_study(data), registry_url(nct), now)
            findings += f
            patches += p
    report = {"check": "factcheck", "checked": checked, "findings": findings, "patches": patches,
              "unreachable": unreachable, "skipped": skipped,
              "counts": {s: sum(1 for f in findings if f["severity"] == s) for s in ("high", "medium", "low")}}
    write_report(reports_dir, "factcheck", report)
    return report
