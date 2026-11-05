# Brief: the drafting step (turns a bare entry into a finished one)

Audience: the coding agent that implements this. Claude wrote the specification; how to code it is yours to choose. Keep all code and text generic (no personal names, machines or accounts).

## Terms (read first)

- **Record**: one entry in the knowledge graph (a trial, a device, a drug and so on). Stored in `records/tinnitus.records.json`.
- **Bare entry**: a record created from a registry feed. It holds facts copied from the registry (title, registry number, status, phase, sponsor) and the placeholder summary "Draft record from a registry feed; summary still to be written". It has no real summary and no sourced relationships.
- **Finished entry**: a record that has (1) a one-sentence summary in `tldr`, (2) a short summary paragraph in `summary` (the site already shows this field when present), and (3) relationships, each with a quote of fewer than 15 words copied word for word from its source, plus a link to that source.
- **Drafter**: a language model that writes the finished entry from the source text. It may be a model on the owner's own computer or a model reached over the internet; the code must not depend on which.
- **Gate**: automatic checks a draft must pass before anyone sees it. A draft that fails never reaches the site.
- **Source text**: the words the drafter is allowed to use: the registry's own description fields for a trial, the FDA record and decision document for a device, the open abstract for a paper.

## Why this exists

Approving a proposal today only creates a bare entry. The roadmap needs about 150 verified, finished records by 22 November (gate G1) and the graph has 11. Approving every sentence by hand is not feasible at that volume, so this step moves most of the checking from people to the gate, and keeps people for the risky items and for a regular sample.

## What the step does

Command: `python3 -m kgkit.draft --config kit.tinnitus.yaml --records records/tinnitus.records.json` (name is yours to choose; keep it one command). It processes every bare entry that has not been drafted yet, up to a configurable cap per run (default 20), and is safe to re-run (never redrafts a finished entry unless asked).

For each bare entry:
1. **Fetch the source text** and store a hash of it. Trials: brief summary, official title, conditions, interventions, primary outcome, from the ClinicalTrials.gov interface already used by the feeds (add the extra fields to the request). Devices: the FDA record fields already fetched plus the decision document when one is linked. If no usable source text can be fetched, stop and queue the record with the reason; do not draft.
2. **Ask the drafter** with a fixed prompt (stored in the repository, versioned). Required output, as structured data: `tldr` (one plain-English sentence, at most 30 words), `summary` (60 to 120 words, plain English, explaining any technical word), and a list of relationships, each with `predicate` (from the allowed list in the configuration), `object` (the id of an existing record), `quote` (fewer than 15 words, word for word from the source text) and the source link.
3. **Rules in the prompt**: use only the source text; never invent a fact; write "no data" instead of guessing; no advice, doses or claims that a treatment works beyond what a quote supports; no regulatory wording (approved, cleared and similar) unless the source is a regulator; neutral tone.
4. **Run the gate** (below). If the draft fails, give the failure reasons back to the drafter once and retry; if it fails again, queue it in `records/draft_queue.json` with the reasons.
5. **Write the result** as a change to the record on a new branch, with the labels the data model already has: `agentType: automated_agent` ("drafted by an agent; not yet checked by a person"), `knowledgeLevel: knowledge_assertion`, plus a provenance note (which model, date, source hash). The export to the Biolink format must still validate.

## The gate (all must pass, no person involved)

1. Every quote appears word for word in the stored source text. The existing quote check only reads paper abstracts; extend it so it also checks registry and FDA text.
2. Every identifier resolves (existing check).
3. Every `object` is an existing record id; every `predicate` is on the allowed list.
4. Lengths and format are as above; `tldr` and `summary` contain no banned phrases (a configurable list, for example "cures", "proven to", "guaranteed").
5. The existing audit rules pass, including the regulatory-wording rule.

## Who looks at what (review modes)

A configuration switch `drafting.review_mode` with two values:
- `person` (default until the owner decides otherwise): every draft goes into the nightly approval flow as a proposal to tick and merge, as today.
- `sampled`: drafts in **tier A** that pass the gate are merged automatically and shown on the site labelled "Drafted by an agent, passed automatic checks, not reviewed by a person". A person reads a random sample each week (at least 10 records or 10 percent, whichever is larger). If more than 5 percent of the sample has a factual error, the step switches itself back to `person` and says so in the digest.

Tier A: trial records whose drafts passed the gate. **Tier B (always `person`, in both modes)**: every device record, any draft containing regulatory wording, any claim that a treatment helps or harms, and any draft the gate marked borderline.

The owner decides which mode to use after the first sample. Build both.

## The sample audit (gate G1)

A second command picks 30 random finished entries and writes `reports/draft_audit.md`: for each, the source text, the draft and an empty verdict column; plus, optionally, a verdict from a second model. The report shows the error rate. The roadmap's pass bar: 5 percent or fewer with a factual error.

## Where it runs (important dependency)

The nightly job runs on GitHub's servers and cannot reach a model on the owner's own computer. So the drafting step is a separate command that the owner's agent server (or any computer with the repository and push access) runs on a schedule, reading and writing through the repository. The model's address, name and key come from configuration or environment variables, never from the code. A later option is to run it on GitHub with a hosted model and a stored key; do not build that now, but do not make it hard.

## Scope of version 1

In: trial records and device records; adding the missing `summary` to the 11 existing records is a one-off task that follows the same gate. Out: paper records, treatment pages and evidence grades (version 2), the synthesis pages, the review page.

## Definition of done

1. All tests pass (`BIOLINK_DIR=<Biolink model folder at tag v4.4.6> python3 -m pytest -q tests`); the count rises, never falls.
2. New tests with stand-in responses: a good draft passes; a draft with an invented quote fails; a draft with banned wording fails; a failed draft is retried once then queued; a device draft is always routed to `person`; the mode switch works; re-running changes nothing.
3. Live check still says all clear and the export still validates.
4. A dry run on 5 real bare entries produces `reports/draft_audit.md` and the owner can read it in under 10 minutes.
5. Report back: what changed, test count before and after, the dry-run result, and anything that deviated from this brief.
