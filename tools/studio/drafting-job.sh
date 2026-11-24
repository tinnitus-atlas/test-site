#!/usr/bin/env bash
# Daily drafting job for a computer that runs a local model server (for example LM Studio).
# Started by the scheduled job in drafting.plist.template: daily, and again at login, so a run missed while the
# computer was off or asleep happens as soon as it is back. Does nothing when there is nothing approved to draft.
#
# Settings come from a file outside the repository (default ~/.config/kg-drafting.env, permissions 600):
#   REPO_DIR=/absolute/path/to/a/clone/of/the/repository
#   DRAFTER_BASE_URL=http://localhost:1234/v1      # LM Studio's local server
#   DRAFTER_MODEL=<model id exactly as GET $DRAFTER_BASE_URL/models lists it>
# The clone must be able to push branches and use the GitHub CLI (gh) as the trusted bot account.
set -uo pipefail

ENV_FILE="${KG_DRAFTING_ENV:-$HOME/.config/kg-drafting.env}"
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }

[ -f "$ENV_FILE" ] || { log "settings file $ENV_FILE not found; nothing done"; exit 2; }
# shellcheck disable=SC1090
. "$ENV_FILE"
: "${REPO_DIR:?REPO_DIR missing in $ENV_FILE}" "${DRAFTER_BASE_URL:?DRAFTER_BASE_URL missing}" "${DRAFTER_MODEL:?DRAFTER_MODEL missing}"
export DRAFTER_BASE_URL DRAFTER_MODEL
[ -n "${DRAFTER_API_KEY:-}" ] && export DRAFTER_API_KEY

# The model server must be up; if not, stop quietly: the next scheduled run or login tries again.
if ! curl -fsS --max-time 5 "$DRAFTER_BASE_URL/models" >/dev/null 2>&1; then
  log "model server not reachable at $DRAFTER_BASE_URL; will try again at the next run"
  exit 0
fi

cd "$REPO_DIR" || { log "REPO_DIR $REPO_DIR not found"; exit 2; }
log "drafting with $DRAFTER_MODEL"
./run_drafts.sh
code=$?
log "finished with exit code $code"
exit $code
