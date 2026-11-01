#!/usr/bin/env python3
"""
Export a project's knowledge-graph records to Biolink-compliant KGX files.

Reads:
  - a configuration file (kinds -> Biolink categories, relationship names -> Biolink predicates)
  - a records file (JSON: {"records": [...]}, the Knowledge Quality Kit data contract)

Writes to the output directory:
  - core_nodes.jsonl / core_edges.jsonl   only nodes with a standard identifier and edges between them;
                                           this is the interoperable graph that must pass KGX validation
  - full_nodes.jsonl / full_edges.jsonl   every exported record, including project-namespace identifiers
  - export_report.json                    counts, items left out of the core graph and why, precheck findings

The built-in precheck mirrors the KGX validator's rules (identifier prefixes from the Biolink JSON-LD
context, known non-mixin categories, known predicates, required edge properties, enum values, list-valued
properties) and adds advisory domain/range warnings. It is a fast first gate, not a replacement for
`kgx validate`, which run_validation.sh runs afterwards when KGX is installed.

Usage:
  python3 export_biolink.py --config kit.tinnitus.yaml --records records.json --out out/
         [--biolink-dir DIR] [--format jsonl|tsv] [--no-precheck]

Exit codes: 0 ok; 1 precheck errors in the core graph; 2 bad input or configuration.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
import uuid
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required: pip install pyyaml")

MODEL_FILE = "biolink_model.yaml"
CONTEXT_FILE = "biolink_model.context.jsonld"
REQUIRED_EDGE_PROPS = ["id", "subject", "predicate", "object", "knowledge_level", "agent_type"]
CAMEL = re.compile(r"^([A-Z][a-z\d]+)+$")
SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
CURIE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*:[^\s]+$")
EDGE_NS = uuid.UUID("6f1c2f2e-1d5b-4c0e-9a51-2c8d0b6f6a10")


class InputError(Exception):
    """Bad configuration or records; reported with exit code 2."""


# ---------------------------------------------------------------------------
# Biolink model
# ---------------------------------------------------------------------------

def to_space(name: str) -> str:
    """'PhenotypicFeature' -> 'phenotypic feature'; 'has_phenotype' -> 'has phenotype'."""
    if "_" in name or name.islower():
        return name.replace("_", " ")
    return re.sub(r"(?<!^)(?=[A-Z])", " ", name).lower()


def local(curie: str) -> str:
    return curie.split(":", 1)[1] if ":" in curie else curie


def prefix_of(curie: str) -> str | None:
    return curie.split(":", 1)[0] if CURIE.match(curie or "") else None


class Biolink:
    def __init__(self, model: dict, context: dict):
        self.version = str(model.get("version", "unknown"))
        self.classes: dict = model.get("classes", {})
        self.slots: dict = model.get("slots", {})
        self.enums: dict = model.get("enums", {})
        ctx = context.get("@context", context)
        self.prefixes = {k for k, v in ctx.items()
                         if isinstance(v, str) or (isinstance(v, dict) and v.get("@prefix", False))}
        self.prefixes.add("biolink")

    @classmethod
    def load(cls, version: str, model_url: str, context_url: str, biolink_dir: str | None) -> "Biolink":
        if biolink_dir:
            base = Path(biolink_dir)
            model_path = next(iter(base.rglob(MODEL_FILE)), None) if base.is_dir() else None
            context_path = next(iter(base.rglob(CONTEXT_FILE)), None) if base.is_dir() else None
            if not model_path or not context_path:
                raise InputError(f"--biolink-dir {base} must contain {MODEL_FILE} and {CONTEXT_FILE}")
        else:
            cache = Path.home() / ".cache" / "kg-biolink-export" / version
            cache.mkdir(parents=True, exist_ok=True)
            model_path, context_path = cache / MODEL_FILE, cache / CONTEXT_FILE
            for path, url in ((model_path, model_url), (context_path, context_url)):
                if not path.exists():
                    try:
                        with urllib.request.urlopen(url.format(version=version), timeout=60) as r:
                            path.write_bytes(r.read())
                    except Exception as exc:  # network refused, offline, 404
                        raise InputError(f"Could not download {url.format(version=version)}: {exc}. "
                                         f"Download it manually or pass --biolink-dir.") from exc
        with open(model_path, encoding="utf-8") as f:
            model = yaml.safe_load(f)
        with open(context_path, encoding="utf-8") as f:
            context = json.load(f)
        bl = cls(model, context)
        if bl.version != version:
            raise InputError(f"Biolink files are version {bl.version}, configuration pins {version}")
        return bl

    def ancestors(self, cls_name: str) -> set[str]:
        seen: set[str] = set()
        stack = [cls_name]
        while stack:
            c = self.classes.get(stack.pop(), {})
            for parent in ([c["is_a"]] if c.get("is_a") else []) + list(c.get("mixins") or []):
                if parent not in seen:
                    seen.add(parent)
                    stack.append(parent)
        return seen

    def conforms(self, categories: list[str], target: str | None) -> bool:
        if not target:
            return True
        for cat in categories:
            name = to_space(local(cat))
            if name == target or target in self.ancestors(name):
                return True
        return False

    def id_prefixes(self, category: str) -> list[str]:
        return list(self.classes.get(to_space(local(category)), {}).get("id_prefixes") or [])

    def enum_values(self, enum: str) -> set[str]:
        return set((self.enums.get(enum, {}).get("permissible_values") or {}).keys())


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def load_config(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    except FileNotFoundError as exc:
        raise InputError(f"Configuration not found: {path}") from exc
    for key in ("project", "biolink", "kinds", "predicates"):
        if key not in (cfg or {}):
            raise InputError(f"Configuration is missing the '{key}' section")
    return cfg


def load_records(path: str) -> list[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError as exc:
        raise InputError(f"Records file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"Records file is not valid JSON: {exc}") from exc
    records = data.get("records") if isinstance(data, dict) else data
    if not isinstance(records, list):
        raise InputError("Records file must be a list or an object with a 'records' list")
    return records


def choose_id(record: dict, categories: list[str], bl: Biolink) -> str:
    """Prefer a cross-reference in the category's preferred prefixes, then any Biolink-known prefix."""
    xrefs = [x for x in record.get("xrefs") or [] if prefix_of(x)]
    preferred = {p for c in categories for p in bl.id_prefixes(c)}
    for x in xrefs:
        if prefix_of(x) in preferred:
            return x
    for x in xrefs:
        if prefix_of(x) in bl.prefixes:
            return x
    return record["id"]


