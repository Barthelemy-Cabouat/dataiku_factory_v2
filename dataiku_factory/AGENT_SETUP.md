# Setting up a structured DSS agent

How to configure the Dataiku agent so it answers business questions from a
governed set of definitions rather than inferring them from dataset names.

The architecture is one agent with layered context:

| Layer | Lives in | Cost | Change cadence |
|---|---|---|---|
| Identity and rules | Agent description in DSS | Resent every iteration | Rarely |
| Tool routing | MCP tool description | Resent every iteration | Rarely |
| Business glossary | `dataiku_mcp/context/*.md`, read on demand | One small tool call | Weekly |
| The data | DSS datasets via MCP tools | Per query | Constantly |

Only the first two are always in context. The glossary is retrieved when
needed, which is what lets it grow to hundreds of concepts without inflating
every turn. An agent framework replays the whole message history on each
iteration, so anything pinned in the prompt is paid for repeatedly.

## Why a glossary at all

"How many clients do we have?" cannot be answered from schemas. BURUNDI_BIZOPS
contains **32 datasets** whose names begin `VFINERACT_CLIENTS`. Only
`VFINERACT_CLIENTS_BI` is correct; `..._QC_Final_1`, `..._Duplicates`,
`..._prepared` and the rest are flow intermediates. Every one of them returns a
number. None of them errors.

That is the failure mode worth engineering against: not a missing answer, but a
confident wrong one. Two real traps already captured in the glossary:

- `OAFID` looks like the obvious One Acre Fund client identifier and is **null
  in all 634,503 rows**. `COUNT_DISTINCT(OAFID)` returns 0 — an agent would
  report "no clients".
- The DSS dataset is `VFINERACT_CLIENTS_BI`, but the Snowflake table behind it
  is `PRODUCTION.CLIENT.VFINERACT_CLIENTS_BU`. Different suffix.

## Step 1 — Deploy the code

The glossary tools ship inside the package. Pin the commit in the code env's
package list:

```
git+https://github.com/Barthelemy-Cabouat/dataiku_factory_v2.git@<sha>#subdirectory=dataiku_factory
```

Then run the **code env's own update** — not the container image rebuild under
Containerized execution. Those are different actions, and only the first touches
the host venv the Local MCP tool actually executes from. Confirm success in the
log: pip should write to
`/data/dataiku/dss_data/code-envs/python/agent-mcp-trial/lib/python3.11/site-packages`.

Re-fetch the tool descriptor afterwards or the agent keeps offering the old tool
list.

## Step 2 — Enable the right tools

Read-only set, plus the two glossary tools:

```
lookup_concept, list_concepts,
resolve_dataset_sql_location, aggregate_dataset,
inspect_dataset_schema, get_dataset_sample,
search_project_objects, get_project_flow,
get_recent_runs, get_job_activities, get_job_log,
get_connections, get_code_environments,
list_wiki_articles, get_wiki_article
```

Leave every `delete_*` tool, `batch_update_objects` and `cancel_running_jobs`
disabled. Wrap anything mutating in DSS's **Human approval**.

On `execute_sql_query`: it runs arbitrary SQL with whatever the connection's
credentials permit, including DDL and DML. `aggregate_dataset` covers the
analytical cases through an allowlist with schema-validated column names, so
prefer it and leave `execute_sql_query` off unless someone needs ad-hoc SQL and
the connection is read-only.

## Step 3 — Set the MCP tool description

Paste `MCP_DESCRIPTION.txt` into the Local MCP tool's description field. It
covers tool routing and the hard rules about aggregates and dataset naming.

## Step 4 — Set the agent description

Paste `AGENT_PROMPT.md` into the agent's description, and add this section so
the agent reaches for the glossary before it reaches for a dataset:

```
## Business terms

When a question uses a business term rather than naming a dataset - "clients",
"total credit", "distributions" - call lookup_concept first. It returns the
agreed dataset, measure and filter, plus known data quality traps.

Do not choose a dataset by name similarity. Names in this instance are
deliberately close: 32 datasets begin VFINERACT_CLIENTS and only one answers
"how many clients". Picking wrong returns a plausible number, not an error.

If lookup_concept finds nothing, say the term is not defined and ask which
dataset is meant. Do not fall back to searching for a likely-looking name.
```

## Step 5 — Verify

Ask the agent "how many clients do we have in Burundi?" and check the trajectory:

1. `lookup_concept("number of clients")` — before touching any dataset
2. `aggregate_dataset` on `VFINERACT_CLIENTS_BI`, `COUNT_DISTINCT(CLIENT_ID)`,
   filtered to `CLIENTSTATUS = 'Active'`
3. An answer of **634,481**, citing the dataset

Failure signs: going straight to `search_project_objects`; landing on a `_QC_`
or `_prepared` dataset; using `get_dataset_sample` for the count; reporting a
figure with no dataset named.

Then try "what's our total revenue?" — a term deliberately not in the glossary.
The agent should say it is not defined and ask, rather than finding something
plausible.

## Maintaining the glossary

Entries live in `dataiku_mcp/context/`, one file per domain. Format and rules
are in `_conventions.md` (files starting with `_` are documentation and are not
loaded).

Adding a concept is a pull request: write the entry, verify the number against
the data, set `verified` to today's date. That review step is the point — it is
where "which dataset means clients" gets decided once by people who know, rather
than repeatedly and invisibly by a model.

Two constraints worth respecting. Keep entries short, since they enter an
agent's context. And put the *dataset* name in the entry, never the physical
table — `resolve_dataset_sql_location` reads that from DSS on demand, and
hard-coding it means the glossary silently rots when a table moves.

Because the files ship inside the package, updating the glossary currently means
a code env rebuild. If that cadence becomes painful, the alternative is moving
entries to DSS wiki articles and reading them with the `get_wiki_article` tools
— editable in the UI with no rebuild, at the cost of losing version control and
the review gate.
