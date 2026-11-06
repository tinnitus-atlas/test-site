# WP-A8: pin every GitHub Action by commit SHA; no real home folder in the Hermes job

| Field | Value |
|---|---|
| Board card | none (Plane deferred) |
| Size | S (≤1h) |
| Risk | R1 |
| Required level | L1, reason: mechanical replacement of seven action references and one example path, checked by a test |
| Owner override | Owner audit fix plan item 6 (2026-11-06); manager-written, under 20 lines |
| Data class | public |
| Model used | manager (Claude Opus 5.5), no worker dispatch |
| Reviewer | manager |
| Branch | wp/A8-pin-actions |
| Test commit | 20c6261 |
| Breaker test file | `tests/test_pinned_actions.py` |

## Goal
Every GitHub Action is pinned to a full commit SHA from the approved list, and the Hermes job text names no real home folder.

## Scope
Files that may change:
- `.github/workflows/live-check.yml`
- `.github/workflows/nightly-manual-test.yml`
- `.github/workflows/tests.yml`
- `hermes/nightly-job.md`

## Acceptance criteria
| # | Criterion (plain words) | Test file and test name |
|---|---|---|
| 1 | Every action is pinned by a commit SHA | tests/test_pinned_actions.py::test_every_action_pinned_by_commit_sha |
| 2 | The Hermes job names no real home folder | tests/test_pinned_actions.py::test_hermes_job_names_no_home_folder |
| 3 | Whole suite still passes, nothing skipped | all of tests/ |

Acceptance test files (locked, the builder may not edit):
- `tests/test_pinned_actions.py`

## Gate commands
```
python -m pytest -q tests
```

## Sign-off
| Check | Result |
|---|---|
| 1. Gate passed on final commit | re-gate after the WP-A2 hash update (runs/A8/gate-report.md) |
| 2. Acceptance tests unchanged since test commit | yes |
| 3. No newly skipped or disabled tests | yes |
| 4. Only in-scope files changed (or extras explained) | yes, plus this spec, the lock files, and (owner-approved 2026-11-06) the pinned live-check.yml hash in WP-A2's locked test `test_live_check_workflow_unchanged`, with WP-A2's lock re-locked |
| 5. No secrets, personal data, machine names, local paths | yes |
| 6. Review findings resolved | none |
| 7. Summary matches the diff | yes |
| R1: most important file read | yes, the three workflows |
| R2: n/a | R1 package |

Signed off by: Opus (manager)  Date: 2026-11-06
Known issues accepted: none.
