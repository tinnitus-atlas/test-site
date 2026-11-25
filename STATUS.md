# Tinnitus Atlas: status (updated every working turn; newest first in the log)

New chat: read this file first; it overrides the Now and Next sections of the claude.ai status doc. Replies follow the 8-line format (Security, Did, Progress, Broke, Fix, Need from you, Next, stamp); details go here, not in chat.

## Now (25 Nov 2026)
- Site: launch-ready in test mode (pilot banner, disclaimer, privacy and corrections pages, CC BY-NC 4.0, launch check: 2 blockers left: test mode, corrections address).
- Summary check: built; runs locally on the drafting computer (second local model) once the local job is live; GitHub nightly is the fallback.
- Records: 10 (target about 150). Content is blocked on the owner's review of #30 (45 proposals), whose merge also starts the 6-month backfill.

## Next (roadmap, in order)
1. Local jobs on the drafting computer: drafting (Qwen) + summary check (Gemma 4 26B A4B, owner downloading it). Live job: agent-loop approvals/approved-brief-tinnitus-local-1550.md (hard stop 17:15 Sofia). The new chat checks agent-loop reports/tinnitus-local-1550*.md and the studio-status branch; no sign of progress within the first check = alert the owner.
2. Owner reviews #30 now -> its merge starts the backfill chain (6, 12, 24 months back) -> more proposals -> local drafts in each Monday review. Claude watches the backfill pull requests.
3. Site look: owner finds it dated ("90s vibe"). Make a simple logo and a modern restyle in the owner's brand direction (minimal, light grey background, dark Prussian blue accent #003153, clean sans-serif type), show it before building; then one pull request.
4. Re-plan gate G1 (about 150 verified records) from the first week of local drafting throughput.
5. Studio domain (owner, later) -> corrections address -> test mode off -> public pilot.
6. Security audit before the public pilot (owner switched the scheduled audit off until then).

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
- 25 Nov 15:59: check-in: tinnitus-local-1550 not yet forwarded by the kit (no "forwarded" mark, no progress, no studio-status branch). Waiting on the owner's Approve click; if approved and still unmarked, the kit or watcher is down.
- 25 Nov 15:50: brief re-sent as tinnitus-local-1550 after the owner restarted Claude Code and the kit; earlier one superseded. Handoff to a new chat in the same project.
- 25 Nov 15:45: summary check cost cap (#41, merged); local-setup brief sent; this status file created. Why/details: PR descriptions and docs/summary-check.md.
- 25 Nov 15:10: #39 (launch readiness, summary check, licence) and #40 merged.
