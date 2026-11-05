#!/usr/bin/env bash
# Publish paths through a branch and a pull request to main that merges itself once the required checks pass.
# Usage: tools/publish_via_pr.sh <branch> <commit message> <path>...
# Run from the repository root while on main. Standard output carries only the pull request URL; all git and gh
# chatter goes to standard error.
# Exit: 0 the pull request is set to auto-merge; 1 publishing failed; 3 the pull request needs a manual merge.
set -uo pipefail

if [ "$#" -lt 3 ]; then
  echo "usage: $0 <branch> <commit message> <path>..." >&2
  exit 1
fi

BRANCH="$1"
MESSAGE="$2"
shift 2

back_to_main() { git checkout -q main >&2 2>&1 || true; }

failed() {
  back_to_main
  echo "publish_via_pr: $1" >&2
  exit 1
}

# Commit the paths on a fresh branch and push it.
git checkout -q -B "$BRANCH" >&2 2>&1 || failed "could not create branch $BRANCH"
git add -- "$@" >&2 2>&1 || failed "could not stage the changes"
git commit -q -m "$MESSAGE" >&2 2>&1 || failed "could not commit the changes"
git push -q -f origin "$BRANCH" >&2 2>&1 || failed "could not push branch $BRANCH"

# Reuse an open pull request for the branch, or create one.
URL="$(gh pr view "$BRANCH" --json url -q .url 2>/dev/null || true)"
if [ -z "$URL" ]; then
  URL="$(gh pr create --head "$BRANCH" --base main --title "$MESSAGE" \
    --body "Opened by the nightly run. It merges itself once the required checks pass.")"
  STATUS=$?
  [ "$STATUS" -eq 0 ] && [ -n "$URL" ] || failed "could not open a pull request for $BRANCH"
fi

git checkout -q main >&2 2>&1 || failed "could not return to main"

# Ask GitHub to merge the pull request once the checks pass. When that is not possible the pull request stays open
# for a person, and the exit code says so.
if gh pr merge "$BRANCH" --auto --squash --delete-branch >&2 2>&1; then
  echo "$URL"
  exit 0
fi

echo "$URL"
exit 3
