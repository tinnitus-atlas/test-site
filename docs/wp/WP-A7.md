# WP-A7: untrusted text in the nightly (trusted authors, no auto-merge for model-written changes)

| Field | Value |
|---|---|
| Board card | none (Plane deferred) |
| Size | S (≤1h) |
| Risk | R2 |
| Required level | L2, reason: two contained changes in two files, fully covered by acceptance tests; R2 because it controls publishing |
| Owner override | Owner asked (2026-11-06) to apply the untrusted-text rule; manager-written, under 20 lines |
| Data class | public |
| Model used | manager (Claude Opus 5.5), no worker dispatch |
| Reviewer | manager |
| Branch | wp/A7-untrusted-text |
| Test commit | c8c0050 |
| Breaker test file | `tests/test_untrusted_text.py` |

## Goal
The apply step acts only on pull requests opened by trusted accounts and titled "Nightly proposals". A change that a model wrote never merges by itself.

## Scope
Files that may change:
- `kgkit/apply.py`
- `tools/publish_via_pr.sh`
- `tests/test_apply.py` (stand-in pull requests gain an author field)

## Acceptance criteria
| # | Criterion (plain words) | Test file and test name |
|---|---|---|
| 1 | Only trusted authors and the exact title are read | tests/test_untrusted_text.py::test_only_trusted_authors_and_exact_title |
| 2 | Trusted authors can be set by environment | tests/test_untrusted_text.py::test_trusted_authors_can_be_set_by_environment |
| 3 | A record labelled automated_agent is not auto-merged | tests/test_untrusted_text.py::test_model_written_record_is_not_auto_merged |
| 4 | MODEL_WRITTEN=1 is not auto-merged | tests/test_untrusted_text.py::test_model_written_flag_is_not_auto_merged |
| 5 | Plain changes still auto-merge | tests/test_untrusted_text.py::test_plain_change_still_auto_merges |
| 6 | Whole suite still passes, nothing skipped | all of tests/ |

Acceptance test files (locked, the builder may not edit):
- `tests/test_untrusted_text.py`

## Gate commands
```
python -m pytest -q tests
bash -n tools/publish_via_pr.sh
```

## Sign-off
| Check | Result |
|---|---|
| 1. Gate passed on final commit | yes (runs/A7/gate-report.md) |
| 2. Acceptance tests unchanged since test commit | yes |
| 3. No newly skipped or disabled tests | yes |
| 4. Only in-scope files changed (or extras explained) | yes, plus this spec and the lock file |
| 5. No secrets, personal data, machine names, local paths | yes |
| 6. Review findings resolved | none |
| 7. Summary matches the diff | yes |
| R1: most important file read | yes, tools/publish_via_pr.sh |
| R2: advisor or Opus consulted, full risky diff read, owner yes for deploy/publish/send/delete | Opus manager read the full diff; owner merges |

Signed off by: Opus (manager)  Date: 2026-11-06
Known issues accepted: the drafting step must set MODEL_WRITTEN=1 or the automated_agent label; its brief's non-person review mode conflicts with the policy.
