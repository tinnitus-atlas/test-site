# WP-A6: report when NIGHTLY_TOKEN expires

| Field | Value |
|---|---|
| Board card | none (Plane deferred) |
| Size | S (≤1h) |
| Risk | R2 |
| Required level | L1, reason: one new workflow file with one shell step, fully covered by the acceptance tests; R2 because it handles a secret |
| Owner override | Owner asked (2026-11-06) for pre-flight to fail when NIGHTLY_TOKEN expires within 14 days, checked via the GitHub API; the token is only readable inside Actions; manager-written, under 20 lines |
| Data class | public |
| Model used | manager (Claude Opus 5.5), no worker dispatch |
| Reviewer | manager |
| Branch | wp/A6-token-expiry |
| Test commit | 5829e91 |
| Breaker test file | `tests/test_token_expiry_workflow.py` |

## Goal
A workflow with no repository permissions calls the GitHub API with NIGHTLY_TOKEN and prints `NIGHTLY_TOKEN expires: <date|never|invalid (HTTP n)|not-configured>` from GitHub's token-expiration response header, weekly and on demand. The token is never printed. The build pipeline's pre-flight reads this line from the latest run.

## Scope
Files that may change:
- `.github/workflows/token-expiry.yml`

## Acceptance criteria
| # | Criterion (plain words) | Test file and test name |
|---|---|---|
| 1 | Manual and weekly start, no permissions | tests/test_token_expiry_workflow.py::test_manual_and_weekly_triggers_and_no_permissions |
| 2 | The secret only enters through the step environment | tests/test_token_expiry_workflow.py::test_secret_only_in_step_env |
| 3 | Prints the expiry date and never the token | tests/test_token_expiry_workflow.py::test_reports_expiry_date |
| 4 | No expiry header prints "never" | tests/test_token_expiry_workflow.py::test_no_expiry_header_means_never |
| 5 | A rejected token fails the run | tests/test_token_expiry_workflow.py::test_rejected_token_fails |
| 6 | No secret configured prints "not-configured" | tests/test_token_expiry_workflow.py::test_missing_secret |
| 7 | Whole suite still passes, nothing skipped | all of tests/ |

Acceptance test files (locked, the builder may not edit):
- `tests/test_token_expiry_workflow.py`

## Gate commands
```
python -m pytest -q tests
```

## Sign-off
| Check | Result |
|---|---|
| 1. Gate passed on final commit | yes (runs/A6/gate-report.md) |
| 2. Acceptance tests unchanged since test commit | yes |
| 3. No newly skipped or disabled tests | yes |
| 4. Only in-scope files changed (or extras explained) | yes, plus this spec, the acceptance test and the lock file |
| 5. No secrets, personal data, machine names, local paths | yes |
| 6. Review findings resolved | none |
| 7. Summary matches the diff | yes |
| R1: most important file read | yes, the workflow |
| R2: advisor or Opus consulted, full risky diff read, owner yes for deploy/publish/send/delete | Opus manager read the full diff; owner asked for the check; owner merges |

Signed off by: Opus (manager)  Date: 2026-11-06
Known issues accepted: an action-free workflow (curl only), so there is nothing to pin.
