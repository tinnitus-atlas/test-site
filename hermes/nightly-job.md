# Nightly scheduled job: knowledge graph checks

This scheduled job runs the feeds, the five quality checks and the Biolink export every night, then posts a short digest to the chat channel. A person approves changes by merging the pull request it opens; the job itself never changes a record.

## One-time setup on the machine that runs the agent

1. Install Python packages: `pip install pyyaml kgx==2.7.0`
2. Clone the knowledge graph repository, for example: `git clone https://github.com/<owner>/<repo>.git ~/kg-quality-kit`
3. Log the GitHub command-line tool in with push access to that repository: `gh auth login`
4. Run the job once by hand and read the output: `cd ~/kg-quality-kit && ./run_nightly.sh`
5. Make sure the agent's home chat channel is set, so scheduled jobs can deliver to it.

## Creating the scheduled job

Send the agent this message in chat, replacing `<PROJECT_DIR>` with the full folder path from step 2 (for example `/home/agent/kg-quality-kit`):

> Create a scheduled job named "kg-nightly" that runs every day at 03:17 in my time zone, delivers its result to the home chat channel, and uses the prompt below exactly as written.

A cheap model is enough for this job: all checking is done by the scripts, and the agent only runs one command and relays the result.

## The prompt (paste exactly)

```
You are running the nightly quality job for a public knowledge graph. This is a fresh session with no memory; follow these steps exactly and do nothing else.

1. In the terminal run:
   cd <PROJECT_DIR> && ./run_nightly.sh
   Wait for it to finish and note its exit code (0 = all clear, 1 = blocking findings, 2 = the run failed).

2. Read the file <PROJECT_DIR>/reports/nightly.md.

3. Post ONE message to the chat channel, under 1,800 characters, in this format:

   **Knowledge graph nightly run, <date from the first line of nightly.md>**
   <the "Status:" line, copied exactly>
   <the "Could not reach:" line if present, copied exactly>
   <the "Held back from publishing" line if present, copied exactly, followed by: "These records stay off the website until fixed.">
   <the "Approved proposals:", "Website:", "Freshness:", "Registry mismatches:", "Feeds:" and "Biolink export:" lines, copied exactly>
   <the "Top proposals:" list, copied exactly, at most 10 items>
   <the "Pull request:" line, copied exactly>
   If there is a pull request, end with: "To approve, tick the Approved box under each proposal you accept in the pull request description, then merge. Unticked items are ignored. Tomorrow's run applies the ticked ones."

   If the exit code was 2, or nightly.md is missing, post instead:
   **Knowledge graph nightly run FAILED**
   <the reason line from nightly.md if present>
   <the last 15 lines of <PROJECT_DIR>/reports/nightly.log, in a code block>

4. Rules:
   - Copy lines from nightly.md; do not reword, summarise, add medical claims or invent numbers.
   - Do not edit, create or delete any file in <PROJECT_DIR>.
   - Do not merge, close or comment on pull requests.
   - Do not run any other command and do not re-run the script.
   - If a step fails, report the failure in the message rather than trying to fix it.
```

## What a person does each morning

Open the pull request link from the message and read the proposals in its description (each shows the claim, why it surfaced, the evidence with its source, and when it would be wrong). Tick the "Approved" box under each one you accept, then merge. The next nightly run applies only the ticked proposals, commits them to the records and reports "Approved proposals: applied". Nothing reaches the records without a tick and a merge, and each pull request is applied once.

---

# Monthly scheduled job: upstream watch

Checks whether OnCo, the project the quality checks were adapted from, changed any of those scripts, so useful fixes can be carried over. Nothing is changed automatically.

Send the agent this message in chat, replacing `<PROJECT_DIR>`:

> Create a scheduled job named "kg-upstream-watch" that runs at 09:23 on the first day of every month in my time zone, delivers its result to the home chat channel, and uses the prompt below exactly as written.

```
This is a fresh session with no memory. In the terminal run:
  cd <PROJECT_DIR> && python3 tools/upstream_watch.py
Then post ONE message to the chat channel, under 1,800 characters:
  **Upstream watch (OnCo quality scripts)**
  followed by the contents of <PROJECT_DIR>/reports/upstream_watch.md, shortened to the section headings and at most three commit lines per section.
If the command fails, post "Upstream watch FAILED" and the last 10 lines of its output in a code block.
Do not edit any file, do not run any other command, and do not apply any change.
```

When the message lists a relevant fix, ask Claude (or your coding agent) to compare that OnCo commit with the matching kit check and propose the same change.
