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

## Two kinds of entry

Most entries are **measure entries**: a business term resolved to a dataset, a
measure and a filter, as above. They answer "what number is this".

A few are **vocabulary entries**: a term the agent must understand to read the
question at all, but which no single dataset answers. Season codes, field
roles, team acronyms, source system names. They carry `kind: vocabulary` and
omit `dataset` and `measure`. They live in `seasons.md`, `organisation.md` and
`systems.md`.

```
## season code
kind: vocabulary
aliases: season, saison, 26A, 26B, what season, which season
verified: 2026-08-06
Prose explaining the term and, crucially, what it stops the agent doing —
here, that no dataset is season-agnostic so a question naming no season
cannot be answered without asking.
```

A vocabulary entry earns its place by preventing a wrong answer, not by being
a definition. If the entry does not change what the agent would do, leave it
out. The useful ones say "this term is ambiguous, ask which", "this number
means something different from the one you'd reach for", or "this acronym
names a team whose figures legitimately differ from another team's".

Mark inferred expansions as inferred. `AFD` and `RBM` are written down in
`organisation.md` with the expansion flagged as probable, because the source
documents use the acronym without ever expanding it. An agent that states an
unverified expansion as fact in a report to the field will be wrong in public.

## Recognised fields

- `kind` — `vocabulary` for entries with no dataset. Omit for measure entries.
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

Check the grain against the data, not against the dataset name. Compare
`COUNT(*)` to `COUNT_DISTINCT(<the entity key>)`. If they differ, the dataset
is not one row per entity, and **some of its columns will be repeated across
the rows rather than split across them**. Summing a repeated column
double-counts. On `26A_Credit_DistrRepaymentMultiS` credit is split and
repayment is repeated, so `SUM` is right for one and wrong for the other on the
same table — a distinction no dataset name will ever tell you. Where a measure
needs a per-entity rollup before it is aggregated, say so in the entry.

Entries do not compose. Two verified entries cannot be combined into a third by
an agent, because the join key, the grain and the treatment of zero-versus-null
are exactly what verification settled and none of them survive being inferred.
A question that crosses two entries needs its own entry.

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

Say when a measure needs SQL. `aggregate_dataset` takes plain column names
only, so any measure that is an expression — `SUM(a - b)`, a filter comparing
two columns — has to go through `execute_sql_query`. Underpayment and
overpayment are both like this. An entry whose `measure` line cannot be pasted
into `aggregate_dataset` must say so, or the agent will try and fail.

Name the season. Nearly every dataset here is one season wide, with the season
in the dataset name, the column name or the project key. An entry that does not
state which season it covers will be applied to the wrong one.

Distinguish the dataset figure from the published figure. Dashboard numbers
have usually had claims corrections and prior-season overpayment offsets
applied; the raw dataset has not. Where the two differ materially — 26A
underpayment is 4.6Bn in the data and 778M on the dashboard — say so in the
entry and say which basis was used when reporting.
