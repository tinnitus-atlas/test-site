# Tinnitus Atlas: status (updated every working turn; newest first in the log)

## Now (25 Nov 2026)
- Site: launch-ready in test mode (pilot banner, disclaimer, privacy and corrections pages, CC BY-NC 4.0, launch check: 2 blockers left: test mode, corrections address).
- Summary check: built; runs locally on the drafting computer (second local model) once the local job is live; GitHub nightly is the fallback.
- Records: 10 (target about 150). Content is blocked on the owner's review of #30 (45 proposals), whose merge also starts the 6-month backfill.

## Next (roadmap, in order)
1. Local jobs on the drafting computer: drafting (Qwen) + summary check (Gemma). Brief sent 25 Nov 15:45 (agent-loop approved-brief-tinnitus-local-1545).
2. Owner reviews #30 -> backfill chain (6, 12, 24 months) -> more proposals -> local drafts in each Monday review.
3. Re-plan gate G1 (about 150 verified records) from the first week of local drafting throughput.
4. Studio domain (owner, later) -> corrections address -> test mode off -> public pilot.
5. Security audit before the public pilot (owner switched the scheduled audit off until then).

## Open loops (nothing leaves this list without a decision)
| Item | Waiting on | Since |
| --- | --- | --- |
| Review #30 (merge starts the backfill) | owner | 24 Nov |
| Restart Claude Code and the kit page, click Approve on the tinnitus-local brief | owner | 25 Nov |
| Loop: reports from Claude Code do not reach GitHub from its sandbox (since 22 Nov); kit page has no switch button | loop fix job (not yet planned) | 22 Nov |
| Ship it: retry with a rebase when an update conflicts | Claude | 25 Nov |
| Ship it: the "void" note should list the changed items | Claude | 24 Nov |
| Setup wizard: PyNaCl vetting card, then live test and Mac packaging | owner approval of the card | 24 Nov |
| Approval Desk product: A1, A2 or A3 | owner | 24 Nov |
| Studio name | owner (after the build) | 25 Nov |
| Roadmap doc (claude.ai) is stale since 5 Nov; this file replaces its Now/Next | Claude | 25 Nov |

## Log
- 25 Nov 15:45: summary check cost cap (#41, merged); local-setup brief sent; this status file created. Why/details: PR descriptions and docs/summary-check.md.
- 25 Nov 15:10: #39 (launch readiness, summary check, licence) and #40 merged.
