# WP-A2: scheduled nightly workflow

| Field | Value |
|---|---|
| Board card | none (Plane deferred) |
| Size | S (≤1h) |
| Risk | R2 |
| Required level | L2, reason: one new workflow file following live-check.yml, every requirement covered by the acceptance tests; R2 because it uses a credential, pushes and sends messages |
| Owner override | Owner-approved unrated routing (Test 1 option A) |
| Data class | public |
| Model used | opencode/deepseek-v4.1-flash-free (default routing), round 1 |
| Reviewer | breaker opencode/glm-5.3-flash-free (28 tests); reviewer qwen3.6-35b-a3b-mlx after GLM stalled; verdict approve, no findings |
| Branch | wp/A2-nightly-workflow |
| Test commit | 73fdfbb |
| Breaker test file | `tests/test_breaker_wpa2.py` |

## Goal
The nightly run starts by itself every night (and by hand from the Actions tab), runs `run_nightly.sh` with git enabled, writes the digest to the run summary, posts it to the chat webhook when configured, and fails visibly when the run itself failed. Built on WP-A1 (`tools/post_digest.py`).

## Context the builder needs
- Relevant files to read first: `docs/briefs/nightly-and-backfill-pilot.md` (Part A only), `.github/workflows/live-check.yml`, `.github/workflows/nightly-manual-test.yml`, `tools/post_digest.py`, `run_nightly.sh`, `tests/test_nightly_workflow.py`.
- Existing patterns to copy: the setup steps of `.github/workflows/live-check.yml` (checkout, Python 3.12, `pip install -r requirements.txt`, Biolink clone at tag v4.4.6), but with the action references pinned to commit SHAs below.
- Decisions already made that must not be reopened:
  - New file `.github/workflows/nightly.yml`, one job. Do not change `live-check.yml` or `nightly-manual-test.yml`.
  - Triggers: `schedule` with exactly one cron `17 2 * * *` (02:17 UTC, off-peak, not on the hour) and `workflow_dispatch`.
  - Workflow-level `permissions: {contents: write, pull-requests: write}`; `concurrency: {group: nightly, cancel-in-progress: false}`; job `timeout-minutes: 30`.
  - Actions pinned to full SHAs: `actions/checkout@11d5960a326750d5838078e36cf38b85af677262` (v4) and `actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065` (v5). No other `uses:` without a 40-character SHA.
  - Credential: repository secret `NIGHTLY_TOKEN` (fine-grained token, contents and pull requests write) with fallback to the built-in token. Checkout gets `with: {fetch-depth: 0, token: ${{ secrets.NIGHTLY_TOKEN || github.token }}}`.
  - Step `id: token-check` with `env: {NIGHTLY_TOKEN_SET: ${{ secrets.NIGHTLY_TOKEN != '' }}}`: when it is not `true`, append to `$GITHUB_STEP_SUMMARY` a note that the built-in token is used, its pushes and pull requests do not start the test workflow, and checks on its pull requests wait for approval. Nothing when it is `true`.
  - Step `id: nightly` with `env: {GH_TOKEN: ${{ secrets.NIGHTLY_TOKEN || github.token }}, BIOLINK_DIR: <the Biolink clone folder>}`: set the git user as in `nightly-manual-test.yml`, `chmod +x run_nightly.sh run_validation.sh`, run `./run_nightly.sh` with git enabled (never set `NO_GIT`), capture its exit code without failing the step (`code=0; ./run_nightly.sh || code=$?`) and write `code=<n>` to `$GITHUB_OUTPUT`. The step itself always exits 0.
  - Step `id: digest` with `if: always()` and `env: {NIGHTLY_WEBHOOK_URL: ${{ secrets.NIGHTLY_WEBHOOK_URL }}, RUN_CODE: ${{ steps.nightly.outputs.code }}}`: run `python3 tools/post_digest.py --report reports/nightly.md --log reports/nightly.log --exit-code "${RUN_CODE:-2}"` and append its output to `$GITHUB_STEP_SUMMARY`.
  - Last step `id: fail-on-error` with `if: always() && steps.nightly.outputs.code != '0' && steps.nightly.outputs.code != '1'` that prints a short reason and exits 1 (covers exit code 2 and a nightly step that never wrote a code).
  - Never put `${{ ... }}` inside a `run:` script; pass values through `env:` (avoids script injection; the tests check this).

