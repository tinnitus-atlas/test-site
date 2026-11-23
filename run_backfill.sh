#!/usr/bin/env bash
# One-off backfill: writes the proposals and opens one pull request titled "Nightly proposals backfill <date> (<n>)".
# Usage: ./run_backfill.sh [since_days] [until_days] [paper_cap]   (defaults 183 30 30)
# Standard output: the pilot report (Markdown) plus the pull request line. Exit 0 done, 2 failed.
set -uo pipefail
cd "$(dirname "$0")"

SINCE="${1:-183}"
UNTIL="${2:-30}"
CAP="${3:-30}"
for v in "$SINCE" "$UNTIL" "$CAP"; do
  case "$v" in ''|*[!0-9]*) echo "Backfill FAILED: window and cap must be whole numbers" ; exit 2;; esac
done

CONFIG="${CONFIG:-kit.tinnitus.yaml}"
RECORDS="${RECORDS:-records/tinnitus.records.json}"
REPORTS="${REPORTS:-reports}"
DAY="$(date -u +%Y-%m-%d)"
LOG="$REPORTS/backfill.log"
mkdir -p "$REPORTS"
: > "$LOG"

OPEN_FLAG=""
command -v gh >/dev/null 2>&1 && [ "${NO_GIT:-0}" != "1" ] && OPEN_FLAG="--open-prs"

python3 -m kgkit.backfill --config "$CONFIG" --records "$RECORDS" --reports "$REPORTS" \
  --since-days "$SINCE" --until-days "$UNTIL" --paper-cap "$CAP" $OPEN_FLAG >>"$LOG" 2>&1 \
  || { echo "Backfill FAILED: see $LOG"; tail -n 20 "$LOG"; exit 2; }

cat "$REPORTS/backfill_pilot.md"
COUNT="$(python3 -c "import json;print(json.load(open('$REPORTS/proposals.json')).get('count',0))" 2>/dev/null || echo 0)"

if [ "${NO_GIT:-0}" = "1" ]; then
  echo "Pull request: none (git disabled for this run)"
  exit 0
fi
if [ "$COUNT" -eq 0 ]; then
  echo "Pull request: none (no proposals)"
  exit 0
fi

BRANCH="proposals/backfill-$DAY"
TITLE="Nightly proposals backfill $DAY ($COUNT)"
{
  git checkout -q -B "$BRANCH" &&
  git add -f "$REPORTS/proposals.json" "$REPORTS/proposals.md" "$REPORTS/feeds.json" \
             "$REPORTS/backfill_queue.json" "$REPORTS/backfill_pilot.md" &&
  git commit -q -m "$TITLE" &&
  git push -q -f origin "$BRANCH"
} >>"$LOG" 2>&1 || { echo "Pull request: could not push branch $BRANCH (see $LOG)"; exit 2; }

URL="$(gh pr view "$BRANCH" --json url -q .url 2>/dev/null || gh pr create --head "$BRANCH" --base main \
       --title "$TITLE" --body-file "$REPORTS/proposals.md" 2>>"$LOG" | tail -n 1)"
echo "Pull request: ${URL:-could not be created (see $LOG)}"
git checkout -q main >>"$LOG" 2>&1 || true
[ -n "$URL" ] || exit 2
exit 0