def export(cfg: dict, records: list[dict], bl: Biolink) -> dict:
    project = cfg["project"]
    kinds: dict = cfg["kinds"]
    predicates: dict = cfg["predicates"]
    report = {"biolink_version": bl.version, "skipped_records": [], "skipped_relations": [],
              "not_in_core": [], "counts": {}}

    ids: dict[str, str] = {}
    nodes: dict[str, dict] = {}
    seen_ids: set[str] = set()
    for i, r in enumerate(records):
        for field in ("id", "kind", "name"):
            if not r.get(field):
                raise InputError(f"Record #{i} is missing '{field}'")
        if r["id"] in seen_ids:
            raise InputError(f"Duplicate record id {r['id']}")
        seen_ids.add(r["id"])
        kind_cfg = kinds.get(r["kind"])
        if kind_cfg is None:
            raise InputError(f"Record {r['id']} has kind '{r['kind']}', not declared in the configuration")
        if kind_cfg.get("export") is False:
            report["skipped_records"].append({"id": r["id"], "reason": f"kind '{r['kind']}' is not exported"})
            continue
        categories = r.get("category") or kind_cfg.get("category") or []
        if not categories:
            raise InputError(f"Kind '{r['kind']}' has no Biolink category")
        node_id = choose_id(r, categories, bl)
        if node_id in nodes:
            # Two records claim the same standard identifier: keep the first, leave this one on its own id.
            report.setdefault("id_collisions", []).append(
                {"id": node_id, "records": [next(k for k, v in ids.items() if v == node_id), r["id"]]})
            node_id = r["id"]
        ids[r["id"]] = node_id
        xrefs = sorted({x for x in (r.get("xrefs") or []) + [r["id"]] if x != node_id})
        node = {"id": node_id, "category": list(categories), "name": r["name"]}
        if r.get("tldr"):
            node["description"] = r["tldr"]
        if xrefs:
            node["xref"] = xrefs
        node["provided_by"] = [project["primary_knowledge_source"]]
        nodes[node_id] = node

    edges: list[dict] = []
    for r in records:
        if r["id"] not in ids:
            continue
        for rel in r.get("relations") or []:
            name = rel.get("predicate")
            where = f"{r['id']} -[{name}]-> {rel.get('object')}"
            if name not in predicates:
                raise InputError(f"Relation {where}: predicate '{name}' is not declared in the configuration")
            if rel.get("object") not in ids:
                reason = ("object is not exported" if rel.get("object") in seen_ids
                          else "object does not exist (dangling reference)")
                report["skipped_relations"].append({"relation": where, "reason": reason})
                continue
            subject, obj, pred = ids[r["id"]], ids[rel["object"]], predicates[name]
            edge = {
                "id": "urn:uuid:" + str(uuid.uuid5(EDGE_NS, f"{subject}|{pred}|{obj}")),
                "subject": subject,
                "predicate": pred,
                "object": obj,
                "knowledge_level": rel.get("knowledgeLevel") or project["default_knowledge_level"],
                "agent_type": rel.get("agentType") or project["default_agent_type"],
                "primary_knowledge_source": rel.get("primarySource") or project["primary_knowledge_source"],
            }
            if rel.get("publications"):
                edge["publications"] = list(rel["publications"])
            if rel.get("quote"):
                edge["supporting_text"] = [rel["quote"]]
            edges.append(edge)

    core_ids = {nid for nid in nodes if prefix_of(nid) in bl.prefixes}
    for nid in sorted(set(nodes) - core_ids):
        report["not_in_core"].append({"id": nid, "reason": f"prefix '{prefix_of(nid) or nid}' is not in the "
                                      f"Biolink JSON-LD context; add a standard identifier to xrefs"})
    core_edges = [e for e in edges if e["subject"] in core_ids and e["object"] in core_ids]
    graphs = {
        "core": ([nodes[n] for n in sorted(core_ids)], core_edges),
        "full": ([nodes[n] for n in sorted(nodes)], edges),
    }
    report["counts"] = {k: {"nodes": len(v[0]), "edges": len(v[1])} for k, v in graphs.items()}
    return {"graphs": graphs, "report": report}


