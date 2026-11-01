#!/usr/bin/env bash
# Export records to Biolink KGX files, then validate the core graph with the official KGX validator.
#
# Usage:  ./run_validation.sh path/to/records.json
# Env:    CONFIG (default kit.tinnitus.yaml), OUT (default out), BIOLINK_DIR (optional local Biolink checkout)
# Exit:   0 valid; 1 precheck or KGX found errors; 2 bad input; 3 KGX not installed
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: ./run_validation.sh path/to/records.json" >&2
  exit 2
fi
# Resolve the records path before moving into the project folder, so relative paths keep working.
RECORDS="$1"
if RDIR="$(cd "$(dirname "$1")" 2>/dev/null && pwd)"; then RECORDS="$RDIR/$(basename "$1")"; fi
cd "$(dirname "$0")"
CONFIG="${CONFIG:-kit.tinnitus.yaml}"
OUT="${OUT:-out}"

python3 export_biolink.py --config "$CONFIG" --records "$RECORDS" --out "$OUT" \
  ${BIOLINK_DIR:+--biolink-dir "$BIOLINK_DIR"}

VERSION="$(python3 -c "import sys, yaml; print(yaml.safe_load(open(sys.argv[1]))['biolink']['version'])" "$CONFIG")"

if ! command -v kgx >/dev/null 2>&1; then
  echo "KGX is not installed, so only the precheck ran. Install it with: pip install kgx==2.7.0" >&2
  exit 3
fi

echo "Running KGX validator (Biolink $VERSION) on the core graph..."
if kgx validate --input-format jsonl --biolink-release "$VERSION" \
     --output "$OUT/kgx_validation.json" "$OUT/core_nodes.jsonl" "$OUT/core_edges.jsonl"; then
  echo "KGX validation passed. Report: $OUT/kgx_validation.json"
else
  echo "KGX validation found errors. Report: $OUT/kgx_validation.json" >&2
  exit 1
fi
