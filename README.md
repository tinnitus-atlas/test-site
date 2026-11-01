# kg-quality-kit

Nightly quality checks and a Biolink export for an AI-maintained, cited knowledge graph. One configuration file adapts it to a new domain; the first configuration covers tinnitus.

| Check | What it guarantees | Blocking? |
| --- | --- | --- |
| DOI and quote check | Every cited paper is the paper the claim says it is, and every quote appears in that paper's title or abstract (via Europe PMC) | Wrong paper or missing quote holds that record back |
| Fact-check | Trial statuses, phases, completion dates and enrolment agree with ClinicalTrials.gov | No; mismatches become proposals |
| Audit | No missing sources, dangling links, unsourced assertions, duplicates or contradictions | Structural and sourcing errors hold the record back |
| Freshness | No record is older than the limit for its type | Fails the run above the configured share of stale critical records |
| Feeds and proposals | New trials and papers are found, and every suggested change is written up for a person to approve | No; nothing is applied without a merge |
| Biolink export | The graph is exported in the standard KGX format and passes the official KGX validator | Export errors flag the run |

## Contents

| Path | What it is |
| --- | --- |
| `kgkit/` | The checks (Python package) |
| `kit.tinnitus.yaml` | Tinnitus configuration: record kinds, Biolink mapping, freshness limits, registries, feeds |
| `records/tinnitus.records.json` | Ten starter records with sources and short verbatim quotes |
| `export_biolink.py`, `run_validation.sh` | Biolink export and KGX validation |
| `run_nightly.sh` | Pull, check, export, open a pull request with proposals, write `reports/nightly.md` |
| `hermes/nightly-job.md` | Prompts and setup for the nightly job and the monthly upstream watch, run from an AI agent scheduler |
| `hermes/mini-test.md` | Stage 1: put the site on a free pages.dev address and run the first live check |
| `.github/workflows/` | Tests on every change; a one-click live check against the real services |
| `kgkit/apply.py` | Applies proposals ticked and merged in the nightly pull request |
| `site/build_site.py`, `site/assets/` | Static website, JSON API, graph explorer, llms.txt and agent context files (no dependencies beyond PyYAML) |
| `mcp/server.py` | MCP server so AI agents can search and read the published records |
| `tools/upstream_watch.py` | Monthly report of changes to the upstream quality scripts the kit was adapted from |
| `docs/deploy.md` | Step-by-step: GitHub plus Cloudflare Pages hosting |
| `docs/maxo-term-requests.md` | Ready-to-post requests for missing ontology terms |
| `tests/` | Automated tests (network replaced by stand-in responses) |

## Setup on a Mac or Linux server

1. Open a terminal and go to the project folder, for example `cd ~/kg-quality-kit`
2. Create a private Python environment: `python3 -m venv .venv`
3. Turn it on: `source .venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Make the scripts runnable: `chmod +x run_nightly.sh run_validation.sh`

## Run

```bash
python3 -m kgkit --config kit.tinnitus.yaml --records records/tinnitus.records.json --reports reports
python3 -m kgkit ... --offline            # skip the checks that need the internet
python3 -m kgkit ... --only doi,audit     # run a subset
NO_GIT=1 ./run_nightly.sh                 # whole nightly run without touching git
```

Reports land in `reports/`: one JSON file per check, `held_records.json` (records the website must not publish), `proposals.md` (the review checklist), `summary.md` and `nightly.md` (the short digest).

Exit codes: `0` nothing blocking; `1` blocking findings; `2` bad input or the run failed. When a service cannot be reached, the digest says so and marks the run as incomplete instead of reporting all clear.

## Record format

Records follow the Knowledge Quality Kit data contract: `id`, `kind`, `name`, `tldr`, `asOf`, `sources`, optional `xrefs`, `status`, `facts` and `relations`. A relationship that states a fact (`knowledgeLevel: knowledge_assertion`) needs a short verbatim `quote` (under 15 words) and either `publications` (DOI or PMID) or a `sourceUrl`.

## Tests

```bash
git clone --depth 1 --branch v4.4.6 https://github.com/biolink/biolink-model /tmp/biolink-model
BIOLINK_DIR=/tmp/biolink-model python3 -m pytest -q tests
```

## Licence

Code: MIT. Starter records: the facts and short quotes come from the cited sources; check each source's terms before commercial reuse.

## Website

```bash
python3 site/build_site.py --config kit.tinnitus.yaml --records records/tinnitus.records.json --out public
cd public && python3 -m http.server 8000      # preview at http://localhost:8000
```

The builder withholds every record that fails the audit or appears in `records/held_records.json` (written by the nightly run). Hosting: see `docs/deploy.md`.

## MCP server for AI agents

```bash
python3 mcp/server.py --data public/api/v1                    # local build
python3 mcp/server.py --url https://YOUR-SITE/api/v1           # live site
```

Tools: `search_records`, `get_record`, `related_records`, `list_kinds`.
