# WP-A1: nightly digest poster

| Field | Value |
|---|---|
| Board card | none (Plane deferred) |
| Size | S (≤1h) |
| Risk | R2 |
| Required level | L2, reason: one new script and its tests, format fully specified by an existing document; R2 because it sends messages with a secret webhook address |
| Owner override | Force L2 (owner, Build pipeline test 1, 2026-11-05) |
| Data class | public |
| Model used | openrouter/deepseek/deepseek-v4.1-flash |
| Reviewer | qwen3.6-35b-a3b-mlx (different family); breaker qwen3.6-35b-a3b-mlx |
| Branch | wp/A1-digest-poster |
| Test commit | e036009 |
| Breaker test file | `tests/test_breaker_wpa1.py` |

## Goal
The nightly workflow (WP-A2) can turn `reports/nightly.md` into the chat digest described in `hermes/nightly-job.md` and post it to a webhook, or skip posting when no webhook is configured, without ever failing the run.

## Context the builder needs
- Relevant files to read first: `hermes/nightly-job.md` (section "The prompt", step 3: the digest format and the failure format), `run_nightly.sh` (how `reports/nightly.md` and `reports/nightly.log` are written), `tests/test_post_digest.py`.
- Existing patterns to copy: `tools/upstream_watch.py` (a standalone script in `tools/` using only the standard library and `urllib.request`).
- Decisions already made that must not be reopened:
  - New file `tools/post_digest.py`, standard library only (no new dependencies).
  - Functions: `build_digest(report: str | None, exit_code: int, log_tail: str = "") -> str`, `post(text: str, url: str, timeout: float = 15) -> bool` (never raises), `main(argv: list[str] | None = None) -> int`.
  - Command line: `python3 tools/post_digest.py --report reports/nightly.md --log reports/nightly.log --exit-code N`. A missing report file means "no report".
  - The webhook address comes only from the environment variable `NIGHTLY_WEBHOOK_URL`. Absent or empty: print `Digest: skipped (no webhook configured)` and do not touch the network. Posted: `Digest: posted`. Any error: `Digest: posting FAILED (<short reason without the address>)`. `main` returns 0 in all three cases. Never print the webhook address.
  - Payload: HTTP POST, `Content-Type: application/json`, body `{"content": <digest>, "text": <digest>}` (works for the common chat webhooks; the chat service is not named in the brief).
  - `main` prints the digest to standard output (the workflow appends it to the run summary), then the `Digest:` line.
  - Normal digest (exit code 0 or 1 and a report exists): first line `**Knowledge graph nightly run, <date>**` with the date taken from the report's first line (`Nightly run <date>`); then the report's lines starting with `Status:`, `Could not reach:`, `Held back from publishing` (followed by the line `These records stay off the website until fixed.`), `Approved proposals:`, `Website:`, `Freshness:`, `Registry mismatches:`, `Feeds:`, `Biolink export:`, copied exactly; then `Top proposals:` and at most 10 numbered items; then the `Pull request:` line if present, followed by the approval instruction sentence from `hermes/nightly-job.md`. Other lines are not posted.
  - Failure digest (exit code 2, or no report): first line `**Knowledge graph nightly run FAILED**`, then the reason line (the line after `Status: RUN FAILED`) if present, then the last 15 lines of the log in a code block.
  - Every digest is at most 1,800 characters: shorten long lines (or the log tail) rather than dropping the header.

## Scope
Files the builder may create or change:
- `tools/post_digest.py`

Out of scope (do not touch):
- `run_nightly.sh`, `hermes/`, `.github/`, `kgkit/`
- Anything in the acceptance test files listed below

## Acceptance criteria
Each criterion has a test. The builder is done when all of these tests pass and nothing else broke.

| # | Criterion (plain words) | Test file and test name |
|---|---|---|
| 1 | Normal digest has the dated header and copies the listed lines exactly | tests/test_post_digest.py::test_normal_digest_header_and_copied_lines |
| 2 | Held-back records get the warning sentence | tests/test_post_digest.py::test_held_back_line_gets_warning_sentence |
| 3 | Lines not in the list are not posted | tests/test_post_digest.py::test_unlisted_lines_are_not_posted |
| 4 | Approval instruction appears only when there is a pull request | tests/test_post_digest.py::test_approval_instruction_only_with_pull_request |
| 5 | At most 10 proposals | tests/test_post_digest.py::test_top_proposals_capped_at_ten |
| 6 | Exit code 2 gives the failure digest with the last 15 log lines | tests/test_post_digest.py::test_exit_code_2_gives_failure_digest_with_log_tail |
| 7 | Missing report gives the failure digest | tests/test_post_digest.py::test_missing_report_gives_failure_digest |
| 8 | Never more than 1,800 characters | tests/test_post_digest.py::test_digest_never_exceeds_1800_characters |
| 9 | No webhook: skip without network, exit 0 | tests/test_post_digest.py::test_main_skips_posting_without_webhook |
| 10 | Webhook set: one POST with the digest, address not printed | tests/test_post_digest.py::test_main_posts_once_with_digest_text |
| 11 | Posting error does not fail the run, address not printed | tests/test_post_digest.py::test_main_posting_failure_does_not_fail |
| 12 | Failed run still posts a failure digest | tests/test_post_digest.py::test_main_failure_digest_when_exit_2_and_report_missing |
| 13 | Whole suite still passes, nothing skipped | all of tests/ |

Acceptance test files (locked, the builder may not edit):
- `tests/test_post_digest.py`

## Gate commands
```
python -m pytest -q tests
```

## Builder instructions
- Work only on branch `wp/A1-digest-poster` in your worktree.
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
| 1. Gate passed on final commit | |
| 2. Acceptance tests unchanged since test commit | |
| 3. No newly skipped or disabled tests | |
| 4. Only in-scope files changed (or extras explained) | |
| 5. No secrets, personal data, machine names, local paths | |
| 6. Review findings resolved | |
| 7. Summary matches the diff | |
| R1: most important file read | |
| R2: advisor or Opus consulted, full risky diff read, owner yes for deploy/publish/send/delete | |

Signed off by:  Date:
Known issues accepted:
