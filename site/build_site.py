#!/usr/bin/env python3
"""
Build the public website, JSON API and agent-readable files from the records.

Output (default folder public/):
  index.html, about/, graph/, <kind>/ (filterable table), <kind>/<slug>/ (one page per record),
  api/v1/{index,records,graph}.json, api/v1/records/<slug>.json, api/v1/kgx/ (if exports/ exists),
  context/<slug>.md and llms.txt (for AI agents), sitemap.xml, robots.txt, _headers, 404.html.

Records held back by the quality checks are not published: the builder runs the audit itself and also
reads records/held_records.json (written by the nightly run) when present.

Usage: python3 site/build_site.py --config kit.tinnitus.yaml --records records/tinnitus.records.json --out public
Exit codes: 0 built; 2 bad input.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kgkit import audit  # noqa: E402
from kgkit.common import KitError, load_config, load_records  # noqa: E402

ASSETS = Path(__file__).resolve().parent / "assets"
AGENT_LABEL = {
    "manual_agent": "written by a person",
    "manual_validation_of_automated_agent": "drafted by an agent and checked by a person",
    "automated_agent": "drafted by an agent; not yet checked by a person",
    "text_mining_agent": "extracted automatically from a registry or database",
    "data_analysis_pipeline": "produced by an automated analysis",
    "computational_model": "predicted by a model",
}
LEVEL_LABEL = {
    "knowledge_assertion": "Sourced statement",
    "prediction": "Hypothesis",
    "observation": "Observation",
    "statistical_association": "Statistical association",
    "not_provided": "Link",
}
OBO = {"HP", "MONDO", "MAXO", "UBERON", "CHEBI", "GO", "CL", "DOID"}


def e(text) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


def ext(url) -> str:
    """Escaped outside link, or '#' unless it is plain http(s): blocks javascript: and data: links in record data."""
    u = str(url or "").strip()
    return e(u) if re.match(r"https?://", u, re.I) else "#"


def script_json(obj) -> str:
    """JSON safe to place inside a <script> element."""
    return (json.dumps(obj, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def resolver(curie: str) -> str | None:
    prefix, _, local = curie.partition(":")
    if not local:
        return None
    if prefix.upper() in OBO:
        return f"http://purl.obolibrary.org/obo/{prefix.upper()}_{local}"
    if prefix.upper() == "CLINICALTRIALS":
        return f"https://clinicaltrials.gov/study/{local}"
    if prefix.upper() == "PMID":
        return f"https://pubmed.ncbi.nlm.nih.gov/{local}/"
    if prefix.lower() == "doi":
        return f"https://doi.org/{local}"
    if prefix.upper() == "ORCID":
        return f"https://orcid.org/{local}"
    return f"https://bioregistry.io/{curie}"


# Static site, no logins or forms: these headers stop the pages being framed, sniffed or made to run outside scripts.
SECURITY_HEADERS = ("/*\n"
                    "  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'none'; object-src 'none'\n"
                    "  X-Content-Type-Options: nosniff\n"
                    "  Referrer-Policy: strict-origin-when-cross-origin\n"
                    "  Permissions-Policy: camera=(), microphone=(), geolocation=()\n"
                    "  Strict-Transport-Security: max-age=31536000\n")
CORS = "/api/*\n  Access-Control-Allow-Origin: *\n/context/*\n  Access-Control-Allow-Origin: *\n"


class Site:
    def __init__(self, cfg: dict, records: list[dict], held: set[str], today: str):
        self.cfg, self.today = cfg, today
        self.s = cfg.get("site") or {}
        self.kinds = self.s.get("kinds") or {}
        self.labels = self.s.get("predicate_labels") or {}
        self.base = (self.s.get("base_url") or "").rstrip("/")
        # Test mode: hidden from search engines and AI crawlers, no data licence granted, labelled as unreviewed.
        self.test = bool(self.s.get("test_site"))
        if self.test:
            self.s = {**self.s, "licence_data": "not yet licensed (test site)"}
        self.held = held
        self.records = [r for r in records if r.get("id") not in held]
        self.by_id = {r["id"]: r for r in self.records}
        self.slugs = self._slugs()
        self.incoming = defaultdict(list)
        for r in self.records:
            for rel in r.get("relations") or []:
                if rel.get("object") in self.by_id:
                    self.incoming[rel["object"]].append((r, rel))

    # ---- naming --------------------------------------------------------------
    def _slugs(self) -> dict:
        out, used = {}, set()
        for r in self.records:
            base = re.sub(r"[^a-z0-9]+", "-", r["id"].split(":", 1)[-1].lower()).strip("-") or "record"
            slug, n = base, 2
            while (r["kind"], slug) in used:
                slug, n = f"{base}-{n}", n + 1
            used.add((r["kind"], slug))
            out[r["id"]] = slug
        return out

    def kind_meta(self, kind: str) -> dict:
        m = self.kinds.get(kind) or {}
        return {"label": m.get("label", kind.replace("_", " ").title()), "plural": m.get("plural", kind.replace("_", " ").title() + "s"),
                "path": m.get("path", kind.replace("_", "-")), "schema": m.get("schema", "Thing")}

    def url(self, r: dict) -> str:
        return f"/{self.kind_meta(r['kind'])['path']}/{self.slugs[r['id']]}/"

    def phrase(self, predicate: str, reverse=False) -> str:
        pair = self.labels.get(predicate) or [predicate.replace("_", " "), predicate.replace("_", " ") + " (reverse)"]
        return pair[1 if reverse else 0]

    # ---- page frame ----------------------------------------------------------
    def page(self, title: str, body: str, description: str = "", jsonld: dict | None = None, path: str = "/") -> str:
        t = self.s.get("title", "Knowledge graph")
        ld = f'<script type="application/ld+json">{script_json(jsonld)}</script>' if jsonld else ""
        canon = f'<link rel="canonical" href="{e(self.base + path)}">' if self.base else ""
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}{' · ' + e(t) if title != t else ''}</title><meta name="description" content="{e(description or self.s.get('tagline', ''))}">
{canon}{'<meta name="robots" content="noindex, nofollow">' if self.test else ''}<link rel="stylesheet" href="/assets/style.css">{ld}</head>
<body><a class="skip" href="#main">Skip to content</a>
<header class="site"><div class="wrap"><a class="brand" href="/">{e(t)}</a>
<nav class="top" aria-label="Main"><a href="/treatments/">Treatments</a><a href="/trials/">Trials</a><a href="/graph/">Graph</a><a href="/about/">About</a></nav></div></header>
<main id="main"><div class="wrap">{body}</div></main>
<footer class="site"><div class="wrap">Not medical advice. Every statement links to its source; check anything that matters there.
Data {e(self.s.get('licence_data', ''))} · code {e(self.s.get('licence_code', ''))} · built {e(self.today)} ·
<a href="/api/v1/index.json">API</a> · <a href="/llms.txt">llms.txt</a></div></footer>
<script src="/assets/app.js" defer></script></body></html>
"""

    def banner(self) -> str:
        if self.test:
            return ('<p class="banner"><strong>Test version. Not medical advice.</strong> Built by automated tools to test the '
                    'process; not yet reviewed by a clinician. Do not rely on anything here.</p>')
        return ('<p class="banner"><strong>Not medical advice.</strong> This is a map of published evidence, built and '
                'checked nightly by automated tools with human review. Talk to a clinician about your own situation.</p>')

    # ---- pages -----------------------------------------------------------------
    def record_page(self, r: dict) -> str:
        km = self.kind_meta(r["kind"])
        parts = [f'<p><span class="kind">{e(km["label"])}</span></p><h1>{e(r["name"])}</h1>',
                 f'<p class="lede">{e(r.get("tldr"))}</p>']
        if r.get("summary"):
            parts.append(f"<p>{e(r['summary'])}</p>")
        parts.append(f'<p class="meta">Last checked {e(r.get("asOf"))}'
                     + (f' · Status: {e(str(r["status"]).replace("_", " "))}' if r.get("status") else "") + "</p>")
        parts.append(self.banner())
        facts = r.get("facts") or {}
        if facts:
            rows = []
            for k, v in facts.items():
                val, src = (v.get("value"), v.get("source")) if isinstance(v, dict) else (v, None)
                link = f' <a href="{ext(src)}" rel="nofollow noopener">source</a>' if src else ""
                label = re.sub(r"\b(Fda|Ema|Mhra|Ce)\b", lambda m: m.group(1).upper(), k.replace("_", " ").capitalize())
                rows.append(f"<tr><th scope=\"row\">{e(label)}</th><td>{e(val)}{link}</td></tr>")
            parts.append("<h2>Key facts</h2><div class=\"table-scroll\"><table>" + "".join(rows) + "</table></div>")
        rels = [rel for rel in r.get("relations") or [] if rel.get("object") in self.by_id]
        if rels:
            parts.append("<h2>What the evidence says</h2>")
            for rel in rels:
                parts.append(self.rel_block(r, rel, self.by_id[rel["object"]], reverse=False))
        inc = self.incoming.get(r["id"]) or []
        if inc:
            parts.append("<h2>Linked from</h2>")
            for src, rel in inc:
                parts.append(self.rel_block(src, rel, src, reverse=True))
        if r.get("xrefs"):
            items = []
            for x in r["xrefs"]:
                href = resolver(x)
                items.append(f'<li><a href="{ext(href)}" rel="nofollow noopener"><code>{e(x)}</code></a></li>' if href else f"<li><code>{e(x)}</code></li>")
            parts.append('<h2>Identifiers</h2><ul class="plain ids">' + "".join(items) + "</ul>")
        if r.get("closeMatches"):
            items = [f'<li><code>{e(m.get("id"))}</code> {e(m.get("label"))}: <span class="meta">{e(m.get("note"))}</span></li>' for m in r["closeMatches"]]
            parts.append('<h2>Close matches in standard vocabularies</h2><ul class="plain">' + "".join(items) + "</ul>")
        srcs = r.get("sources") or []
        parts.append("<h2>Sources</h2><ul>" + "".join(
            f'<li><a href="{ext(s.get("url"))}" rel="nofollow noopener">{e(s.get("label") or s.get("url"))}</a></li>' for s in srcs) + "</ul>")
        repo = self.s.get("repo_url")
        if repo:
            parts.append(f'<p class="meta">Spotted an error? <a href="{ext(repo)}/issues/new?title={e("Correction: " + r["name"])}">Suggest a correction</a> · '
                         f'<a href="/api/v1/records/{e(self.slugs[r["id"]])}.json">This record as JSON</a></p>')
        return self.page(r["name"], "\n".join(parts), r.get("tldr", ""), self.jsonld(r), self.url(r))

    def rel_block(self, subject: dict, rel: dict, other: dict, reverse: bool) -> str:
        if reverse:
            stmt = f'<a href="{e(self.url(other))}">{e(other["name"])}</a> {e(self.phrase(rel["predicate"]))} this'
        else:
            stmt = f'{e(self.phrase(rel["predicate"]))} <a href="{e(self.url(other))}">{e(other["name"])}</a>'
        level = LEVEL_LABEL.get(rel.get("knowledgeLevel"), "Link")
        bits = [f'<div class="rel"><div class="stmt">{stmt}</div><div class="meta">{e(level)} · {e(AGENT_LABEL.get(rel.get("agentType"), "origin not recorded"))}</div>']
        if rel.get("quote") and not reverse:
            bits.append(f"<blockquote>“{e(rel['quote'])}”</blockquote>")
        links = []
        for p in rel.get("publications") or []:
            href = resolver(p) if ":" in p else None
            links.append(f'<a href="{ext(href)}" rel="nofollow noopener">{e(p)}</a>' if href else e(p))
        if rel.get("sourceUrl"):
            links.append(f'<a href="{ext(rel["sourceUrl"])}" rel="nofollow noopener">source</a>')
        if links and not reverse:
            bits.append(f'<div class="meta">Evidence: {" · ".join(links)}</div>')
        bits.append("</div>")
        return "".join(bits)

    def jsonld(self, r: dict) -> dict:
        ld = {"@context": "https://schema.org", "@type": self.kind_meta(r["kind"])["schema"], "name": r["name"],
              "description": r.get("tldr", ""), "dateModified": r.get("asOf")}
        if self.base:
            ld["url"] = self.base + self.url(r)
        same = [resolver(x) for x in r.get("xrefs") or [] if resolver(x)]
        if same:
            ld["sameAs"] = same
        cites = [s.get("url") for s in r.get("sources") or [] if s.get("url")]
        if cites:
            ld["citation"] = cites
        return ld

    def kind_index(self, kind: str, recs: list[dict]) -> str:
        km = self.kind_meta(kind)
        show_status = any(r.get("status") for r in recs)
        head = "<tr><th>Name</th><th>Summary</th><th>Last checked</th>" + ("<th>Status</th>" if show_status else "") + "</tr>"
        rows = []
        for r in sorted(recs, key=lambda x: x["name"].lower()):
            status = f"<td>{e(str(r.get('status') or '').replace('_', ' '))}</td>" if show_status else ""
            rows.append(f'<tr><td><a href="{e(self.url(r))}">{e(r["name"])}</a></td><td>{e(r.get("tldr"))}</td><td>{e(r.get("asOf"))}</td>{status}</tr>')
        body = (f"<h1>{e(km['plural'])}</h1><p class=\"lede\">{len(recs)} records. Every row links to a page with its sources.</p>"
                f'<label for="flt" class="meta">Filter this list</label><input id="flt" type="search" data-filter-table="#tbl" placeholder="Type to filter">'
                f'<div class="table-scroll"><table id="tbl"><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>')
        return self.page(km["plural"], body, f"{km['plural']} in the {self.s.get('title', '')}", path=f"/{km['path']}/")

    def home(self, groups: dict) -> str:
        cards = "".join(f'<a class="card" href="/{e(self.kind_meta(k)["path"])}/"><span class="n">{len(v)}</span><span class="l">{e(self.kind_meta(k)["plural"])}</span></a>'
                        for k, v in groups.items())
        body = (f"<h1>{e(self.s.get('title', ''))}</h1><p class=\"lede\">{e(self.s.get('tagline', ''))}</p>{self.banner()}"
                f'<label for="site-search" class="meta">Search everything</label>'
                f'<input id="site-search" type="search" data-index="/api/v1/index.json" placeholder="Try: sound therapy, CBT, trial">'
                f'<ul id="search-results" class="results"></ul><h2>Browse</h2><div class="grid">{cards}</div>'
                f'<h2>How this works</h2><ul><li>Every statement links to a primary source, with a short verbatim quote where it states a finding.</li>'
                f'<li>Automated checks run every night: cited papers are matched to their claims, quotes are found in the source, trial statuses are compared with the registry, and stale records are flagged.</li>'
                f'<li>Changes found overnight are proposed, not applied; a person approves each one.</li></ul>'
                f'<p><a href="/graph/">Explore the graph</a> · <a href="/about/">Method and licence</a></p>')
        return self.page(self.s.get("title", "Knowledge graph"), body, self.s.get("tagline", ""), self.dataset_ld(), "/")

    def dataset_ld(self) -> dict:
        ld = {"@context": "https://schema.org", "@type": "Dataset", "name": self.s.get("title", ""),
              "description": f"{self.s.get('tagline', '')} Open, cited records on conditions, treatments, trials, devices and papers, with every statement linked to its source.",
              "license": self.s.get("licence_data"), "dateModified": self.today, "isAccessibleForFree": True}
        if self.base:
            ld["url"] = self.base + "/"
            ld["distribution"] = [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": self.base + "/api/v1/records.json"}]
        return ld

    def about(self) -> str:
        body = (f"<h1>About</h1><p class=\"lede\">{e(self.s.get('tagline', ''))}</p>{self.banner()}"
                "<h2>Method</h2><p>Records are collected from public sources such as Europe PMC, ClinicalTrials.gov and FDA device data, "
                "structured by automated agents, and published only after passing automated checks. Statements of fact carry a short quote "
                "copied from the source. Each statement shows whether it was drafted by an agent, extracted from a registry, or checked by a person.</p>"
                "<h2>Nightly checks</h2><ul><li>Cited papers are looked up and compared with the claim that cites them.</li>"
                "<li>Quotes must appear word for word in the cited abstract.</li><li>Trial details are compared with ClinicalTrials.gov.</li>"
                "<li>Regulatory claims must cite the regulator, not only the manufacturer.</li><li>Records older than their freshness limit are flagged.</li>"
                "<li>Records failing a blocking check are withheld until fixed.</li></ul>"
                f"<h2>Licence</h2><p>Data: {e(self.s.get('licence_data', ''))}. Code: {e(self.s.get('licence_code', ''))}. Quotes remain the work of their authors.</p>"
                "<h2>For developers and AI agents</h2><p><a href=\"/api/v1/index.json\">JSON index</a> · <a href=\"/api/v1/records.json\">all records</a> · "
                "<a href=\"/api/v1/graph.json\">graph</a> · <a href=\"/llms.txt\">llms.txt</a>"
                + (" · <a href=\"/api/v1/kgx/\">Biolink KGX files</a>" if self._kgx_present else "") + "</p>")
        return self.page("About", body, "Method, checks and licence", path="/about/")

    def graph_page(self) -> str:
        body = ('<h1>Graph</h1><p class="lede">Every record is a dot; every line is a sourced or linked relationship. '
                'Drag to rearrange, click a dot to open its page.</p><div id="graph-legend" class="legend"></div>'
                '<svg id="graph" data-src="/api/v1/graph.json" role="img" aria-label="Graph of records and relationships"></svg>'
                '<script src="/assets/graph.js" defer></script>'
                '<p class="meta">Prefer a list? <a href="/api/v1/index.json">Browse the index</a>.</p>')
        return self.page("Graph", body, "Interactive graph of the knowledge base", path="/graph/")

    # ---- data outputs ------------------------------------------------------------
    def public_record(self, r: dict) -> dict:
        out = {k: v for k, v in r.items()}
        out["relations"] = [rel for rel in r.get("relations") or [] if rel.get("object") in self.by_id]
        out["url"] = (self.base or "") + self.url(r)
        out["linkedFrom"] = [{"id": s["id"], "predicate": rel["predicate"]} for s, rel in self.incoming.get(r["id"], [])]
        return out

    def context_md(self, r: dict) -> str:
        lines = [f"# {r['name']}", "", f"Kind: {self.kind_meta(r['kind'])['label']}. Last checked: {r.get('asOf')}.", "", r.get("tldr", ""), ""]
        for rel in r.get("relations") or []:
            if rel.get("object") in self.by_id:
                q = f' Quote: "{rel["quote"]}"' if rel.get("quote") else ""
                lines.append(f"- {self.phrase(rel['predicate'])} {self.by_id[rel['object']]['name']}.{q}")
        lines += ["", "Sources:"] + [f"- {s.get('label') or ''} {s.get('url')}" for s in r.get("sources") or []]
        lines += ["", f"Attribution: Data from {self.s.get('title', '')} ({self.base or 'site'}), {self.s.get('licence_data', '')}. Not medical advice."]
        return "\n".join(lines) + "\n"

    _kgx_present = False

    def build(self, out: Path, exports: Path | None):
        if out.exists():
            shutil.rmtree(out)
        (out / "assets").mkdir(parents=True)
        for f in ASSETS.iterdir():
            shutil.copy(f, out / "assets" / f.name)
        if exports and exports.exists():
            kgx = list(exports.glob("core_*.jsonl"))
            if kgx:
                self._kgx_present = True
                (out / "api/v1/kgx").mkdir(parents=True)
                for f in kgx:
                    shutil.copy(f, out / "api/v1/kgx" / f.name)
                (out / "api/v1/kgx/index.html").write_text(self.page("Biolink KGX files", "<h1>Biolink KGX files</h1><ul>" + "".join(
                    f'<li><a href="{e(f.name)}">{e(f.name)}</a></li>' for f in kgx) + "</ul>", path="/api/v1/kgx/"), encoding="utf-8")

        groups: dict = {}
        order = list(self.kinds) + sorted({r["kind"] for r in self.records} - set(self.kinds))
        for k in order:
            recs = [r for r in self.records if r["kind"] == k]
            if recs:
                groups[k] = recs
        urls = ["/", "/about/", "/graph/"]
        for k, recs in groups.items():
            d = out / self.kind_meta(k)["path"]
            d.mkdir(parents=True, exist_ok=True)
            (d / "index.html").write_text(self.kind_index(k, recs), encoding="utf-8")
            urls.append(f"/{self.kind_meta(k)['path']}/")
            for r in recs:
                p = out / self.url(r).strip("/")
                p.mkdir(parents=True, exist_ok=True)
                (p / "index.html").write_text(self.record_page(r), encoding="utf-8")
                urls.append(self.url(r))
        (out / "index.html").write_text(self.home(groups), encoding="utf-8")
        for name, content in (("about", self.about()), ("graph", self.graph_page())):
            (out / name).mkdir(exist_ok=True)
            (out / name / "index.html").write_text(content, encoding="utf-8")
        (out / "404.html").write_text(self.page("Not found", "<h1>Page not found</h1><p><a href=\"/\">Back to the start</a></p>"), encoding="utf-8")

        api = out / "api/v1"
        (api / "records").mkdir(parents=True, exist_ok=True)
        attribution = f"Data from {self.s.get('title', '')} ({self.base or 'this site'}), {self.s.get('licence_data', '')}"
        pub = [self.public_record(r) for r in self.records]
        index = [{"id": r["id"], "name": r["name"], "kind": r["kind"], "kind_label": self.kind_meta(r["kind"])["label"],
                  "tldr": r.get("tldr", ""), "url": self.url(r), "asOf": r.get("asOf")} for r in self.records]
        (api / "index.json").write_text(json.dumps({"attribution": attribution, "built": self.today, "records": index}, ensure_ascii=False), encoding="utf-8")
        (api / "records.json").write_text(json.dumps({"attribution": attribution, "built": self.today, "records": pub}, ensure_ascii=False, indent=1), encoding="utf-8")
        for r, p in zip(self.records, pub):
            (api / "records" / f"{self.slugs[r['id']]}.json").write_text(json.dumps({"attribution": attribution, "record": p}, ensure_ascii=False, indent=1), encoding="utf-8")
        degree: dict = defaultdict(int)
        edges = []
        for r in self.records:
            for rel in r.get("relations") or []:
                if rel.get("object") in self.by_id:
                    edges.append({"source": r["id"], "target": rel["object"], "label": self.phrase(rel["predicate"])})
                    degree[r["id"]] += 1
                    degree[rel["object"]] += 1
        nodes = [{"id": i["id"], "name": i["name"], "kind_label": i["kind_label"], "url": i["url"], "degree": degree[i["id"]]} for i in index]
        (api / "graph.json").write_text(json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False), encoding="utf-8")

        ctx = out / "context"
        ctx.mkdir()
        for r in self.records:
            (ctx / f"{self.slugs[r['id']]}.md").write_text(self.context_md(r), encoding="utf-8")
        llms = [f"# {self.s.get('title', '')}", "", f"> {self.s.get('tagline', '')}", "",
                "Open, cited knowledge graph. Not medical advice. Every statement links to its source.", "",
                "## Data", "- [All records (JSON)](/api/v1/records.json)", "- [Index (JSON)](/api/v1/index.json)", "- [Graph (JSON)](/api/v1/graph.json)"]
        if self._kgx_present:
            llms.append("- [Biolink KGX files](/api/v1/kgx/)")
        llms += ["", "## Records"] + [f"- [{r['name']}](/context/{self.slugs[r['id']]}.md): {r.get('tldr', '')}" for r in self.records]
        (out / "llms.txt").write_text("\n".join(llms) + "\n", encoding="utf-8")

        if self.base:
            sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
            sm += [f"<url><loc>{e(self.base + u)}</loc></url>" for u in urls]
            sm.append("</urlset>")
            (out / "sitemap.xml").write_text("\n".join(sm) + "\n", encoding="utf-8")
        if self.test:
            (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
            (out / "_headers").write_text(SECURITY_HEADERS.replace("/*\n", "/*\n  X-Robots-Tag: noindex, nofollow\n", 1) + CORS, encoding="utf-8")
        else:
            (out / "robots.txt").write_text("User-agent: *\nAllow: /\n" + (f"Sitemap: {self.base}/sitemap.xml\n" if self.base else ""), encoding="utf-8")
            (out / "_headers").write_text(SECURITY_HEADERS + CORS, encoding="utf-8")
        return {"pages": len(urls), "records": len(self.records), "withheld": sorted(self.held)}


def held_records(records: list[dict], cfg: dict, held_file: Path | None) -> set[str]:
    with tempfile.TemporaryDirectory() as tmp:
        held = set(audit.run(records, cfg, tmp)["held_records"])
    if held_file and held_file.exists():
        held |= set(json.loads(held_file.read_text(encoding="utf-8")).get("held_records", []))
    return held


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the website from the records")
    ap.add_argument("--config", required=True)
    ap.add_argument("--records", required=True)
    ap.add_argument("--out", default="public")
    ap.add_argument("--held", help="held_records.json from the nightly checks (default: next to the records file)")
    ap.add_argument("--exports", default="exports", help="folder with Biolink KGX exports to publish, if present")
    args = ap.parse_args(argv)
    try:
        cfg = load_config(args.config)
        records = load_records(args.records)
    except KitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    held_file = Path(args.held) if args.held else Path(args.records).parent / "held_records.json"
    held = held_records(records, cfg, held_file)
    site = Site(cfg, records, held, dt.date.today().isoformat())
    result = site.build(Path(args.out), Path(args.exports) if args.exports else None)
    print(f"Built {result['pages']} pages from {result['records']} records into {args.out}"
          + (f"; withheld {len(result['withheld'])}: {', '.join(result['withheld'])}" if result["withheld"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
