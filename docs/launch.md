# Launching the site

The site stays a hidden test site until `site.test_site` is `false` in `kit.tinnitus.yaml`.
The launch check lists what is still missing:

    python3 -m kgkit.launch_check --config kit.tinnitus.yaml --records records/tinnitus.records.json

Blockers stop the launch; warnings are shown and allowed.

## Decisions for the owner

| Decision | Setting | Blocks launch |
| --- | --- | --- |
| Data licence | `licence_data`, then `licence_decided: true` | yes |
| Corrections address (a role address, not a personal one) | `contact_email` | yes |
| Domain | `base_url` (the pages.dev address is allowed) | no |
| Visit statistics (Cloudflare Web Analytics site token) | `analytics_token` | no |
| Clinician reviews the summaries | `clinical_review: true` removes the Pilot banner | no |

## What changes when test mode is turned off

- Search engines and AI crawlers may index the site (robots.txt, sitemap, no `noindex` tag or header).
- The data licence is shown as chosen instead of "not yet licensed".
- The banner changes from "Test version" to "Pilot" (or to the plain notice once `clinical_review` is true). Every banner says
  it is about this site's summaries and choices, not about the trials, papers or products listed.
- Analytics loads only if `analytics_token` is set, and the privacy page says so automatically.

## Undo

Set `test_site: true` again and merge. The next deploy hides the site again; search engines drop it over the following weeks.
