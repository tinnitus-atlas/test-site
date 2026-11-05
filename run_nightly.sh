#!/usr/bin/env bash
# Nightly run: update the repository, run feeds and checks, export to Biolink, open a pull request with
# the proposals, and write reports/nightly.md for the scheduler to post.
#
# Env (all optional):
#   CONFIG   default kit.tinnitus.yaml
#   RECORDS  default records/tinnitus.records.json
#   NO_GIT=1 skip git pull, branch and pull request (local runs and tests)
# Exit: 0 all clear; 1 blocking findings (records held, freshness breach or export errors); 2 the run itself failed
set -uo pipefail
cd "$(dirname "$0")"

CONFIG="${CONFIG:-kit.tinnitus.yaml}"
RECORDS="${RECORDS:-records/tinnitus.records.json}"
REPORTS="reports"
DAY="$(date +%Y-%m-%d)"
mkdir -p "$REPORTS"
LOG="$REPORTS/nightly.log"
: > "$LOG"

fail() { echo "RUN FAILED: $1" | tee -a "$LOG"; { echo "Status: RUN FAILED"; echo "$1"; echo; tail -n 20 "$LOG"; } > "$REPORTS/nightly.md"; exit 2; }

APPLY_LINE="Approved proposals: not checked (git disabled)"
if [ "${NO_GIT:-0}" != "1" ]; then
  # Reports are regenerated every night; discard last night's local copies so the update cannot conflict.
  git checkout -q -- "$REPORTS" 2>/dev/null || true
  git checkout -q main >>"$LOG" 2>&1 && git pull -q --ff-only origin main >>"$LOG" 2>&1 || fail "git pull failed"

  # Do not apply the same proposals twice while the previous apply pull request is still open.
  OPEN_APPLY=0
  if command -v gh >/dev/null 2>&1; then
    OPEN_APPLY="$(gh pr list --state open --search "Apply approved proposals in:title" --json number -q length 2>/dev/null || echo 0)"
  fi
  case "$OPEN_APPLY" in
    ''|*[!0-9]*) OPEN_APPLY=0;;
  esac

  if [ "$OPEN_APPLY" -gt 0 ]; then
    APPLY_LINE="Approved proposals: waiting, the previous apply pull request is still open"
  else
    # Apply proposals ticked and merged since the last run, then publish them through a pull request.
    python3 -m kgkit.apply --config "$CONFIG" --records "$RECORDS" --from-github >>"$LOG" 2>&1
    case $? in
      0)
        if [ -n "$(git status --porcelain -- "$(dirname "$RECORDS")")" ]; then
          URL="$(tools/publish_via_pr.sh "nightly/apply-$DAY" "Apply approved proposals $DAY" "$(dirname "$RECORDS")" 2>>"$LOG")"
          case $? in
            0) APPLY_LINE="Approved proposals: applied; pull request $URL merges itself once the checks pass";;
            3) APPLY_LINE="Approved proposals: applied; pull request $URL needs a manual merge (auto-merge unavailable)";;
            *) fail "could not publish applied proposals";;
          esac
        else
          APPLY_LINE="Approved proposals: none newly approved"
        fi;;
      1) APPLY_LINE="Approved proposals: NOT applied, they would break the audit (see reports/nightly.log)";;
      *) APPLY_LINE="Approved proposals: could not read merged pull requests (see reports/nightly.log)";;
    esac
  fi
fi

python3 -m kgkit --config "$CONFIG" --records "$RECORDS" --reports "$REPORTS" >>"$LOG" 2>&1
CHECKS=$?
[ "$CHECKS" -eq 2 ] && fail "checks could not read the configuration or records"

# Publish the held list next to the records so the website build withholds the same records.
HELD_LINE="Website: held list unchanged"
HELD_DEST="$(dirname "$RECORDS")/held_records.json"
python3 -c "import json,sys;d=json.load(open(sys.argv[1]));json.dump({'held_records':d.get('held_records',[])},open(sys.argv[2],'w'),indent=2)" \
  "$REPORTS/held_records.json" "$HELD_DEST" >>"$LOG" 2>&1
