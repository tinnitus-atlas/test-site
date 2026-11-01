#!/usr/bin/env python3
"""
MCP server for the knowledge graph (stdio transport, no dependencies).

Lets AI agents search and read the published records. It reads the site's JSON API, either from a local
build folder or from the live site.

Tools: search_records, get_record, related_records, list_kinds.

Run:   python3 mcp/server.py --data public/api/v1            (local build)
       python3 mcp/server.py --url https://example.org/api/v1 (live site)
Client configuration example (JSON used by most MCP clients):
  {"mcpServers": {"knowledge-graph": {"command": "python3", "args": ["/path/to/mcp/server.py", "--url", "https://example.org/api/v1"]}}}
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

SERVER = {"name": "knowledge-graph", "version": "0.1.0"}
TOOLS = [
    {"name": "search_records", "description": "Search records by words in their name or summary. Optionally limit to one kind (for example intervention, trial, device).",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "kind": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 50}}, "required": ["query"]}},
    {"name": "get_record", "description": "Get one record in full, with its sourced relationships, quotes and sources. Accepts the record id (for example tin:cbt).",
     "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}},
    {"name": "related_records", "description": "List records linked to or from a record, with the relationship and its evidence level.",
     "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}},
    {"name": "list_kinds", "description": "List the kinds of records and how many of each exist.",
     "inputSchema": {"type": "object", "properties": {}}},
]


class Data:
    def __init__(self, folder: str | None, url: str | None):
        if folder:
            payload = json.loads((Path(folder) / "records.json").read_text(encoding="utf-8"))
        else:
            with urllib.request.urlopen(url.rstrip("/") + "/records.json", timeout=30) as r:
                payload = json.loads(r.read().decode("utf-8"))
        self.attribution = payload.get("attribution", "")
        self.records = payload.get("records", [])
        self.by_id = {r["id"]: r for r in self.records}

    def search(self, query: str, kind: str | None = None, limit: int = 10) -> list[dict]:
        words = [w for w in query.lower().split() if w]
        out = []
        for r in self.records:
            if kind and r.get("kind") != kind:
                continue
            hay = f"{r.get('name', '')} {r.get('tldr', '')}".lower()
            score = sum(hay.count(w) for w in words) + (3 if query.lower() in r.get("name", "").lower() else 0)
            if score:
                out.append((score, r))
        out.sort(key=lambda x: -x[0])
        return [{"id": r["id"], "name": r["name"], "kind": r["kind"], "tldr": r.get("tldr"), "url": r.get("url"),
                 "asOf": r.get("asOf")} for _, r in out[:limit]]

    def related(self, rid: str) -> list[dict]:
        r = self.by_id[rid]
        out = [{"direction": "outgoing", "predicate": rel["predicate"], "id": rel["object"],
                "name": self.by_id.get(rel["object"], {}).get("name"), "knowledgeLevel": rel.get("knowledgeLevel"),
                "quote": rel.get("quote")} for rel in r.get("relations") or []]
        out += [{"direction": "incoming", "predicate": l["predicate"], "id": l["id"], "name": self.by_id.get(l["id"], {}).get("name")}
                for l in r.get("linkedFrom") or []]
        return out


def handle(data: Data, msg: dict) -> dict | None:
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:  # notification, no reply
        return None

    def ok(result):
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    if method == "initialize":
        version = (msg.get("params") or {}).get("protocolVersion") or "2025-06-18"
        return ok({"protocolVersion": version, "capabilities": {"tools": {}}, "serverInfo": SERVER,
                   "instructions": "Open, cited knowledge graph. Not medical advice. Cite the record url and the attribution line."})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        params = msg.get("params") or {}
        name, args = params.get("name"), params.get("arguments") or {}
        try:
            if name == "search_records":
                result = data.search(str(args["query"]), args.get("kind"), int(args.get("limit", 10)))
            elif name == "get_record":
                if args["id"] not in data.by_id:
                    raise KeyError(f"No record with id {args['id']}")
                result = data.by_id[args["id"]]
            elif name == "related_records":
                if args["id"] not in data.by_id:
                    raise KeyError(f"No record with id {args['id']}")
                result = data.related(args["id"])
            elif name == "list_kinds":
                counts: dict = {}
                for r in data.records:
                    counts[r["kind"]] = counts.get(r["kind"], 0) + 1
                result = counts
            else:
                return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"Unknown tool {name}"}}
            text = json.dumps({"attribution": data.attribution, "result": result}, ensure_ascii=False, indent=1)
            return ok({"content": [{"type": "text", "text": text}], "isError": False})
        except (KeyError, ValueError, TypeError) as exc:
            return ok({"content": [{"type": "text", "text": str(exc).strip("'\"")}], "isError": True})
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--data", help="folder holding records.json (a local site build's api/v1)")
    src.add_argument("--url", help="base URL of the live API, for example https://example.org/api/v1")
    args = ap.parse_args(argv)
    data = Data(args.data, args.url)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            reply = handle(data, msg)
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
