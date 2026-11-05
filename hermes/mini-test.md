# Mini test (stage 1)

Goal: see the site online, run every check once against the real services, and confirm the website rebuilds by itself, before any scheduled job is handed to an agent.

The site is in test mode (`site.test_site: true` in `kit.tinnitus.yaml`): search engines and AI crawlers are told not to index it, it grants no data licence, and every page says it is an unreviewed test.

## Who is who

| Who | Where | Does |
|---|---|---|
| You | Browser | Create an empty repository, press "Run workflow", connect Cloudflare |
| GitHub | Your account | Stores the code; its free automated runs ("GitHub Actions") run the tests on every change and the live check when you press the button |
| Cloudflare Pages | Your account | Rebuilds the website from GitHub on every change, free, at `<name>.pages.dev` |
| Claude | claude.ai | Uploads the code, reads the live-check results, fixes what breaks |

## Optional, tonight: look at the site in two minutes (no GitHub)

[Browser: your Cloudflare account]
1. Go to https://dash.cloudflare.com, left menu **Workers & Pages**.
2. Click **Create application**, then **Get started** next to "Drag and drop your files".
3. Project name: `tinnitus-preview`. Click **Create project**.
4. Drag `tinnitus-preview-site.zip` onto the upload box, then click **Deploy site**.

You should see a link to `https://tinnitus-preview.pages.dev`. This project can never be connected to GitHub (a Cloudflare rule), so delete it after the real one is up: **Workers & Pages** > `tinnitus-preview` > **Settings** > **Delete project**.

## Step 1. [Browser: your GitHub account] Create an empty repository

1. Go to https://github.com/new
2. Repository name: `test-site`. Choose **Private**. Leave "Add a README" and every other box unticked.
3. Click **Create repository**. You should see a page titled "Quick setup".
4. Tell Claude "tinnitus-atlas exists". Claude uploads the code.

## Step 2. [Browser: your GitHub account] Run the live check

1. Open the repository, click the **Actions** tab.
2. In the left list click **Live check**, then **Run workflow** (right side), then the green **Run workflow** button.
3. Wait 3–5 minutes until the run shows a green tick (or a red cross). Click the run. The digest is on that page under "Live check".
4. Copy the digest to Claude, or tell Claude the run finished.

What it proves: the citation, quote, trial and FDA checks reach the real services, and the official Biolink validator accepts the export. Until now these ran only against stand-ins.

## Step 3. [Browser: your Cloudflare account] Connect the repository

1. https://dash.cloudflare.com > **Workers & Pages** > **Create application** > **Pages** tab (not the default Workers view) > **Import an existing Git repository**. A Workers application shows a placeholder page instead of the site.
2. Choose **GitHub**. If asked, click **Install & Authorize** and allow access to `test-site` only.
3. Select `test-site`, click **Begin setup**, and fill in exactly:
   - Project name: `tinnitus-atlas-test`
   - Production branch: `main`
   - Framework preset: `None`
   - Build command: `pip install pyyaml==6.0.2 && python3 site/build_site.py --config kit.tinnitus.yaml --records records/tinnitus.records.json --out public`
   - Build output directory: `public`
4. Deploy. You should see a link like `https://tinnitus-atlas-test.pages.dev`, and the page should say "Tinnitus Atlas" with a yellow "Test version" banner. Tell Claude the address; Claude sets it in the configuration, which triggers the first automatic rebuild.

## How you know it worked

The live-check digest has no "INCOMPLETE" line, the Tests run on GitHub has a green tick, and the site at the pages.dev address changes by itself after Claude's next upload.

## Next stage

Only after this passes: the nightly run is scheduled (on GitHub or on the agent's server) with the digest posted to chat, using `hermes/nightly-job.md`.

## How to pause or undo

Cloudflare: **Workers & Pages** > project > **Settings** > **Delete project**. GitHub: repository **Settings** > **Delete this repository**.
