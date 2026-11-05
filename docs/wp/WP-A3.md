# WP-A3: nightly publishes through auto-merging pull requests

| Field | Value |
|---|---|
| Board card | none (Plane deferred) |
| Size | S (≤1h) |
| Risk | R2 |
| Required level | L2, reason: one small new script plus two contained edits in run_nightly.sh, behaviour fully covered by tests with a local remote and a stand-in gh; R2 because it publishes record changes |
| Owner override | Owner-approved unrated routing (Test 1 option A) |
| Data class | public |
| Model used | opencode/deepseek-v4.1-flash-free (default routing), round 1, $0 |
| Reviewer | breaker opencode/glm-5.3-flash-free (41 tests) after a 20-min timeout on qwen3.6-35b-a3b-mlx; reviewer opencode/glm-5.3-flash-free (approve, no findings) |
| Branch | wp/A3-publish-via-pr |
| Test commit | 58c3305 |
| Breaker test file | `tests/test_breaker_wpa3.py` |

## Goal
`main` stays protected (pull request required). The nightly run no longer pushes to `main`: applied proposals and the held list are published on a branch with a pull request that is set to auto-merge, so it merges by itself once the required checks pass.

## Context the builder needs
- Relevant files to read first: `run_nightly.sh` (the two `git push -q origin main` blocks: applied proposals, about line 34, and the held list, about line 55), `kgkit/apply.py` (finds merged pull requests titled "Nightly proposals"; the new pull requests must NOT use that title), `tests/test_publish_via_pr.py`.
- Decisions already made that must not be reopened:
  - New script `tools/publish_via_pr.sh <branch> <commit message> <path>...` (bash, run from the repository root while on `main`):
    1. `git checkout -q -B <branch>`, `git add -- <paths>`, `git commit -q -m <message>`, `git push -q -f origin <branch>`. Any failure: go back to `main`, print a short reason to standard error, exit 1.
    2. Reuse an open pull request for the branch (`gh pr view <branch> --json url -q .url`) or create one: `gh pr create --head <branch> --base main --title <message> --body <short text saying it was opened by the nightly run and merges itself after the checks>`. Failure: back to `main`, exit 1.
    3. Go back to `main` (`git checkout -q main`).
    4. `gh pr merge <branch> --auto --squash --delete-branch`. Success: print the pull request URL as the last line of standard output, exit 0. Failure (auto-merge not allowed or not possible): print the URL as the last line, exit 3 (the pull request stays open for a person).
    Git and gh chatter goes to standard error, so standard output carries only the URL.
  - `run_nightly.sh`, apply step (only when git is enabled):
    - Before applying, if `gh pr list --state open --search "Apply approved proposals in:title" --json number -q length` prints a number greater than 0, skip applying and set `APPLY_LINE="Approved proposals: waiting, the previous apply pull request is still open"`. This stops the same proposals being applied twice.
    - Otherwise apply as today; when records changed, run `tools/publish_via_pr.sh "nightly/apply-$DAY" "Apply approved proposals $DAY" "$(dirname "$RECORDS")"`. Exit 0: `APPLY_LINE="Approved proposals: applied; pull request <url> merges itself once the checks pass"`. Exit 3: `APPLY_LINE="Approved proposals: applied; pull request <url> needs a manual merge (auto-merge unavailable)"`. Exit 1: `fail "could not publish applied proposals"`.
  - `run_nightly.sh`, held list: replace the direct push with `tools/publish_via_pr.sh "nightly/held-$DAY" "Update held records $DAY" "$HELD_DEST"`; exit 0 or 3 sets `HELD_LINE` to say the held list goes through pull request <url> (and whether it merges itself); exit 1 keeps today's "could not publish the held list" line.
  - Nothing else in `run_nightly.sh` changes; `NO_GIT=1` behaviour is unchanged. No new dependencies.

## Scope
Files the builder may create or change:
- `tools/publish_via_pr.sh`
- `run_nightly.sh`

Out of scope (do not touch):
- `.github/`, `kgkit/`, `tools/post_digest.py`, `hermes/`
- Anything in the acceptance test files listed below

## Acceptance criteria
Each criterion has a test. The builder is done when all of these tests pass and nothing else broke.

| # | Criterion (plain words) | Test file and test name |
|---|---|---|
| 1 | Pushes a branch, opens a pull request to main, sets auto-merge (squash, delete branch), prints the URL, main untouched | tests/test_publish_via_pr.py::test_publishes_branch_and_sets_auto_merge |
| 2 | Auto-merge refused: exit 3, pull request left for a person | tests/test_publish_via_pr.py::test_auto_merge_refused_leaves_pull_request_for_a_person |
| 3 | Push failure: exit 1, no pull request, back on main | tests/test_publish_via_pr.py::test_push_failure_returns_1_and_back_on_main |
| 4 | Pull request failure: exit 1, back on main | tests/test_publish_via_pr.py::test_pull_request_failure_returns_1 |
| 5 | run_nightly.sh never pushes main and uses the script for both publishes | tests/test_publish_via_pr.py::test_run_nightly_never_pushes_main_directly |
| 6 | run_nightly.sh waits while an apply pull request is open | tests/test_publish_via_pr.py::test_run_nightly_waits_for_open_apply_pull_request |
| 7 | Whole suite still passes, nothing skipped | all of tests/ |

Acceptance test files (locked, the builder may not edit):
- `tests/test_publish_via_pr.py`

## Gate commands
```
python -m pytest -q tests
bash -n run_nightly.sh
bash -n tools/publish_via_pr.sh
```

## Builder instructions
- Work only on branch `wp/A3-publish-via-pr` in your worktree.
- Do not edit, skip or delete the acceptance tests.
- Do not add new dependencies unless listed here: none.
- No secrets, personal data, machine names or local paths in code or comments.
- When finished, return: a five-line summary of what you changed and why, the list of files changed, and anything you were unsure about.

## Builder summary

## Review findings
| # | File:line | Finding | Status (fixed / rejected + reason) |
|---|---|---|---|

## Sign-off
| Check | Result |
|---|---|
| 1. Gate passed on final commit | PASS dde76c3 (193 passed incl. A1-A3 acceptance + 41 breaker, bash -n both scripts, scanners clean) |
| 2. Acceptance tests unchanged since test commit | yes (gate lock check) |
| 3. No newly skipped or disabled tests | yes (gate skip check) |
| 4. Only in-scope files changed (or extras explained) | yes; extras are the spec, lock and breaker test file |
| 5. No secrets, personal data, machine names, local paths | yes (gitleaks, local-path check, diff read) |
| 6. Review findings resolved | yes, none raised |
| 7. Summary matches the diff | yes |
| R1: most important file read | yes |
| R2: advisor or Opus consulted, full risky diff read, owner yes for deploy/publish/send/delete | advisor consulted 2026-11-05; full diff read; nothing deployed or sent (merge waits for the owner) |

Signed off by: Manager (Claude Opus), advisor consulted  Date: 2026-11-05
Known issues accepted: auto-merge cannot happen until the owner enables Allow auto-merge and a required status check on main (until then the script exits 3 and a person merges); auto-merge on a Free-plan public repo is not confirmed by the docs; with the built-in token checks need approval, so auto-merge also needs NIGHTLY_TOKEN; the night's checks run on records before the apply; held-list pull requests from two nights can conflict
