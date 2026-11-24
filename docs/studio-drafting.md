# Drafting with a local model on a Mac (agent brief)

Audience: the coding agent on the computer that runs the local model. Goal: the drafting step runs every day on that
computer with the local model, only on entries a person has approved, and adds its drafts to the open review pull
request. Nothing here changes main: the owner's merge does.

Privacy and security: the model sees only public registry text; the bot token stays in the system keychain (used by
gh), never in files, logs or this repository; the settings file holds no secret unless a hosted model is used, and is
readable only by its user (chmod 600); the model server listens on localhost only.

## Terms
- **Model server:** LM Studio's local server, an address on this computer that answers like the OpenAI API.
- **Bare entry:** an approved trial or device that still has no summary. Only these are drafted.
- **Review pull request:** the weekly "Nightly proposals ..." pull request the owner ticks and merges.

## Steps
1. Model server: in LM Studio open the **Developer** tab, load the drafting model, switch on **Start server**, and keep
   the default address `http://localhost:1234/v1`. Check: `curl -s http://localhost:1234/v1/models` lists the model;
   note its id exactly.
2. Repository: clone the repository into a folder used only for this job, with git and gh signed in as the trusted bot
   account (the one the nightly uses), able to push branches. Do not reuse a clone that has other work in it.
3. Settings: create `~/.config/kg-drafting.env` (chmod 600) with REPO_DIR (absolute path of that clone),
   DRAFTER_BASE_URL=http://localhost:1234/v1 and DRAFTER_MODEL=<the id from step 1>.
4. Test once by hand: `bash <clone>/tools/studio/drafting-job.sh`. Expect either "Bare entries: 0" (nothing approved
   yet) or drafts added to the open review pull request. Report the output.
5. Schedule: copy `tools/studio/drafting.plist.template` to `~/Library/LaunchAgents/org.kg.drafting.plist`, replace
   JOB_SCRIPT with the absolute path of `drafting-job.sh` and LOG_FILE with a log path, then
   `launchctl load -w ~/Library/LaunchAgents/org.kg.drafting.plist`. Check: `launchctl list | grep org.kg.drafting`.
6. Report back: the model id, the test output, and the line from step 5.
7. Readiness check (added 24 Nov): pull the latest main in the clone, then run
   `bash <clone>/tools/studio/doctor.sh --publish`. It checks the settings file, the model server, the API key (when
   LM Studio's **Require Authentication** is on, put one of its keys in the settings file as DRAFTER_API_KEY), whether
   the model is loaded and whether the server listens only on this computer, and saves the yes/no answers to the
   `studio-status` branch, where the maintainers read them. Fix any "no" you can; report the rest.
8. Model loading and server start: the daily job now starts the model server and loads the model itself (with a
   fixed context length, DRAFTER_CONTEXT, default 16384) when LM Studio's command-line tool `lms` is installed, so
   LM Studio's own "start on login" setting is not needed. If `lms` is not found, install it from LM Studio's
   **Developer** settings or note it in the report. Each run publishes the readiness check again, so this report is
   never relayed by hand.

## Done when
The test run finishes without error, the scheduled job is listed, and the next day's log shows a run.

## Undo
`launchctl unload -w ~/Library/LaunchAgents/org.kg.drafting.plist` and delete that file and the settings file.