if [ "${NO_GIT:-0}" != "1" ] && [ -n "$(git status --porcelain -- "$HELD_DEST")" ]; then
  URL="$(tools/publish_via_pr.sh "nightly/held-$DAY" "Update held records $DAY" "$HELD_DEST" 2>>"$LOG")"
  case $? in
    0) HELD_LINE="Website: held list goes through pull request $URL, which merges itself once the checks pass";;
    3) HELD_LINE="Website: held list goes through pull request $URL and needs a manual merge (auto-merge unavailable)";;
    *) HELD_LINE="Website: could not publish the held list (see reports/nightly.log)";;
  esac
fi

OUT="exports" ./run_validation.sh "$RECORDS" >>"$LOG" 2>&1
EXPORT=$?
case "$EXPORT" in
  0) EXPORT_LINE="Biolink export: valid (KGX passed)";;
  1) EXPORT_LINE="Biolink export: ERRORS, see exports/export_report.json and exports/kgx_validation.json";;
  3) EXPORT_LINE="Biolink export: precheck only (KGX not installed)";;
  *) EXPORT_LINE="Biolink export: FAILED to run (exit $EXPORT)";;
esac

COUNT="$(python3 -c "import json;print(json.load(open('$REPORTS/proposals.json')).get('count',0))" 2>/dev/null || echo 0)"
{
  echo "Nightly run $DAY"
  if [ "$EXPORT" -eq 0 ] || [ "$EXPORT" -eq 3 ]; then cat "$REPORTS/summary.md"
  else sed 's/^Status: all clear$/Status: Biolink export problems (checks otherwise clear)/' "$REPORTS/summary.md"; fi
  echo "$APPLY_LINE"
  echo "$HELD_LINE"
  echo "$EXPORT_LINE"
  echo
  echo "Top proposals:"
  python3 - "$REPORTS/proposals.json" <<'EOF'
import json, sys
props = json.load(open(sys.argv[1])).get("proposals", [])
for i, p in enumerate(props[:10], 1):
    print(f"{i}. [{p['confidence']}] {p['claim'][:140]}")
if len(props) > 10:
    print(f"... and {len(props) - 10} more in the pull request")
if not props:
    print("none")
EOF
} > "$REPORTS/nightly.md"


PR_LINE="No pull request (no proposals)"
if [ "${NO_GIT:-0}" != "1" ] && [ "$COUNT" -gt 0 ]; then
  BRANCH="proposals/$DAY"
  {
    git checkout -q -B "$BRANCH" &&
    git add "$REPORTS"/*.json "$REPORTS"/proposals.md &&
    git commit -q -m "Nightly proposals $DAY ($COUNT)" &&
    git push -q -f origin "$BRANCH"
  } >>"$LOG" 2>&1 || PR_LINE="Pull request: could not push branch $BRANCH (see reports/nightly.log)"
  if [ "$PR_LINE" = "No pull request (no proposals)" ]; then
    if command -v gh >/dev/null 2>&1; then
      URL="$(gh pr view "$BRANCH" --json url -q .url 2>/dev/null || gh pr create --head "$BRANCH" --base main \
             --title "Nightly proposals $DAY ($COUNT)" --body-file "$REPORTS/proposals.md" 2>>"$LOG" | tail -n 1)"
      PR_LINE="Pull request: ${URL:-could not be created (see reports/nightly.log)}"
    else
      PR_LINE="Pull request: branch $BRANCH pushed; GitHub CLI not installed, open the pull request by hand"
    fi
  fi
  git checkout -q main >>"$LOG" 2>&1
fi

[ "${NO_GIT:-0}" = "1" ] && [ "$COUNT" -gt 0 ] && PR_LINE="No pull request (git disabled for this run)"
echo "$PR_LINE" >> "$REPORTS/nightly.md"

cat "$REPORTS/nightly.md"
if [ "$CHECKS" -eq 1 ] || [ "$EXPORT" -eq 1 ]; then exit 1; fi
exit 0
