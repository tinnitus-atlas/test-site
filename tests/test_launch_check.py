"""Tests for the launch check."""
import copy
from pathlib import Path

import yaml

from kgkit import launch_check as lc

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / "kit.tinnitus.yaml").read_text())
RECS = [{"id": f"x:{i}"} for i in range(10)]


def states(cfg, recs=RECS):
    return {item.split(":")[0]: st for st, item, _ in lc.check(cfg, recs)}


def test_shipped_config_is_not_ready():
    st = states(CFG)
    assert st["Test mode off"] == lc.BLOCK
    assert st["Data licence chosen"] == lc.BLOCK
    assert st["Corrections address published"] == lc.BLOCK
    assert st["Own domain"] == lc.WARN and st["Records"] == lc.WARN and st["Clinician review"] == lc.WARN


def test_ready_when_decisions_are_made_and_only_warnings_remain(tmp_path):
    cfg = copy.deepcopy(CFG)
    cfg["site"].update(test_site=False, licence_decided=True, contact_email="corrections@example.org")
    items = lc.check(cfg, RECS)
    assert not [i for i in items if i[0] == lc.BLOCK]
    assert lc.render(items).splitlines()[2] == "Ready to launch."
    assert items[0][0] == lc.WARN  # warnings listed before done items


def test_cli_exit_codes(tmp_path):
    rec = ROOT / "records" / "tinnitus.records.json"
    assert lc.main(["--config", str(ROOT / "kit.tinnitus.yaml"), "--records", str(rec), "--report", str(tmp_path / "r.md")]) == 1
    assert "Not ready: 3 blockers." in (tmp_path / "r.md").read_text()
    assert lc.main(["--config", str(tmp_path / "missing.yaml"), "--records", str(rec)]) == 2
