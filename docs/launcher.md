# Launcher: stand up a new condition site in a few clicks

Goal: anyone can create a cited, nightly-checked site like this one for another condition or topic, without
the command line. Status: specification (26 Nov 2026). Nothing built yet beyond the Ship it setup wizard.

## What the person sees
One page with five steps, each with a Connect button, a field to paste what it asks for, and a check mark when
it works. A step that is missing something says exactly what to do.

1. **Topic**: the condition or topic name, its standard identifier (for example a MONDO or HP code), the site
   title and tagline. The launcher proposes the record sections (treatments, trials, devices, papers ...) and the
   search terms for the nightly sources; the person ticks or edits them.
2. **GitHub**: sign in; the launcher creates the repository from this template, private or public.
3. **Hosting**: connect Cloudflare Pages to the new repository (free plan).
4. **Approvals**: install the Ship it app on the new repository (the existing four-click wizard).
5. **First build**: runs the first nightly search and the backfill, opens the first review pull request, and shows
   the test site address.

## What it creates
- A copy of this repository's engine (kgkit, site builder, workflows) with a new settings file for the topic.
- The site in test mode (hidden from search engines, "Test version" banner) until the owner launches it.
- The content editor (see the editor decision) pointed at the new repository.

## Build order
1. Template: separate the engine from the tinnitus content (settings, records and prompts move into one folder),
   so a new topic is a new settings file plus empty records.
2. Topic step: generate the settings file (sections, sources, search terms) from the topic name, for review.
3. GitHub and hosting steps, reusing the Ship it wizard's pattern.
4. First build and a health page showing the nightly, the backfill and the review status for each site.

## Open decisions
- Content editor: Sveltia CMS or Pages CMS (vetting in progress).
- Whether the launcher is a hosted page (anyone can use it) or a local app; hosted is needed to sell it.
