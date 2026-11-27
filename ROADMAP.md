# Tinnitus Atlas and the condition-site package: roadmap and feature list

Updated 27 Nov 2026. Status words: done, in review (pull request open), next, planned, decision (waits on the owner).
The package has two parts that grow together: content (records, checked nightly) and the platform
(site, editor, API, launcher) that any new topic reuses.

## M1 Content engine running
| Feature | Status | Done when |
| --- | --- | --- |
| Nightly checks and Monday review pull request | done | runs every night (02:17 UTC) |
| Local drafting on the Studio (Qwen), daily schedule | done (26 Nov) | drafts appear in the Monday review |
| Summary check with a second local model (Gemma 4 26B A4B) | next | model downloaded, CHECKER_MODEL set, first check in a run log |
| Review of #30 (45 proposals) | decision | owner ticks items and Ship it |
| Backfill fix: review text within GitHub limits (#46) | in review | merged, backfill re-run opens its review |
| Backfill chain 6, 12, 24 months back | next | three backfill reviews merged |
| Readiness check publishes from the Studio | next | studio-status branch shows today's report |
| Records gate G1: about 150 verified records | planned | launch check counts 150 |

## M2 Public launch
| Feature | Status | Done when |
| --- | --- | --- |
| Studio name, domain, corrections@ address | decision | contact_email set, launch check blocker cleared |
| Test mode off | decision | owner flips test_site |
| Security check before the public pilot | planned | findings fixed or accepted |
| Visit statistics (optional) | planned | analytics token set |

## M3 Site and editing
| Feature | Status | Done when |
| --- | --- | --- |
| Logo, refreshed look, phone layout (#43) | in review | merged |
| Editor (Sveltia CMS, option B): edits collect on an edits branch, one pull request, Ship it to publish | next | owner edits a record and a section in the browser and publishes with one tick |
| Edit sections, labels and record types from the editor | next | adding a new section needs no code |
| Summary editing in the editor | next | a summary edit reaches the site through Ship it |
| Data dictionary page (/schema/) | planned | every field explained |
| Data sources page (/data-sources/) | planned | every feed listed with its licence and schedule |
| Recent changes and changelog pages | planned | human pages built from the changes feed |
| Re-check dates page (/freshness/) | planned | every record's last and next check |
| Suggest-an-edit form | planned | a visitor's suggestion arrives as an issue or review item |
| What's missing page (/gaps/) | planned | lists empty sections and thin evidence |
| Email digest (newsletter) | planned | weekly email built from the changes feed |
| Compare, query builder, timeline views | later | |
| New content sections like onco.cc (technologies, people, institutions, glossary, roadmaps, bottlenecks, ideas, key papers) | later | added as kinds in the settings file once records exist |

## M4 Data and API
| Feature | Status | Done when |
| --- | --- | --- |
| Open files: records, index, graph, Biolink KGX, llms.txt, per-record text pages | done | |
| Changes feed, trials, relations, sources, RIS/BibTeX, CSV, OpenAPI, /api/ guide (#45) | in review | merged |
| Keyed API: self-serve key page, usage limits, commercial licence terms, payment (Cloudflare Worker + Stripe) | next (moved up by the owner, 27 Nov) | a buyer gets a key, calls the API, usage is counted, payment works in test mode |
| Hosted AI connector (MCP over the web, no install) | planned | any AI tool connects with a URL |
| Notifications to other systems (webhooks) | planned | a subscriber receives a call on each change |
| Dated, citable data releases (DOI via Zenodo) | planned | first release has a DOI |
| Search across all topic sites | later | |

## M5 Launcher (paid convenience feature)
| Feature | Status | Done when |
| --- | --- | --- |
| Specification (#44, docs/launcher.md) and clickable mockup | in review | owner approves the flow |
| Template: engine separated from tinnitus content | planned | a new topic is one settings file plus empty records |
| Topic step: settings proposed from the topic name | planned | sections, sources and search terms proposed for review |
| GitHub, hosting, approvals steps (Connect buttons, checks) | planned | a test account stands up a site without the command line |
| First build and a health page per site | planned | nightly, backfill and review status visible per site |
| Payment for the launcher | planned | checkout before the first build |

## M6 Products on top of the data
| Feature | Status | Done when |
| --- | --- | --- |
| Industry tracker (trials, devices, papers for companies) | planned | one-page offer and sample sent to two or three companies |
| White-label atlas for charities and clinics | planned | one pilot client |
| Clinician edition (briefs and patient handouts) | later | |

## Operations (owner's build pipeline, parallel)
| Feature | Status | Done when |
| --- | --- | --- |
| Find and stop what floods the bot's GitHub allowance | decision | flood stopped; Accept fix merged (approval route to Claude Code is broken) |
