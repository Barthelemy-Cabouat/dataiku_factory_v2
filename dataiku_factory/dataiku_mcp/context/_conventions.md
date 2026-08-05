# How to write a glossary entry

Files in this directory are the agent's business glossary. Filenames starting
with `_` are ignored by the loader, so this file is documentation only.

Each entry is a level-2 heading followed by `key: value` lines, then free prose.
Keep entries short — they are read into an agent's context.

```
## number of clients
aliases: client count, how many clients, total clients
project: BURUNDI_BIZOPS
dataset: VFINERACT_CLIENTS_BI
measure: COUNT_DISTINCT(CLIENT_ID)
filter: CLIENTSTATUS = 'Active'
verified: 2026-08-04
Prose notes go here: caveats, lookalike datasets to avoid, known data quality
issues, who owns the definition.
```

## Recognised fields

- `aliases` — comma-separated. The phrasings a user actually types. This is what
  makes lookup work, so be generous and include the sloppy ones.
- `project` — DSS project key.
- `dataset` — the DSS dataset name, exactly. Not the physical table.
- `measure` — the aggregation, written as `aggregate_dataset` would take it.
- `filter` — a SQL predicate for the `where` argument, or omit if none.
- `grain` — what one row represents. Worth stating whenever it isn't obvious.
- `verified` — the date someone last checked this against the data. An entry
  nobody has confirmed in a year should be treated as a hypothesis.

## Rules

State the grain whenever a dataset could be misread as one-row-per-something-else.
Most wrong answers come from a plausible dataset at the wrong grain, not from a
missing dataset.

Name the lookalikes. If a concept has thirty near-identically named datasets
beside it, list the ones to avoid and say why. The agent cannot tell
`VFINERACT_CLIENTS_BI` from `VFINERACT_CLIENTS_BI_QC_Final_1` without help, and
both return a number.

Record known-bad columns. A column that is entirely null, or that looks like the
obvious key but isn't, costs an analyst an afternoon and an agent a wrong answer.

Do not put the physical table name in the entry. It drifts, and
`resolve_dataset_sql_location` reads it from DSS on demand. Name the DSS dataset
and let the tooling resolve it.

Keep one concept per entry. If a phrase has two legitimate meanings, write two
entries and say in each how it differs from the other.
