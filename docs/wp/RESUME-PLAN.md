# Resume plan: work packages WP-A9, WP-A10, WP-B1, WP-C1

Status: specifications for the build pipeline. No code in this file. The pipeline's manager writes the locked acceptance tests (tests the builder may not edit) and the test commit for each package, in the format of WP-A1 to WP-A8, before any builder starts.

Terms used here:
- **Proposals pull request**: the pull request the nightly opens, titled "Nightly proposals <date> (<n>)", with one "Approved" box per proposal.
- **Seen list**: `records/seen_proposals.json`, the proposals already shown in a merged proposals pull request, which are never proposed again.
- **Digest**: the short run summary the nightly posts to the chat webhook and writes to the run summary.

Order: WP-A9 first (it unblocks everything), WP-A10 alongside it, then WP-B1, then WP-C1.

Privacy and security for every package: the repository is private; records hold only public-source facts and quotes under 15 words; no package adds a secret, an outside service or a new account; secrets enter only through step environments and are never printed; model-written text never merges by itself (WP-A7 rule stays).

## WP-A9: restart the nightly safely

| Field | Value |
|---|---|
| Size | S |
| Risk | R2 (touches the workflow that handles a secret) |
| Data class | public-source data, private repository |
| Depends on | Repository secret `NIGHTLY_TOKEN` set by the owner (a fine-grained token of the trusted bot account, limited to this repository: Contents and Pull requests read and write, with an expiry) |

Goal: the nightly runs every day, cannot bury unreviewed proposals, and says clearly when its token is missing.

Scope (files that may change): `kgkit/apply.py`, `.github/workflows/token-expiry.yml`, `.github/workflows/nightly.yml` (digest wording only), delete `.github/workflows/nightly-manual-test.yml`, new tests.

Acceptance criteria (plain words):
1. A merged proposals pull request with zero ticked boxes adds nothing to the seen list; the digest says "Pull request #<n> was merged with no box ticked; its items stay open" (fixes gap G-20).
2. A merged proposals pull request with at least one ticked box behaves as today: ticked items are applied, the rest go to the seen list.
3. When `NIGHTLY_TOKEN` is not set, the weekly token report shows a warning annotation and the line "NIGHTLY_TOKEN expires: not-configured (the nightly cannot open proposals)"; when it is set, behaviour is unchanged (fixes gap G-21).
4. The temporary workflow "Nightly (manual test)" no longer exists.
5. Whole suite passes, nothing skipped; count may rise, never fall.

Live proof after merge (manager runs it, owner only merges):
1. Enable the workflow "Nightly" (state today: disabled manually).
2. Start it once by hand.
3. Done when: the run reads pull request #12, applies its ticked items, opens a new proposals pull request authored by the trusted bot, and the site rebuild after the records push succeeds. Report the run links.

## WP-A10: make the permission test independent of the user

Size S, risk R1. Scope: `tests/test_breaker_wpa3.py` only.
Goal: `test_git_add_fails_on_permission_denied` passes whether the suite runs as a normal user or as an administrator, without being skipped (gap G-23). First confirm on GitHub's Tests workflow that it passes there; if it does, change how the test produces the permission error (for example a stand-in for the git call), not what it checks.

## WP-B1: 6-month backfill pilot

Size M, risk R1. Specification: Part B of `docs/briefs/nightly-and-backfill-pilot.md` (unchanged), with two additions:
- The window is set in days (since, until); default 30 to 183.
- The pilot pull request title starts "Nightly proposals" so the existing apply step reads it; it must hold no item that is in the open nightly proposals pull request or on the seen list.
Done when: the done-when of Part B is met and `reports/backfill_pilot.md` exists with every count that Part B names.

## WP-C1: drafting step

Size L, risk R2 (model-written text). Specification: `docs/briefs/drafting-step.md` (unchanged), with these constraints from the gaps register:
- Runs as its own command on the owner's agent server, not on GitHub's runners, because the drafting model is not reachable from GitHub (gap G-19). It reads the repository and opens a pull request; it never pushes to main.
- Drafts are model-written text: their pull request never merges by itself and every draft is approved by a person until the owner picks the review mode after the first sample (gap G-18).
- Every relationship in a draft carries a source link and a verbatim quote under 15 words that the existing quote check verifies; a draft that fails is held back, not shown.
Done when: 30 drafted records pass the quote check and a person finds at most 5 percent with factual errors (gate G1).
