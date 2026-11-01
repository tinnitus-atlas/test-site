"""Tests for export_biolink.py. Run: BIOLINK_DIR=/path/to/biolink-model pytest -q tests"""
import copy
import json
import os
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import export_biolink as ex  # noqa: E402

BIOLINK_DIR = os.environ.get("BIOLINK_DIR")
pytestmark = pytest.mark.skipif(not BIOLINK_DIR, reason="set BIOLINK_DIR to a Biolink model checkout")
CONFIG = ROOT / "kit.tinnitus.yaml"
RECORDS = ROOT / "examples" / "records.example.json"


def run(tmp_path, records=None, config=None, extra=()):
    rec_path, cfg_path = RECORDS, CONFIG
    if records is not None:
        rec_path = tmp_path / "records.json"
        rec_path.write_text(json.dumps(records) if not isinstance(records, str) else records)
    if config is not None:
        cfg_path = tmp_path / "kit.yaml"
        cfg_path.write_text(yaml.safe_dump(config))
    out = tmp_path / "out"
    code = ex.main(["--config", str(cfg_path), "--records", str(rec_path), "--out", str(out),
                    "--biolink-dir", BIOLINK_DIR, *extra])
    report = json.loads((out / "export_report.json").read_text()) if (out / "export_report.json").exists() else None
    return code, out, report


def jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def base_records():
    return json.loads(RECORDS.read_text())


def base_config():
    return yaml.safe_load(CONFIG.read_text())


# --- happy path -------------------------------------------------------------

def test_example_exports_and_core_passes(tmp_path):
    code, out, report = run(tmp_path)
    assert code == 0
    assert report["precheck"]["core"]["errors"] == []
    assert report["counts"]["core"] == {"nodes": 5, "edges": 4}


def test_standard_identifier_replaces_project_id_and_is_kept_as_xref(tmp_path):
    _, out, _ = run(tmp_path)
    nodes = {n["id"]: n for n in jsonl(out / "core_nodes.jsonl")}
    assert "HP:0000360" in nodes
    assert "tin:tinnitus" in nodes["HP:0000360"]["xref"]
    assert nodes["HP:0000360"]["category"] == ["biolink:PhenotypicFeature"]


def test_edges_use_remapped_ids_and_biolink_predicates(tmp_path):
    _, out, _ = run(tmp_path)
    edges = jsonl(out / "core_edges.jsonl")
    assert all(e["object"] == "HP:0000360" for e in edges)
    assert {"biolink:in_clinical_trials_for", "biolink:ameliorates_condition"} <= {e["predicate"] for e in edges}
    for e in edges:
        for prop in ex.REQUIRED_EDGE_PROPS:
            assert e[prop]


def test_provenance_and_quote_are_carried(tmp_path):
    _, out, _ = run(tmp_path)
    e = next(e for e in jsonl(out / "core_edges.jsonl") if e["predicate"] == "biolink:ameliorates_condition")
    assert e["agent_type"] == "manual_validation_of_automated_agent"
    assert e["publications"] == ["PMID:00000000"] and e["supporting_text"] == ["EXAMPLE quote."]


def test_non_exported_kind_and_dangling_reference_are_reported(tmp_path):
    _, _, report = run(tmp_path)
    assert any(s["id"] == "tin:open-question-1" for s in report["skipped_records"])
    assert any("dangling" in s["reason"] for s in report["skipped_relations"])


def test_project_namespace_nodes_stay_out_of_core_but_in_full(tmp_path):
    _, out, report = run(tmp_path)
    core = {n["id"] for n in jsonl(out / "core_nodes.jsonl")}
    full = {n["id"] for n in jsonl(out / "full_nodes.jsonl")}
    assert "tin:example-mechanism" not in core and "tin:example-mechanism" in full
    assert any("prefix 'tin'" in e for e in report["precheck"]["full"]["errors"])


def test_output_is_deterministic(tmp_path):
    _, out1, _ = run(tmp_path / "a")
    _, out2, _ = run(tmp_path / "b")
    for name in ("core_nodes.jsonl", "core_edges.jsonl", "full_nodes.jsonl", "full_edges.jsonl"):
        assert (out1 / name).read_text() == (out2 / name).read_text()


def test_tsv_format(tmp_path):
    code, out, _ = run(tmp_path, extra=("--format", "tsv"))
    assert code == 0
    header = (out / "core_nodes.tsv").read_text().splitlines()[0].split("\t")
    assert header[:3] == ["id", "category", "name"]


def test_no_precheck_flag_skips_precheck(tmp_path):
    code, _, report = run(tmp_path, extra=("--no-precheck",))
    assert code == 0 and "precheck" not in report


# --- precheck catches what KGX would reject ----------------------------------

