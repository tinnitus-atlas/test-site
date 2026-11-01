# Putting the site online (GitHub + Cloudflare Pages, free)

The code and records live in a GitHub repository. Cloudflare Pages watches that repository and rebuilds the website every time something changes on the main branch: when an approved proposal is applied, when the held list changes, or when you edit a record. Nothing runs on your own computer for the website.

Free-plan limits that matter here: 500 builds a month, 20,000 files per site, 20-minute build time ([Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits)). A nightly rebuild uses about 30 builds a month.

## 1. Put the project on GitHub (once)

1. Sign in at https://github.com and click **New** (top left, next to "Top repositories").
2. Repository name: for example `tinnitus-atlas`. Choose **Public** (needed for free GitHub tools and for an open resource). Click **Create repository**.
3. On your computer, open Terminal (Applications > Utilities > Terminal) and run, one line at a time, replacing OWNER with your GitHub username:
   ```
   cd ~/kg-quality-kit
   git init -b main
   git add .
   git commit -m "First version"
   git remote add origin https://github.com/OWNER/tinnitus-atlas.git
   git push -u origin main
   ```
4. Open `kit.tinnitus.yaml`, set `site.repo_url` to `https://github.com/OWNER/tinnitus-atlas`, save, then run:
   `git commit -am "Set repository address" && git push`

## 2. Connect Cloudflare Pages (once)

1. Sign in at https://dash.cloudflare.com (a free account is enough).
2. In the left menu click **Workers & Pages**, then **Create**, then the **Pages** tab, then **Connect to Git**.
3. Choose GitHub, authorise Cloudflare, and select the `tinnitus-atlas` repository. Click **Begin setup**.
4. Fill in the build settings exactly:
   - **Production branch:** `main`
   - **Framework preset:** `None`
   - **Build command:** `pip install pyyaml==6.0.2 && python3 site/build_site.py --config kit.tinnitus.yaml --records records/tinnitus.records.json --out public`
   - **Build output directory:** `public`
5. Click **Save and Deploy**. After about a minute the site is live at an address like `tinnitus-atlas.pages.dev`.

The Cloudflare build image includes Python 3.13 ([build image](https://developers.cloudflare.com/pages/configuration/build-image/)). The `_headers` file the builder writes lets other sites and agents read the JSON API ([custom headers](https://developers.cloudflare.com/pages/configuration/headers/)).

## 3. Set the real address (once)

1. Open `kit.tinnitus.yaml` and set `site.base_url` to the live address, for example `https://tinnitus-atlas.pages.dev` (or your own domain later).
2. Commit and push: `git commit -am "Set site address" && git push`. Cloudflare rebuilds automatically; the sitemap and search-engine data now use the real address.

## 4. Optional: your own domain

In Cloudflare Pages open the project, click **Custom domains**, then **Set up a custom domain**, and follow the prompts. Then update `site.base_url` as in step 3.

## What happens every night after this

1. The nightly job applies proposals you approved, runs the checks, and publishes the held list.
2. Each of those is a push to `main`, so Cloudflare rebuilds the site within a minute or two.
3. Records the checks hold back disappear from the site, the API and the agent files until fixed.

## Alternative: GitHub Pages

GitHub can host the site too (repository **Settings** > **Pages**), but it needs a small build workflow file. Cloudflare Pages is simpler for this project because it runs the build command directly.
