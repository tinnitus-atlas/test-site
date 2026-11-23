#!/usr/bin/env bash
# Drafting step: drafts finished entries for bare records and opens one pull request titled
# "Nightly proposals drafts <date> (<n>)", reviewed and applied like every other proposals pull request.
# Runs where the drafting model is reachable (for example the agent server); needs DRAFTER_BASE_URL and
# DRAFTER_MODEL (and DRAFTER_API_KEY for a hosted model) in the environment, plus git and gh with push access.
# Usage: ./run_drafts.sh [cap]   (default from the configuration, drafting.cap)
# Standard output: the run report (Markdown) plus the pull request line. Exit 0 done, 2 failed.
set -uo pipefail
cd "$(dirname "$0")"

CAP_ARG=""
if [ -n "${1:-}" ]; then
  case "$1" in *[!0-9]*) echo "Drafting FAILED: cap must be a whole number"; exit 2;; esac
  CAP_ARG="--cap $1"
fi

CONFIG="${CONFIG:-kit.tinnitus.yaml}"
RECORDS="${RECORDS:-records/tinnitus.records.json}"
REPORTS="${REPORTS:-reports}"
DAY="$(date -u +%Y-%m-%d)"
LOG="$REPORTS/drafts.log"
mkdir -p "$REPORTS"
: > "$LOG"

if [ "${NO_GIT:-0}" != "1" ]; then
  git checkout -q main >>"$LOG" 2>&1 && git pull -q --ff-only origin main >>"$LOG" 2>&1 \
    || { echo "Drafting FAILED: git pull failed (see $LOG)"; exit 2; }
fi

python3 -m kgkit.draft --config "$CONFIG" --records "$RECORDS" --reports "$REPORTS" $CAP_ARG >>"$LOG" 2>&1 \
  || { echo "Drafting FAILED: see $LOG"; tail -n 20 "$LOG"; exit 2; }

cat "$REPORTS/draft_run.md"
COUNT="$(python3 -c "import json;print(json.load(open('$REPORTS/proposals.json')).get('count',0))" 2>/dev/null || echo 0)"

if [ "${NO_GIT:-0}" = "1" ]; then
  echo "Pull request: none (git disabled for this run)"
  exit 0
fi
if [ "$COUNT" -eq 0 ]; then
  echo "Pull request: none (no proposals)"
  exit 0
fi

BRANCH="proposals/drafts-$DAY"
TITLE="Nightly proposals drafts $DAY ($COUNT)"
{
  git checkout -q -B "$BRANCH" &&
  git add -f "$REPORTS/proposals.json" "$REPORTS/proposals.md" "$REPORTS/draft_run.md" &&
  { [ ! -f "$(dirname "$RECORDS")/draft_queue.json" ] || git add "$(dirname "$RECORDS")/draft_queue.json"; } &&
  git commit -q -m "$TITLE" &&
  git push -q -f origin "$BRANCH"
} >>"$LOG" 2>&1 || { echo "Pull request: could not push branch $BRANCH (see $LOG)"; exit 2; }

URL="$(gh pr view "$BRANCH" --json url -q .url 2>/dev/null || gh pr create --head "$BRANCH" --base main \
       --title "$TITLE" --body-file "$REPORTS/proposals.md" 2>>"$LOG" | tail -n 1)"
echo "Pull request: ${URL:-could not be created (see $LOG)}"
git checkout -q main >>"$LOG" 2>&1 || true
[ -n "$URL" ] || exit 2
exit 0
