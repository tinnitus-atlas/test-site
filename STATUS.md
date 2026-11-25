# Tinnitus Atlas: status (updated every working turn; newest first in the log)

New chat: read this file first; it overrides the Now and Next sections of the claude.ai status doc. Reply format (owner, 25 Nov 20:41): the short lines he named (what was done, progress, what worked, what broke, the fix, what is needed from him, next); extra sections only when he asks. Details go here, not in chat.

## Now (25 Nov 2026)
- Site: launch-ready in test mode (pilot banner, disclaimer, privacy and corrections pages, CC BY-NC 4.0, launch check: 2 blockers left: test mode, corrections address).
- Summary check: built; runs locally on the drafting computer (second local model) once the local job is live; GitHub nightly is the fallback.
- Records: 10 (target about 150). Content is blocked on the owner's review of #30 (45 proposals; 5 of 90 boxes ticked, gh api pulls/30 at 20:27), whose merge also starts the 6-month backfill.
- Local job (tinnitus-local-2027, report 20:31): key works, drafting model qwen3.6-35b-a3b-mlx found, job clone and daily schedule installed. Stopped: the job's Python lacks PyYAML (vetting card proposed in the Registry tab); no Gemma checker model listed in LM Studio yet.

## Next (roadmap, in order)
1. Local jobs on the drafting computer: drafting (Qwen) + summary check (Gemma 4 26B A4B QAT). Live job: agent-loop approvals/approved-brief-tinnitus-local-2027.md (hard stop 21:30 Sofia; reuses the LM Studio key OpenCode already uses; reports whether LM Studio listens only on this computer). The chat checks agent-loop reports/tinnitus-local-2027*.md and the studio-status branch; no progress at the first check = alert the owner.
2. Owner reviews #30 now -> its merge starts the backfill chain (6, 12, 24 months back) -> more proposals -> local drafts in each Monday review. Claude watches the backfill pull requests.
3. Site look: owner finds it dated ("90s vibe"). Make a simple logo and a modern restyle in the owner's brand direction (minimal, light grey background, dark Prussian blue accent #003153, clean sans-serif type), show it before building; then one pull request.
4. Re-plan gate G1 (about 150 verified records) from the first week of local drafting throughput.
5. Studio domain (owner, later) -> corrections address -> test mode off -> public pilot.
6. Security audit before the public pilot (owner switched the scheduled audit off until then).

## Open loops (nothing leaves this list without a decision)
| Item | Waiting on | Since |
| --- | --- | --- |
| Review #30 (merge starts the backfill) | owner | 24 Nov |
| Readiness check not published (no studio-status branch after the 20:46 run; the job discards its output): build pipeline fix, keep its output in the log and find the failing step | Claude (next brief) | 25 Nov 20:55 |
| Doorbell to this chat + Accept button fix: loop-doorbell-2052, held for the owner's Approve click (routing change) | owner click, then Claude Code | 25 Nov 20:55 |
| Gemma 4 26B A4B QAT still downloading; then set CHECKER_MODEL | owner, then Claude | 25 Nov 20:41 |
| Confirm LM Studio is not reachable from the Wi-Fi ("Serve on Local Network" off): answered by the job's readiness check | tinnitus-local-2027 | 25 Nov |
| Loop: reports from Claude Code do not reach GitHub from its sandbox (since 22 Nov); kit page has no switch button | loop fix job (not yet planned) | 22 Nov |
| Ship it: retry with a rebase when an update conflicts | Claude | 25 Nov |
| Ship it: the "void" note should list the changed items | Claude | 24 Nov |
| Setup wizard: PyNaCl vetting card, then live test and Mac packaging | owner approval of the card | 24 Nov |
| Approval Desk product: A1, A2 or A3 | owner | 24 Nov |
| Studio name | owner (after the build) | 25 Nov |
| Roadmap doc (claude.ai) is stale since 5 Nov; this file replaces its Now/Next | Claude | 25 Nov |

## Log
- 25 Nov 20:55: tinnitus-local-2045: local drafting works (Qwen, exit 0) but drafted 0: nothing approved to draft until #30 is reviewed. Kit logged nothing for the Accept click; doorbell still targets an old chat (set 15:39). Brief loop-doorbell-2052 sent (signed, verified). Planning check 17: restore what used to work without asking.
- 25 Nov 20:45: owner approved PyYAML (Registry card adopted); brief tinnitus-local-2045 sent (signed, verified): installs it in the job's own environment, runs the job, and reads the kit log for the stuck Accept click. Reply format settled (owner's short lines only).
- 25 Nov 20:40: tinnitus-local-2027 ran: key OK, schedule installed, stopped on missing PyYAML; no checker model listed. Switch request for this chat saved (signed, verified). Planning check 16 added. Friction row logged.
- 25 Nov 20:27: new chat took over (start point: this file). Owner chose to keep LM Studio's key check on and reuse the existing key (credential register row 3); brief tinnitus-local-2027 sent (signed, verified), 1550 superseded. Planning check 15 added: look for existing keys before asking the owner. Project doc carry-on.md now points only here. Friction row logged.
- 25 Nov 20:15: tinnitus-local-1550 ran and reported (the loop delivers reports again). Nothing set up yet on the drafting computer: no settings file, no scheduled job; LM Studio requires an API token, so models could not be listed. Owner decision: switch off LM Studio "Require Authentication" (server is local only) or provide a token. Gemma 4 26B A4B QAT (google/) chosen as checker.
- 25 Nov 15:59: check-in: tinnitus-local-1550 not yet forwarded by the kit (no "forwarded" mark, no progress, no studio-status branch). Waiting on the owner's Approve click; if approved and still unmarked, the kit or watcher is down.
- 25 Nov 15:50: brief re-sent as tinnitus-local-1550 after the owner restarted Claude Code and the kit; earlier one superseded. Handoff to a new chat in the same project.
- 25 Nov 15:45: summary check cost cap (#41, merged); local-setup brief sent; this status file created. Why/details: PR descriptions and docs/summary-check.md.
- 25 Nov 15:10: #39 (launch readiness, summary check, licence) and #40 merged.
