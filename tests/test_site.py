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


def test_every_record_page_says_how_it_was_made_without_naming_tools(tmp_path):
    import re
    out = tmp_path / "out"
    r = subprocess.run([sys.executable, str(ROOT / "site" / "build_site.py"), "--config", str(ROOT / "kit.tinnitus.yaml"),
                        "--records", str(ROOT / "tests" / "fixtures" / "tinnitus.records.json"), "--out", str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    pages = [p for p in out.rglob("index.html") if p.parent.parent.name in ("treatments", "trials", "devices", "conditions")]
    assert pages
    for p in pages:
        html = p.read_text()
        assert "How this page was made" in html and "Summary not yet checked by a clinician" in html
        assert not re.search(r"qwen|deepseek|sonnet|llama|lm studio", html, re.I)
    treatments = (out / "treatments" / "index.html").read_text()
    assert "Trials linked" in treatments and "not a recommendation" in treatments


def test_drafted_summaries_are_labelled_as_drafts(tmp_path):
    import json as _json
    data = _json.loads((ROOT / "tests" / "fixtures" / "tinnitus.records.json").read_text())
    rec = next(x for x in data["records"] if x["kind"] == "intervention")
    rec["provenance"] = {"drafted_by": "some-local-model-7b", "drafted_on": "2026-11-24"}
    f = tmp_path / "r.json"
    f.write_text(_json.dumps(data))
    out = tmp_path / "out"
    r = subprocess.run([sys.executable, str(ROOT / "site" / "build_site.py"), "--config", str(ROOT / "kit.tinnitus.yaml"),
                        "--records", str(f), "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    import html as _html
    own = f"<h1>{_html.escape(rec['name'])}</h1>"
    html = next(p for p in out.rglob("index.html") if own in p.read_text()).read_text()
    assert "Draft summary written by an AI model" in html and "some-local-model-7b" not in html


def launched(tmp_path, **site):
    cfg = yaml.safe_load(CFG_PATH.read_text())
    cfg["site"].update({"test_site": False, **site})
    tmp_path.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "kit.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg))
    out = tmp_path / "public"
    assert build_site.main(["--config", str(cfg_path), "--records", str(REC_PATH), "--out", str(out), "--exports", str(tmp_path / "x")]) == 0
    return out


def test_launch_pages_exist_and_are_linked_from_every_page(tmp_path):
    out = launched(tmp_path, contact_email="corrections@example.org")
    for p in ("disclaimer", "privacy", "corrections"):
        assert (out / p / "index.html").exists()
        assert f"/{p}/" in (out / "sitemap.xml").read_text()
    home = (out / "index.html").read_text()
    for href in ('href="/disclaimer/"', 'href="/privacy/"', 'href="/corrections/"'):
        assert href in home
    assert 'mailto:corrections@example.org' in (out / "corrections/index.html").read_text()
    dis = (out / "disclaimer/index.html").read_text()
    assert "head injury" in dis and "https://www.nhs.uk/conditions/tinnitus/" in dis


def test_bad_contact_address_is_not_printed(tmp_path):
    out = launched(tmp_path, contact_email='x" onmouseover="alert(1)@a.org')
    page = (out / "corrections/index.html").read_text()
    assert "mailto:" not in page and "onmouseover" not in page
    assert "will be published here before launch" in page


def test_launched_site_without_clinician_says_pilot(tmp_path):
    out = launched(tmp_path)
    page = (out / "treatments/cbt/index.html").read_text()
    assert "Pilot. Not medical advice." in page and "no clinician has checked them yet" in page
    assert "not about the trials, papers or products themselves" in page
    out2 = launched(tmp_path / "b", clinical_review=True)
    assert "Pilot." not in (out2 / "treatments/cbt/index.html").read_text()


def test_analytics_only_on_launched_site_with_valid_token(tmp_path):
    token = "a" * 32
    out = launched(tmp_path, analytics_token=token)
    assert f'"token": "{token}"' in (out / "index.html").read_text()
    headers = (out / "_headers").read_text()
    assert "script-src 'self' https://static.cloudflareinsights.com" in headers
    assert "connect-src 'self' https://cloudflareinsights.com" in headers
    assert "cookies" in (out / "privacy/index.html").read_text()
    bad = launched(tmp_path / "bad", analytics_token='x"><script>alert(1)</script>')
    assert "cloudflareinsights" not in (bad / "index.html").read_text()
    assert "cloudflareinsights" not in (bad / "_headers").read_text()
    # The shipped config is a test site: never loads analytics even with a token.
    cfg = yaml.safe_load(CFG_PATH.read_text())
    cfg["site"]["analytics_token"] = token
    (tmp_path / "t.yaml").write_text(yaml.safe_dump(cfg))
    test_out = tmp_path / "test-public"
    build_site.main(["--config", str(tmp_path / "t.yaml"), "--records", str(REC_PATH), "--out", str(test_out), "--exports", str(tmp_path / "x")])
    assert "cloudflareinsights" not in (test_out / "index.html").read_text()
    assert "does not use analytics" in (test_out / "privacy/index.html").read_text()


def test_pages_carry_link_preview_tags(tmp_path):
    _, out = build(tmp_path)
    page = (out / "treatments/cbt/index.html").read_text()
    for tag in ('property="og:title"', 'property="og:description"', 'property="og:url"', 'name="twitter:card"'):
        assert tag in page


def test_summary_check_results_show_only_for_the_summary_they_checked(tmp_path):
    from kgkit.common import summary_hash
    recs = copy.deepcopy(REAL["records"])
    cbt = next(r for r in recs if r["id"] == "tin:cbt")
    sound = next(r for r in recs if r["id"] == "tin:sound-therapy-devices")
    rec = tmp_path / "recs" / "r.json"
    rec.parent.mkdir(parents=True)
    rec.write_text(json.dumps({"records": recs}))
    (rec.parent / "summary_checks.json").write_text(json.dumps({"records": {
        "tin:cbt": {"status": "flagged", "summary_hash": summary_hash(cbt), "checked_on": "2026-11-25"},
        "tin:sound-therapy-devices": {"status": "ok", "summary_hash": summary_hash(sound), "checked_on": "2026-11-25"},
        "tin:bimodal-neuromodulation": {"status": "flagged", "summary_hash": "stale", "checked_on": "2026-11-01"}}}))
    out = tmp_path / "public"
    assert build_site.main(["--config", str(CFG_PATH), "--records", str(rec), "--out", str(out), "--exports", str(tmp_path / "x")]) == 0
    assert "Summary under review" in (out / "treatments/cbt/index.html").read_text()
    assert "independent automated check on 2026-11-25" in (out / "treatments/sound-therapy-devices/index.html").read_text()
    assert "Summary under review" not in (out / "treatments/bimodal-neuromodulation/index.html").read_text()
    assert "Nightly summary check" in (out / "about/index.html").read_text()
    _, plain = build(tmp_path / "plain")
    assert "Nightly summary check" not in (plain / "about/index.html").read_text()


def test_launched_about_page_links_the_licence_and_commercial_terms(tmp_path):
    out = launched(tmp_path, contact_email="corrections@example.org")
    about = (out / "about/index.html").read_text()
    assert 'href="https://creativecommons.org/licenses/by-nc/4.0/"' in about and "separate licence" in about


def test_editor_page_is_published_hidden_and_has_its_own_policy(tmp_path):
    _, out = build(tmp_path)
    assert (out / "admin/index.html").exists() and (out / "admin/config.yml").exists()
    page = (out / "admin/index.html").read_text()
    assert "noindex" in page and "@sveltia/cms@0." in page  # pinned to one version
    cfg = yaml.safe_load((out / "admin/config.yml").read_text())
    assert cfg["backend"]["branch"] == "edits"  # edits never go straight to the live site
    headers = (out / "_headers").read_text()
    assert headers.index("/admin/*") > headers.index("/*\n")  # the detach must come after the site-wide rule
    assert "! Content-Security-Policy" in headers