@pytest.mark.parametrize("category,needle", [
    ("biolink:NotThing", "not in Biolink"),
    ("biolink:NotAThing", "CamelCase"),  # KGX's CamelCase rule rejects a single-letter word too
    ("biolink:ChemicalOrDrugOrTreatment", "mixin"),
    ("biolink:phenotypic_feature", "CamelCase"),
])
def test_bad_categories_fail_core(tmp_path, category, needle):
    cfg = base_config()
    cfg["kinds"]["condition"]["category"] = [category]
    code, _, report = run(tmp_path, config=cfg)
    assert code == 1
    assert any(needle in e for e in report["precheck"]["core"]["errors"])


def test_unknown_biolink_predicate_fails(tmp_path):
    cfg = base_config()
    cfg["predicates"]["ameliorates"] = "biolink:cures_everything"
    code, _, report = run(tmp_path, config=cfg)
    assert code == 1 and any("cures_everything" in e for e in report["precheck"]["core"]["errors"])


def test_bad_knowledge_level_fails(tmp_path):
    recs = base_records()
    recs["records"][3]["relations"][0]["knowledgeLevel"] = "very_sure"
    code, _, report = run(tmp_path, records=recs)
    assert code == 1 and any("knowledge_level" in e for e in report["precheck"]["core"]["errors"])


def test_domain_warning_when_procedure_used_as_treatment(tmp_path):
    cfg = base_config()
    cfg["kinds"]["intervention"]["category"] = ["biolink:Procedure"]
    code, _, report = run(tmp_path, config=cfg)
    assert code == 0
    assert any("subject to be a 'chemical or drug or treatment'" in w for w in report["precheck"]["core"]["warnings"])


def test_record_level_category_override(tmp_path):
    recs = base_records()
    recs["records"][0]["category"] = ["biolink:Disease"]
    _, out, _ = run(tmp_path, records=recs)
    nodes = {n["id"]: n for n in jsonl(out / "core_nodes.jsonl")}
    assert nodes["HP:0000360"]["category"] == ["biolink:Disease"]


def test_two_records_with_same_standard_id_do_not_merge(tmp_path):
    recs = base_records()
    clone = copy.deepcopy(recs["records"][1])
    clone["id"], clone["xrefs"] = "tin:another", ["HP:0000360"]
    recs["records"].append(clone)
    code, out, report = run(tmp_path, records=recs)
    full = {n["id"] for n in jsonl(out / "full_nodes.jsonl")}
    assert "HP:0000360" in full and "tin:another" in full
    assert report["id_collisions"][0]["records"] == ["tin:tinnitus", "tin:another"]


# --- bad input exits 2 with a message ----------------------------------------

def test_unknown_kind(tmp_path, capsys):
    recs = base_records()
    recs["records"][0]["kind"] = "planet"
    code, _, _ = run(tmp_path, records=recs)
    assert code == 2 and "planet" in capsys.readouterr().err


def test_unknown_project_predicate(tmp_path, capsys):
    recs = base_records()
    recs["records"][1]["relations"][0]["predicate"] = "is_friends_with"
    code, _, _ = run(tmp_path, records=recs)
    assert code == 2 and "is_friends_with" in capsys.readouterr().err


def test_duplicate_id(tmp_path, capsys):
    recs = base_records()
    recs["records"].append(copy.deepcopy(recs["records"][0]))
    code, _, _ = run(tmp_path, records=recs)
    assert code == 2 and "Duplicate" in capsys.readouterr().err


def test_missing_required_field(tmp_path, capsys):
    recs = base_records()
    del recs["records"][0]["name"]
    code, _, _ = run(tmp_path, records=recs)
    assert code == 2 and "missing 'name'" in capsys.readouterr().err


def test_invalid_json(tmp_path, capsys):
    code, _, _ = run(tmp_path, records="{not json")
    assert code == 2 and "not valid JSON" in capsys.readouterr().err


def test_missing_records_file(tmp_path, capsys):
    code = ex.main(["--config", str(CONFIG), "--records", str(tmp_path / "nope.json"),
                    "--out", str(tmp_path / "o"), "--biolink-dir", BIOLINK_DIR])
    assert code == 2 and "not found" in capsys.readouterr().err


def test_version_mismatch(tmp_path, capsys):
    cfg = base_config()
    cfg["biolink"]["version"] = "9.9.9"
    code, _, _ = run(tmp_path, config=cfg)
    assert code == 2 and "pins 9.9.9" in capsys.readouterr().err


def test_missing_config_section(tmp_path, capsys):
    cfg = base_config()
    del cfg["predicates"]
    code, _, _ = run(tmp_path, config=cfg)
    assert code == 2 and "predicates" in capsys.readouterr().err


def test_bad_biolink_dir(tmp_path, capsys):
    code = ex.main(["--config", str(CONFIG), "--records", str(RECORDS), "--out", str(tmp_path / "o"),
                    "--biolink-dir", str(tmp_path)])
    assert code == 2 and "must contain" in capsys.readouterr().err
