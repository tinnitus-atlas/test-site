# WP-A5: digest reaches Discord (User-Agent) and the run log shows the outcome

| Field | Value |
|---|---|
| Board card | none (Plane deferred) |
| Size | S (≤1h) |
| Risk | R2 |
| Required level | L1, reason: one function in one file, cause known and reproduced, fully covered by the acceptance tests; R2 because it sends messages |
| Owner override | Owner asked for the fix (2026-11-06: "find out why and fix it"); manager-written fix under 20 lines |
| Data class | public |
| Model used | manager (Claude Opus 5.5), no worker dispatch |
| Reviewer | manager |
| Branch | wp/A5-digest-clean |
| Test commit | e65f44c |
| Breaker test file | `tests/test_breaker_wpa1.py` |

## Goal
The first nightly digest (run 42125774648) never reached the channel. Discord's front end answers Python's default User-Agent with HTTP 403 "error code: 1010" (reproduced; a named agent reaches the webhook check). The digest must send its own User-Agent, and the posting outcome must appear in the run log.

## Scope
Files that may change:
- `tools/post_digest.py`
- `tests/test_breaker_wpa1.py`

## Acceptance criteria
| # | Criterion (plain words) | Test file and test name |
|---|---|---|
| 1 | The webhook request carries a named User-Agent, not Python's default | tests/test_digest_user_agent.py::test_digest_request_has_named_user_agent |
| 2 | An HTTP error is reported with its status code on standard output and standard error | tests/test_digest_user_agent.py::test_http_error_reports_status_code |
| 3 | Whole suite still passes, nothing skipped | all of tests/ |

Acceptance test files (locked, the builder may not edit):
- `tests/test_digest_user_agent.py`

## Gate commands
```
python -m pytest -q tests
```

## Sign-off
| Check | Result |
|---|---|
| 1. Gate passed on final commit | yes (runs/A5/gate-report.md) |
| 2. Acceptance tests unchanged since test commit | yes |
| 3. No newly skipped or disabled tests | yes |
| 4. Only in-scope files changed (or extras explained) | yes, plus this spec and the acceptance test |
| 5. No secrets, personal data, machine names, local paths | yes |
| 6. Review findings resolved | none |
| 7. Summary matches the diff | yes |
| R1: most important file read | yes, tools/post_digest.py |
| R2: advisor or Opus consulted, full risky diff read, owner yes for deploy/publish/send/delete | Opus manager read the full diff; owner asked for the fix |

Signed off by: Opus (manager)  Date: 2026-11-06
Known issues accepted: delivery is confirmed only by the next run's log line "Digest: posted".
