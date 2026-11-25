# Ship it: one tick instead of babysitting a merge

Tick **Ship it** in a pull request and walk away. The pull request is brought up to date with main, the tests run, and
it is merged for you (squash). You get GitHub's usual notification when it is merged.

Privacy and security: the merge uses a GitHub App ("Ship it app") whose keys are minted for each run, expire after one
hour, and are limited to this repository with contents and pull request access. The app's private key lives only in
an environment secret that only workflows running on main can read. The workflow runs main's copy of its own code, never a pull request's.

## What it will and will not merge
- Only after the owner's own edit turns the box from unticked to ticked. A tick by anyone else does nothing, and
  unticking withdraws the approval (nobody else can re-tick it).
- Only the content the owner approved: the approval records a fingerprint of every changed file at the moment of the
  tick. Bringing the branch up to date with main keeps it; any other change voids the approval and the pull request
  says so.
- Review pull requests ("Nightly proposals ..."): tick your items and Ship it, in one go or in any order. Ship it
  waits for the review sync to write your ticked items, then rebuilds the record changes from your ticks with main's
  own code and settings in a scratch copy and merges only if the branch holds exactly that, nothing else changed
  since your tick, and the review touches only its data folders (reports/ and records/). Your own later tick edits
  are followed; an edit by anyone else (including new items added later, such as drafts) voids the approval: read
  them, then untick and tick Ship it again.
- Never a pull request that changes `.github/` (workflows) or one not aimed at main: those need the owner's manual
  merge.
- Never with failing tests or conflicts: it comments once and waits for a fix and a new tick.
- Known limit: an AI agent working through the owner's own GitHub account could tick the box as the owner. Agents are
  instructed never to tick Ship it; giving agents their own account removes the limit.

## Using it
Add this line to a pull request's description (agents add it to theirs), then tick it when you are happy:

    - [ ] **Ship it**: tick when you are done here. The pull request is then brought up to date, tested and merged for you.

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
8. Open https://github.com/tinnitus-atlas/test-site/settings/environments. If `ship-it` is already listed (GitHub
   creates it the first time the workflow runs), click it; otherwise click **New environment**, name it `ship-it` and
   click **Configure environment**.
   - Under **Deployment branches and tags**, choose **Selected branches and tags**, click **Add deployment branch or
     tag rule**, type `main` and click **Add rule**. (This is what stops a workflow on any other branch from reading
     the key.)
   - Under **Environment variables**, click **Add environment variable**: name `SHIPIT_APP_ID`, value the App ID from
     step 6. Click **Add variable**.
9. Still on that page, under **Environment secrets**, click **Add environment secret**: name `SHIPIT_APP_KEY`; for the
   value, open the `.pem` file in TextEdit, select all, copy, and paste. Click **Add secret**. Then move the `.pem`
   file to the Bin and empty it.
10. Open https://github.com/tinnitus-atlas/test-site/settings/rules, click the rule **Only the owner merges**, under
    **Bypass list** click **Add bypass**, choose the app, set it to **For pull requests only**, and click
    **Save changes**.

Check: the next run of the "Ship it" workflow (Actions tab) shows "No pull request has Ship it ticked." instead of
"not set up yet".
