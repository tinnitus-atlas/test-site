# Ship it: one tick instead of babysitting a merge

Tick **Ship it** in a pull request and walk away. The pull request is brought up to date with main, the tests run, and
it is merged for you (squash). You get GitHub's usual notification when it is merged.

Privacy and security: the merge uses a GitHub App ("Ship it app") whose keys are minted for each run, expire after one
hour, and are limited to this repository with contents and pull request access. The app's private key lives only in
the repository's encrypted secrets. The workflow runs main's copy of its own code, never a pull request's.

## What it will and will not merge
- Only after the owner's own edit turns the box from unticked to ticked. A tick by anyone else does nothing.
- Only the version the owner approved. Later commits keep the approval only if they are the app's own "bring up to
  date with main" merges, or, on a review pull request, the review sync's commit that changes only `records/`. Any
  other commit voids the approval and the pull request says so.
- Never a pull request that changes `.github/workflows`: those need the owner's manual merge.
- Never with failing tests or conflicts: it comments once and waits for a fix and a new tick.

## One-time setup (owner, about 10 minutes, Browser: your account)
Impact: adds one app that can merge pull requests in this repository only after your tick; nothing else changes.
Undo: uninstall the app (organisation Settings > GitHub Apps) or delete the secret; manual merging keeps working.

1. Open https://github.com/organizations/tinnitus-atlas/settings/apps/new
2. **GitHub App name:** any free name, for example `tinnitus-atlas-ship-it`.
   **Homepage URL:** `https://github.com/tinnitus-atlas/test-site`
3. Under **Webhook**, untick **Active**.
4. Under **Repository permissions**, set **Contents** to **Read & write** and **Pull requests** to **Read & write**.
   Leave everything else at **No access**.
5. Under **Where can this GitHub App be installed?**, choose **Only on this account**, then click
   **Create GitHub App**.
6. On the app page that opens, note the **App ID** near the top. Scroll to **Private keys** and click
   **Generate a private key**: a `.pem` file downloads.
7. In the left menu click **Install App**, then **Install** next to tinnitus-atlas, choose **Only select
   repositories**, pick **test-site**, and click **Install**.
8. Open https://github.com/tinnitus-atlas/test-site/settings/variables/actions and click **New repository
   variable**: name `SHIPIT_APP_ID`, value the App ID from step 6. Click **Add variable**.
9. Open https://github.com/tinnitus-atlas/test-site/settings/secrets/actions and click **New repository secret**:
   name `SHIPIT_APP_KEY`; for the value, open the `.pem` file in TextEdit, select all, copy, and paste. Click
   **Add secret**. Then move the `.pem` file to the Bin and empty it.
10. Open https://github.com/tinnitus-atlas/test-site/settings/rules, click the rule **Only the owner merges**, under
    **Bypass list** click **Add bypass**, choose the app, set it to **For pull requests only**, and click
    **Save changes**.

Check: the next run of the "Ship it" workflow (Actions tab) shows "No pull request has Ship it ticked." instead of
"not set up yet".
