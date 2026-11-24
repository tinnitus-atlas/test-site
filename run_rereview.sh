#!/usr/bin/env bash
# Re-review: sends an earlier proposals pull request through the screener again and opens one pull request titled
# "Nightly proposals re-review #<old> (<n>)". Merging it settles the old pull request.
# Usage: ./run_rereview.sh <pull request number> [only-skipped]
# Standard output: one result line plus the pull request line. Exit 0 done, 2 failed.
set -uo pipefail
cd "$(dirname "$0")"

PR="${1:-}"
case "$PR" in ''|*[!0-9]*) echo "Re-review FAILED: give the number of a proposals pull request"; exit 2;; esac
ONLY=""
[ "${2:-}" = "only-skipped" ] && ONLY="--only-skipped"

CONFIG="${CONFIG:-kit.tinnitus.yaml}"
RECORDS="${RECORDS:-records/tinnitus.records.json}"
REPORTS="${REPORTS:-reports}"
LOG="$REPORTS/rereview.log"
mkdir -p "$REPORTS"
: > "$LOG"

RESULT="$(python3 -m kgkit.rereview --config "$CONFIG" --records "$RECORDS" --reports "$REPORTS" --pr "$PR" $ONLY 2>>"$LOG")" \
  || { echo "Re-review FAILED: see $LOG"; tail -n 20 "$LOG"; exit 2; }
echo "Re-review of #$PR: $RESULT"
COUNT="$(python3 -c "import json;print(json.load(open('$REPORTS/proposals.json')).get('count',0))" 2>/dev/null || echo 0)"
if [ "${NO_GIT:-0}" = "1" ]; then echo "Pull request: none (git disabled for this run)"; exit 0; fi
if [ "$COUNT" -eq 0 ]; then echo "Pull request: none (nothing left to review)"; exit 0; fi

BRANCH="proposals/rereview-$PR"
TITLE="Nightly proposals re-review #$PR ($COUNT)"
{
  git checkout -q -B "$BRANCH" &&
  git add -f "$REPORTS/proposals.json" "$REPORTS/proposals.md" &&
  git commit -q -m "$TITLE" &&
  git push -q -f origin "$BRANCH"
} >>"$LOG" 2>&1 || { echo "Pull request: could not push branch $BRANCH (see $LOG)"; exit 2; }
URL="$(gh pr view "$BRANCH" --json url -q .url 2>/dev/null || gh pr create --head "$BRANCH" --base main \
       --title "$TITLE" --body-file "$REPORTS/proposals.md" 2>>"$LOG" | tail -n 1)"
echo "Pull request: ${URL:-could not be created (see $LOG)}"
git checkout -q main >>"$LOG" 2>&1 || true
[ -n "$URL" ] || exit 2
