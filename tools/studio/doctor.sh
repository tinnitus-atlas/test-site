#!/usr/bin/env bash
# Readiness check for the drafting computer. Prints one line per check; with --publish it also saves the result as
# status/studio.json on the studio-status branch, where the maintainers read it (nobody relays it by hand).
# The report holds only yes/no answers and times: no paths, user names, machine names or model ids.
set -uo pipefail
PUBLISH=0; LAST_EXIT=""
while [ $# -gt 0 ]; do
  case "$1" in --publish) PUBLISH=1 ;; --last-exit) LAST_EXIT="$2"; shift ;; esac
  shift
done
ENV_FILE="${KG_DRAFTING_ENV:-$HOME/.config/kg-drafting.env}"
yes_no() { if "$@"; then echo yes; else echo no; fi; }

settings=$(yes_no test -f "$ENV_FILE")
perms=no
if [ "$settings" = yes ]; then
  [ "$(stat -f %Lp "$ENV_FILE" 2>/dev/null || stat -c %a "$ENV_FILE" 2>/dev/null)" = "600" ] && perms=yes
  # shellcheck disable=SC1090
  . "$ENV_FILE"
fi
LMS="${LMS_BIN:-$(command -v lms 2>/dev/null || echo "$HOME/.lmstudio/bin/lms")}"
lms=$(yes_no test -x "$LMS")
AUTH=()
[ -n "${DRAFTER_API_KEY:-}" ] && AUTH=(-H "Authorization: Bearer $DRAFTER_API_KEY")
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 ${AUTH[@]+"${AUTH[@]}"} "${DRAFTER_BASE_URL:-http://localhost:1234/v1}/models" 2>/dev/null)"
server=no; key_ok=n/a
case "$code" in 200) server=yes; key_ok=yes ;; 401|403) server=yes; key_ok=no ;; esac
loaded=unknown
if [ "$lms" = yes ] && [ -n "${DRAFTER_MODEL:-}" ]; then
  loaded=$(yes_no sh -c "'$LMS' ps 2>/dev/null | grep -qF -- '$DRAFTER_MODEL'")
fi
listens_local=unknown
if command -v lsof >/dev/null 2>&1; then
  port="$(echo "${DRAFTER_BASE_URL:-http://localhost:1234/v1}" | sed -E 's#.*:([0-9]+).*#\1#')"
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | grep -q LISTEN; then
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | grep -Eq '\*:|0\.0\.0\.0:'; then listens_local=no; else listens_local=yes; fi
  fi
fi
scheduled=$(yes_no sh -c "launchctl list 2>/dev/null | grep -q org.kg.drafting")
now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

cat <<OUT
Settings file present: $settings
Settings file private (600): $perms
LM Studio command-line tool found: $lms
Model server answering: $server
API key accepted (if one is required): $key_ok
Drafting model loaded: $loaded
Model server only on this computer: $listens_local
Daily job scheduled: $scheduled
Last job exit code: ${LAST_EXIT:-not given}
Checked at: $now
OUT

[ "$PUBLISH" = 1 ] || exit 0
[ -n "${REPO_DIR:-}" ] && cd "$REPO_DIR" 2>/dev/null || exit 0
json=$(printf '{"checked_at":"%s","settings":"%s","settings_private":"%s","lms":"%s","server":"%s","key_ok":"%s","model_loaded":"%s","local_only":"%s","scheduled":"%s","last_exit":"%s"}\n' \
  "$now" "$settings" "$perms" "$lms" "$server" "$key_ok" "$loaded" "$listens_local" "$scheduled" "${LAST_EXIT:-}")
repo="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)" || exit 0
if ! gh api "repos/$repo/branches/studio-status" >/dev/null 2>&1; then
  main_sha="$(gh api "repos/$repo/git/ref/heads/main" -q .object.sha)" || exit 0
  gh api "repos/$repo/git/refs" -f ref=refs/heads/studio-status -f sha="$main_sha" >/dev/null || exit 0
fi
old="$(gh api "repos/$repo/contents/status/studio.json?ref=studio-status" -q .sha 2>/dev/null || true)"
args=(-X PUT "repos/$repo/contents/status/studio.json" -f message="Studio readiness $now" -f branch=studio-status
      -f content="$(printf '%s' "$json" | base64 | tr -d '\n')")
[ -n "$old" ] && args+=(-f sha="$old")
gh api "${args[@]}" >/dev/null && echo "Published to the studio-status branch."
