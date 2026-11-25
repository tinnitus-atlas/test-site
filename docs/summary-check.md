# Summary check

Every summary on the site is compared with its source text by a model from a different family from the one that
wrote it (`kgkit/summary_check.py`). A summary that contradicts its source, with the contradicting passage quoted,
shows "Summary under review" on its page; points not found in the source text go to the nightly digest.

## Where it runs (one place at a time)

| Route | Settings | When to use |
| --- | --- | --- |
| Drafting computer (preferred) | `CHECKER_MODEL` in the drafting job's settings file, a local model from another family than the drafting model | Once the drafting job runs there daily |
| GitHub nightly (fallback) | repository variables `CHECKER_BASE_URL`, `CHECKER_MODEL` and secret `CHECKER_API_KEY` | Until the drafting computer runs it |

Use one route at a time: when the drafting computer takes over, clear `CHECKER_MODEL` in the repository variables.
Both routes write `records/summary_checks.json` through a pull request that merges itself.

## Choosing the model

- The checker is refused for any summary written by its own family, and it refuses to run when its family is unknown.
- A hosted model behind an OpenAI-compatible endpoint works (for example through OpenRouter); give its key a credit
  limit. A model from the same family as the drafter checks nothing that drafter wrote.

## Cost

`summary_check.max_cost_per_run` (default 0.20 US dollars, as reported by the provider) stops a run once reached;
records never checked go first and the rest follow on later nights, so a capped run becomes a rolling spot check.
Unchanged summaries are checked again only after `recheck_days` (default 30). Each run's cost is in the digest.