## Scope
Files the builder may create or change:
- `.github/workflows/nightly.yml`

Out of scope (do not touch):
- `.github/workflows/live-check.yml`, `.github/workflows/nightly-manual-test.yml`, `.github/workflows/tests.yml`
- `run_nightly.sh`, `tools/`, `kgkit/`, `hermes/`
- Anything in the acceptance test files listed below

## Acceptance criteria
Each criterion has a test. The builder is done when all of these tests pass and nothing else broke.

| # | Criterion (plain words) | Test file and test name |
|---|---|---|
| 1 | Daily schedule off the hour, plus manual start | tests/test_nightly_workflow.py::test_daily_schedule_off_the_hour_and_manual_start |
| 2 | One run at a time, a running nightly is never cancelled | tests/test_nightly_workflow.py::test_one_run_at_a_time_without_cancelling |
| 3 | Write permissions for contents and pull requests, job timeout | tests/test_nightly_workflow.py::test_permissions_and_timeout |
| 4 | Same setup as Live check, actions pinned to SHAs | tests/test_nightly_workflow.py::test_setup_matches_live_check_with_pinned_actions |
| 5 | Checkout uses the dedicated token with fallback | tests/test_nightly_workflow.py::test_checkout_uses_dedicated_token_with_fallback |
| 6 | Nightly step runs run_nightly.sh with git enabled and the token | tests/test_nightly_workflow.py::test_nightly_step_runs_script_with_git_enabled |
| 7 | No expressions inside run scripts | tests/test_nightly_workflow.py::test_no_expressions_inside_run_scripts |
| 8 | Digest step always runs with the webhook secret and the exit code | tests/test_nightly_workflow.py::test_digest_step_always_runs_with_webhook_secret |
| 9 | A failed run fails the workflow after the digest | tests/test_nightly_workflow.py::test_failed_run_fails_workflow_after_digest |
| 10 | Live check workflow unchanged | tests/test_nightly_workflow.py::test_live_check_workflow_unchanged |
| 11 | Nightly step records exit code 0/1/2 and never fails itself | tests/test_nightly_workflow.py::test_nightly_step_records_exit_code_and_never_fails_itself |
| 12 | Built-in token fallback is explained in the run summary | tests/test_nightly_workflow.py::test_token_check_notes_builtin_token_limits |
| 13 | Whole suite still passes, nothing skipped | all of tests/ |

Acceptance test files (locked, the builder may not edit):
- `tests/test_nightly_workflow.py`

## Gate commands
```
python -m pytest -q tests
```

## Builder instructions
- Work only on branch `wp/A2-nightly-workflow` in your worktree.
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
| 1. Gate passed on final commit | PASS c4f0739 (159 passed + 28 breaker, scanners clean); 1 earlier FAIL caused by the gate sandbox (global git config), fixed in the pipeline |
| 2. Acceptance tests unchanged since test commit | yes (gate lock check) |
| 3. No newly skipped or disabled tests | yes (gate skip check) |
| 4. Only in-scope files changed (or extras explained) | yes; extras are the spec, lock and breaker test file |
| 5. No secrets, personal data, machine names, local paths | yes (gitleaks, local-path check, diff read) |
| 6. Review findings resolved | yes, none raised |
| 7. Summary matches the diff | yes |
| R1: most important file read | yes |
| R2: advisor or Opus consulted, full risky diff read, owner yes for deploy/publish/send/delete | advisor consulted 2026-11-05; full diff read; nothing deployed or sent (merge waits for the owner) |

Signed off by: Manager (Claude Opus), advisor consulted  Date: 2026-11-05
Known issues accepted: secret names NIGHTLY_TOKEN and NIGHTLY_WEBHOOK_URL chosen by the manager (brief does not name them); with the built-in token, test checks on the nightly's pull requests wait for approval
