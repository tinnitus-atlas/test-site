"""Tests for the website builder and the MCP server."""
import copy
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))
import build_site  # noqa: E402

CFG_PATH = ROOT / "kit.tinnitus.yaml"
REC_PATH = ROOT / "records" / "tinnitus.records.json"
REAL = json.loads(REC_PATH.read_text())


def build(tmp_path, records=None, held=None):
    rec = REC_PATH
    if records is not None:
        rec = tmp_path / "recs" / "r.json"
        rec.parent.mkdir(parents=True, exist_ok=True)
        rec.write_text(json.dumps({"records": records}))
        if held is not None:
            (rec.parent / "held_records.json").write_text(json.dumps({"held_records": held}))
    out = tmp_path / "public"
    code = build_site.main(["--config", str(CFG_PATH), "--records", str(rec), "--out", str(out), "--exports", str(tmp_path / "none")])
    return code, out


def test_builds_every_record_page_and_outputs(tmp_path):
    code, out = build(tmp_path)
    assert code == 0
    for p in ["index.html", "about/index.html", "graph/index.html", "treatments/cbt/index.html", "trials/trial-tent-a/index.html",
              "api/v1/index.json", "api/v1/records.json", "api/v1/graph.json", "api/v1/records/cbt.json",
              "llms.txt", "context/cbt.md", "sitemap.xml", "robots.txt", "_headers", "404.html", "assets/style.css"]:
        assert (out / p).exists(), p
    assert len(json.loads((out / "api/v1/index.json").read_text())["records"]) == len(REAL["records"])


def test_internal_links_resolve(tmp_path):
    _, out = build(tmp_path)
    missing = []
    for page in out.rglob("*.html"):
        for href in re.findall(r'href="(/[^"#?]*)', page.read_text()):
            target = out / href.lstrip("/")
            if not (target.exists() or (target / "index.html").exists()):
                missing.append((page.relative_to(out), href))
    assert missing == []


def test_jsonld_is_valid(tmp_path):
    _, out = build(tmp_path)
    for page in [out / "index.html", out / "treatments/cbt/index.html"]:
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', page.read_text(), re.S)
        data = json.loads(blocks[0])
        assert data["@context"] == "https://schema.org"
    assert json.loads(re.findall(r'ld\+json">(.*?)</script>', (out / "index.html").read_text(), re.S)[0])["@type"] == "Dataset"


def test_html_is_escaped(tmp_path):
    recs = copy.deepcopy(REAL["records"])
    recs[0]["name"] = 'Tinnitus <script>alert(1)</script>'
    recs[0]["tldr"] = "</script><img src=x onerror=alert(1)>"
    _, out = build(tmp_path, recs)
    page = (out / "conditions/tinnitus/index.html").read_text()
    assert "<script>alert(1)" not in page and "<img src=x" not in page
    assert "&lt;script&gt;" in page


def test_held_records_are_withheld_everywhere(tmp_path):
    _, out = build(tmp_path, copy.deepcopy(REAL["records"]), held=["tin:cbt"])
    assert not (out / "treatments/cbt").exists()
    assert "tin:cbt" not in (out / "api/v1/records.json").read_text()
    assert "Cognitive behavioural therapy" not in (out / "llms.txt").read_text()
    assert all(e["target"] != "tin:cbt" for e in json.loads((out / "api/v1/graph.json").read_text())["edges"])


def test_audit_failures_are_withheld_without_held_file(tmp_path):
    recs = copy.deepcopy(REAL["records"])
    del recs[2]["relations"][0]["quote"]  # CBT assertion without quote: blocking
    _, out = build(tmp_path, recs)
    assert not (out / "treatments/cbt").exists()


def test_bad_input(tmp_path, capsys):
    code = build_site.main(["--config", str(CFG_PATH), "--records", str(tmp_path / "missing.json"), "--out", str(tmp_path / "o")])
    assert code == 2


# --- MCP server --------------------------------------------------------------------

def mcp_session(api_dir, messages):
    proc = subprocess.run([sys.executable, str(ROOT / "mcp" / "server.py"), "--data", str(api_dir)],
                          input="\n".join(json.dumps(m) for m in messages) + "\n", capture_output=True, text=True, timeout=30)
    return [json.loads(l) for l in proc.stdout.splitlines() if l.strip()]


def test_mcp_protocol(tmp_path):
    _, out = build(tmp_path)
    replies = mcp_session(out / "api/v1", [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search_records", "arguments": {"query": "sound therapy"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "get_record", "arguments": {"id": "tin:cbt"}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "related_records", "arguments": {"id": "tin:tinnitus"}}},
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "get_record", "arguments": {"id": "tin:nope"}}},
        {"jsonrpc": "2.0", "id": 7, "method": "nonexistent"},
    ])
    by = {r["id"]: r for r in replies}
    assert len(replies) == 7  # the notification gets no reply
    assert by[1]["result"]["protocolVersion"] == "2025-06-18" and "tools" in by[1]["result"]["capabilities"]
    assert {t["name"] for t in by[2]["result"]["tools"]} == {"search_records", "get_record", "related_records", "list_kinds"}
    hits = json.loads(by[3]["result"]["content"][0]["text"])["result"]
    assert hits[0]["id"] == "tin:sound-therapy-devices"
    rec = json.loads(by[4]["result"]["content"][0]["text"])["result"]
    assert rec["relations"][0]["quote"].startswith("reducing the negative impact")
    rel = json.loads(by[5]["result"]["content"][0]["text"])["result"]
    assert any(r["direction"] == "incoming" for r in rel)
    assert by[6]["result"]["isError"] is True
    assert by[7]["error"]["code"] == -32601


def test_test_site_mode_hides_from_search_and_grants_no_licence(tmp_path):
    cfg = yaml.safe_load(CFG_PATH.read_text())
    assert cfg["site"]["test_site"] is True  # the shipped config is a test site until launch
    _, out = build(tmp_path)
    assert (out / "robots.txt").read_text().strip().endswith("Disallow: /")
    assert "X-Robots-Tag: noindex" in (out / "_headers").read_text()
    home = (out / "index.html").read_text()
    assert 'name="robots" content="noindex' in home and "Test version" in home
    assert "CC BY" not in home and "not yet licensed" in home


def test_launch_mode_is_indexable(tmp_path):
    cfg = yaml.safe_load(CFG_PATH.read_text())
    cfg["site"]["test_site"] = False
    cfg_path = tmp_path / "kit.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg))
    out = tmp_path / "public"
    assert build_site.main(["--config", str(cfg_path), "--records", str(REC_PATH), "--out", str(out), "--exports", str(tmp_path / "x")]) == 0
    assert "Allow: /" in (out / "robots.txt").read_text()
    assert "noindex" not in (out / "index.html").read_text()
