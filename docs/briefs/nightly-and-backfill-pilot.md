# Brief: nightly job on GitHub, and a 6-month backfill pilot

Audience: the coding agent that implements this. Strategy and scope are decided here; how to code it is yours to choose. Keep all code and text generic (no personal names, machines or accounts).

## Decisions already made (2026-11-05)

1. The nightly job runs as a scheduled GitHub Actions workflow in this repository, not on a separate agent server.
2. Every new record (trial, paper, device) is reviewed in a batch through the nightly pull request. `proposals.auto_apply_sources` stays empty. No auto-apply is built now.
3. The nightly feeds keep their recent-only rule: trials updated in the last 30 days, papers first published in the last 30 days, FDA decisions in the last 90 days.
4. Older material comes in through staged one-off backfills, each only the new slice: first 30 days to 6 months back (the pilot), later 6 to 12 months, then 12 to 24. This brief covers the pilot only.

## Part A: nightly workflow

Build `.github/workflows/nightly.yml`.

- Triggers: a daily schedule (an off-peak time that is not on the hour) and manual start.
- Runs `run_nightly.sh` with git enabled, using the same setup steps as `live-check.yml` (Python, packages, Biolink model at tag v4.4.6). The Live check workflow stays unchanged as the dry run.
- Credential: use a GitHub App installation token, or a fine-grained personal access token limited to this repository (contents and pull requests: write), stored as a repository secret. Reason: pushes and pull requests made with the built-in workflow token do not start the test workflow, and checks on pull requests it opens wait for manual approval. If the dedicated credential is missing, fall back to the built-in token and say in the run summary which limitations apply.
- Digest: write `reports/nightly.md` to the run summary, and post it to a chat channel through a webhook address stored as a repository secret. If the secret is absent, skip posting without failing. Same format and 1,800-character limit as `hermes/nightly-job.md`.
- Exit codes as in `run_nightly.sh`: 0 all clear and 1 blocking findings both count as a finished run (the digest says which); 2 means the run failed and the workflow must fail visibly and still post a failure digest.
- One run at a time (no overlapping nightly runs).

## Part B: 6-month backfill pilot

Add a one-off backfill mode, started by hand, that proposes older material for review. Window: from 30 days back to 6 months back, so it never overlaps the nightly feeds' last 30 days. The window must be configurable (since and until, in days) so the same mode serves the later 12 and 24-month stages.

What it pulls:
- Trials: on-topic studies (use the relevance filter already in `kgkit/feeds.py`) updated within the window.
- Papers: only the top ~30 by evidence level (guidelines, systematic reviews and meta-analyses, randomized trials, then the rest). The cap is configurable. Papers beyond the cap go to a queue file for later and are not proposed.
- Devices: all FDA decisions under the configured product codes with no date limit. There are few.

How it is delivered:
- One pull request containing its own `reports/proposals.json` and `reports/proposals.md`, with a title starting "Nightly proposals". The apply step finds merged pull requests by that title and reads the proposal list from the merge commit. Note it only looks at the 30 most recent merged pull requests.
- No item may appear in both the pilot pull request and a nightly pull request: exclude anything already listed in an open proposals pull request, and rely on the seen list (`records/seen_proposals.json`) after merge.
- Write `reports/backfill_pilot.md` with: counts per category, how many trials were skipped as off-topic and the list of their registry numbers (so a person can spot-check ten), the share of proposed items whose quote and citation checks passed, and run time.

## Pilot success checks (a person judges these)

- At least about 90% of proposed trials are on-topic in a ten-item spot check.
- The quote and citation checks pass on the bulk of items without manual fixes.
- The whole approval list can be cleared in one sitting (roughly 60 items or fewer).
- Approved items appear on the site after the next nightly run applies them. Approved records are currently thin drafts with the summary marked "still to be written": report how they look, but do not build the drafting pipeline here.

## Dependencies and things to watch

- Order: run the pilot and merge its pull request before enabling the nightly schedule, or accept that the first nightly pull request overlaps. The no-duplicates rule above covers the overlap.
- Applying and publishing are two steps: merging the pull request does nothing by itself; the next nightly run applies ticked items and pushes the records, and that push triggers the site rebuild on the hosting service. Verify this end to end with one ticked item.
- Each approved-and-applied pull request is applied once; its number is stored in `records/applied_prs.json`.

## Reversibility

- Moving the nightly elsewhere: disable the workflow and run `run_nightly.sh` on any machine that has Python, the `gh` tool and push access. `hermes/nightly-job.md` stays valid for that route.
- Batch review is the default configuration; nothing needs undoing.
- Delete the repository secrets to remove the credential and the chat webhook.

## Not in this brief

Auto-applying any source, the content drafting pipeline, the 12 and 24-month backfill stages, clinical review, licence, name and domain.

## Needed from the owner before the workflow can be tested

A GitHub App or token as described above, and a chat webhook address, both added as repository secrets. Exact click steps are to be verified against the current GitHub documentation at the time, not written from memory.
