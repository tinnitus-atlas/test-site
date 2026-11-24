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

# LM Studio's command-line tool, if installed: used to start the server and load the model with fixed settings, so
# neither depends on the app's "start on login" setting or on per-model presets (which on-demand loading has been
# reported to ignore). Optional settings: LMS_BIN, DRAFTER_CONTEXT (default 16384).
LMS="${LMS_BIN:-$(command -v lms 2>/dev/null || echo "$HOME/.lmstudio/bin/lms")}"
[ -x "$LMS" ] || LMS=""
AUTH=()
[ -n "${DRAFTER_API_KEY:-}" ] && AUTH=(-H "Authorization: Bearer $DRAFTER_API_KEY")
server_up() { curl -fsS --max-time 5 ${AUTH[@]+"${AUTH[@]}"} "$DRAFTER_BASE_URL/models" >/dev/null 2>&1; }

if ! server_up && [ -n "$LMS" ]; then
  log "model server not running; starting it"
  "$LMS" server start >/dev/null 2>&1 || true
  sleep 5
fi
# The model server must be up; if not, stop quietly: the next scheduled run or login tries again.
if ! server_up; then
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$DRAFTER_BASE_URL/models" 2>/dev/null || echo 000)"
  if [ "$code" = "401" ] || [ "$code" = "403" ]; then
    log "model server requires an API key: set DRAFTER_API_KEY in $ENV_FILE"
    exit 2
  fi
  log "model server not reachable at $DRAFTER_BASE_URL; will try again at the next run"
  exit 0
fi
if [ -n "$LMS" ] && ! "$LMS" ps 2>/dev/null | grep -qF "$DRAFTER_MODEL"; then
  log "loading the drafting model"
  "$LMS" load "$DRAFTER_MODEL" --context-length "${DRAFTER_CONTEXT:-16384}" -y >/dev/null 2>&1 \
    || log "could not load the model with fixed settings; the server will load it on the first request"
fi

cd "$REPO_DIR" || { log "REPO_DIR $REPO_DIR not found"; exit 2; }
log "drafting with $DRAFTER_MODEL"
./run_drafts.sh
code=$?
log "finished with exit code $code"
# Publish a privacy-safe readiness report (no paths, names or model ids) so nobody has to relay it by hand.
bash "$REPO_DIR/tools/studio/doctor.sh" --publish --last-exit "$code" >/dev/null 2>&1 || true
exit $code