# ---------------------------------------------------------------------------
# Precheck (mirrors KGX validator rules, plus advisory domain/range warnings)
# ---------------------------------------------------------------------------

def precheck(nodes: list[dict], edges: list[dict], bl: Biolink) -> dict:
    errors, warnings = [], []
    levels = bl.enum_values("KnowledgeLevelEnum")
    agents = bl.enum_values("AgentTypeEnum")
    by_id = {n["id"]: n for n in nodes}

    def check_list_props(where: str, obj: dict):
        for key, value in obj.items():
            slot = bl.slots.get(to_space(key))
            if slot and slot.get("multivalued") and not isinstance(value, list):
                errors.append(f"{where}: property '{key}' must be a list")

    for n in nodes:
        nid = n.get("id", "")
        p = prefix_of(nid)
        if not p:
            errors.append(f"node {nid}: id is not a CURIE")
        elif p not in bl.prefixes:
            errors.append(f"node {nid}: prefix '{p}' is not in the Biolink JSON-LD context")
        cats = n.get("category")
        if not isinstance(cats, list) or not cats:
            errors.append(f"node {nid}: category must be a non-empty list")
            continue
        for c in cats:
            name = local(c)
            cls = bl.classes.get(to_space(name))
            if not CAMEL.match(name):
                errors.append(f"node {nid}: category '{c}' is not CamelCase")
            elif cls is None:
                errors.append(f"node {nid}: category '{c}' is not in Biolink {bl.version}")
            elif cls.get("mixin"):
                errors.append(f"node {nid}: category '{c}' is a mixin, not a class")
        check_list_props(f"node {nid}", n)

    for e in edges:
        where = f"edge {e.get('subject')} -[{e.get('predicate')}]-> {e.get('object')}"
        for prop in REQUIRED_EDGE_PROPS:
            if not e.get(prop):
                errors.append(f"{where}: missing required property '{prop}'")
        for end in ("subject", "object"):
            p = prefix_of(e.get(end, ""))
            if not p:
                errors.append(f"{where}: {end} is not a CURIE")
            elif p not in bl.prefixes:
                errors.append(f"{where}: {end} prefix '{p}' is not in the Biolink JSON-LD context")
        pred = local(e.get("predicate", ""))
        slot = bl.slots.get(to_space(pred))
        if not SNAKE.match(pred):
            errors.append(f"{where}: predicate is not snake_case")
        elif slot is None:
            errors.append(f"{where}: predicate '{pred}' is not in Biolink {bl.version}")
        if e.get("knowledge_level") and e["knowledge_level"] not in levels:
            errors.append(f"{where}: knowledge_level '{e['knowledge_level']}' is not a Biolink value")
        if e.get("agent_type") and e["agent_type"] not in agents:
            errors.append(f"{where}: agent_type '{e['agent_type']}' is not a Biolink value")
        check_list_props(where, e)
        if slot and e.get("subject") in by_id and e.get("object") in by_id:
            if not bl.conforms(by_id[e["subject"]]["category"], slot.get("domain")):
                warnings.append(f"{where}: Biolink expects the subject to be a '{slot.get('domain')}'")
            if not bl.conforms(by_id[e["object"]]["category"], slot.get("range")):
                warnings.append(f"{where}: Biolink expects the object to be a '{slot.get('range')}'")
        if e.get("knowledge_level") == "knowledge_assertion" and not e.get("publications"):
            warnings.append(f"{where}: knowledge assertion without publications")
    return {"errors": errors, "warnings": warnings}


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_jsonl(path: Path, rows: list[dict]):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_tsv(path: Path, rows: list[dict]):
    lead = ["id", "category", "name", "subject", "predicate", "object"]
    cols = sorted({k for r in rows for k in r}, key=lambda k: (lead.index(k) if k in lead else len(lead), k))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            cells = []
            for c in cols:
                v = r.get(c, "")
                v = "|".join(v) if isinstance(v, list) else str(v)
                cells.append(v.replace("\t", " ").replace("\n", " "))
            f.write("\t".join(cells) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", required=True)
    ap.add_argument("--records", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--biolink-dir", help="local folder holding the pinned Biolink model and JSON-LD context")
    ap.add_argument("--format", choices=["jsonl", "tsv"], default="jsonl")
    ap.add_argument("--no-precheck", action="store_true")
    args = ap.parse_args(argv)

    try:
        cfg = load_config(args.config)
        b = cfg["biolink"]
        bl = Biolink.load(str(b["version"]), b["model_url"], b["context_url"], args.biolink_dir)
        result = export(cfg, load_records(args.records), bl)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    writer = write_jsonl if args.format == "jsonl" else write_tsv
    for scope, (nodes, edges) in result["graphs"].items():
        writer(out / f"{scope}_nodes.{args.format}", nodes)
        writer(out / f"{scope}_edges.{args.format}", edges)

    report = result["report"]
    status = 0
    if not args.no_precheck:
        report["precheck"] = {scope: precheck(*g, bl) for scope, g in result["graphs"].items()}
        core = report["precheck"]["core"]
        if core["errors"]:
            status = 1
    (out / "export_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    c = report["counts"]
    print(f"Biolink {bl.version}: core {c['core']['nodes']} nodes / {c['core']['edges']} edges; "
          f"full {c['full']['nodes']} nodes / {c['full']['edges']} edges -> {out}")
    if not args.no_precheck:
        for scope in ("core", "full"):
            pc = report["precheck"][scope]
            print(f"precheck {scope}: {len(pc['errors'])} errors, {len(pc['warnings'])} warnings")
        for line in report["precheck"]["core"]["errors"][:20]:
            print(f"  ERROR {line}")
    return status


if __name__ == "__main__":
    sys.exit(main())
