#!/usr/bin/env python3
"""
Run the official KGX validator against the Biolink release the project uses.

KGX 2.7.0 checks identifier prefixes against a built-in copy of the Biolink 2.2.5 prefix list, even when
--biolink-release names a newer release, so prefixes added since (CLINICALTRIALS, for example) are wrongly
rejected. This wrapper gives KGX the prefix list of the configured release, then runs its normal validation.

Usage: python3 tools/kgx_validate.py --release 4.4.6 --context path/to/biolink_model.context.jsonld \
           --output out/kgx_validation.json nodes.jsonl edges.jsonl
Exit codes: 0 valid; 1 errors found; 2 bad input.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--release", required=True, help="Biolink release, e.g. 4.4.6")
    ap.add_argument("--context", required=True, help="that release's biolink_model.context.jsonld")
    ap.add_argument("--output", required=True)
    ap.add_argument("inputs", nargs="+")
    args = ap.parse_args(argv)
    ctx_path = Path(args.context)
    if not ctx_path.is_file():
        print(f"error: context file not found: {ctx_path}", file=sys.stderr)
        return 2
    ctx = json.loads(ctx_path.read_text(encoding="utf-8"))

    from kgx import config  # imported here so --help works without KGX installed
    config.jsonld_context_map["biolink"] = ctx.get("@context", ctx)
    from kgx.cli.cli_utils import validate

    release = args.release if args.release.startswith("v") else f"v{args.release}"
    errors = validate(inputs=args.inputs, input_format="jsonl", input_compression=None,
                      output=args.output, biolink_release=release)
    return 1 if (errors or {}).get("ERROR") else 0


if __name__ == "__main__":
    sys.exit(main())
