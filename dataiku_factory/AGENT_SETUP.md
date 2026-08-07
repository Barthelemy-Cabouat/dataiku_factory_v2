# Setting up a structured DSS agent

End-to-end setup for a Dataiku agent that answers business questions from a
governed set of definitions rather than inferring them from dataset names.

Written against **DSS 14.7**. Where a UI label may have moved, the function is
described rather than the exact menu path.

---

## 0. Prerequisites

**Code environment.** Python 3.11+. The Dataiku docs for Local MCP ask for
`fastmcp>=2.0`; that guidance targets servers launched through `uvx`/`npx`.
This server is a pip-installed console script that imports `mcp.server.fastmcp`
from the `mcp` package, so it needs `mcp>=1.2,<2` and **not** `fastmcp`. Do not
add `fastmcp` back — it is unpinned and can drag `mcp` past the `<2` bound,
which removes the module `server.py` imports.

Package list:

```
dataiku-api-client
python-dotenv
git+https://github.com/Barthelemy-Cabouat/dataiku_factory_v2.git@<sha>#subdirectory=dataiku_factory
```

**API key.** Scope it to the projects the agent should reach. Note the two
identities in play: the Local MCP process runs under the *querying user's* OS
identity under User Isolation, but every DSS API call it makes uses the
`DSS_API_KEY` in the tool's environment. The key is what determines which
projects and connections are reachable, regardless of who is chatting. Never use
an admin key.

**Licence.** Knowledge Bank Search and semantic retrieval need Advanced LLM
Mesh. If your instance reports `Advanced LLM Mesh: No`, the glossary-as-files
approach in this repo is the path that works without it — one reason it was
built that way.

**Admin permission.** An administrator can disable or restrict creation of
Local MCP tools in *Administration > Settings > LLM Mesh*. Confirm it is
permitted before building.

---

## 1. Choose the agent type

DSS 14 offers three:

| Type | What it is | Use when |
|---|---|---|
| Simple Visual Agent | One LLM plus tools, free-running loop | Prototyping, low-stakes Q&A |
| **Structured Visual Agent** | A sequence of blocks with deterministic control | **Recommended here** |
| Code Agent | Python, full control | Logic the blocks cannot express |

Use a **Structured Visual Agent**. The reason is specific rather than
stylistic: in a simple agent, "call `lookup_concept` before choosing a dataset"
is a *request* in the prompt, and the first real trace we captured showed an
agent ignoring exactly that kind of instruction — it went straight to sampling
and produced a wrong total. A structured agent lets you make that step
**mandatory** rather than hoped-for.

Start from a Simple Visual Agent to prove the tools work, then convert.

---

## 2. Create the Local MCP tool

Create a tool of type **Local MCP** and configure the process:

```
command: /data/dataiku/dss_data/code-envs/python/agent-mcp-trial/bin/dataiku-mcp-server
args:    (none)
env:     DSS_HOST=https://your-dss:10000
         DSS_API_KEY=<scoped key>
         DSS_INSECURE_TLS=false
```

There is a **Paste config** button that fills this from a standard MCP JSON
block, and a **Load tools** button that enumerates what the server exposes.

Four traps, each of which cost real time:

- **Use local, non-containerized execution.** Absolute host paths do not resolve
  inside a container image; a containerized tool reports
  `[Errno 2] No such file or directory` for a launcher that plainly exists.
- **No quotes around the command.** A literal-quoted path produces
  `No such file or directory: '"/data/..."'`.
- **The console script is `dataiku-mcp-server`**, not `dataiku-mcp`.
- **Every tool is disabled by default.** Enable them deliberately (§3).

Press **Load tools** again after every code env update, or DSS keeps serving the
previous tool list and your new tools never appear.

### Deploying code changes

Pin the commit SHA in the package list, then run the **code env's own update** —
*not* the image rebuild under Containerized execution. These are different
actions and only the first touches the host venv the MCP actually runs from. We
lost an evening to a build that correctly installed the new commit into the
container image while the venv stayed nine hours stale.

Confirm from the log that pip wrote to
`/data/dataiku/dss_data/code-envs/python/agent-mcp-trial/lib/python3.11/site-packages`.
To verify from inside DSS, run the `mcp_env_diagnostic` notebook in DSSTESTBART:
it prints the installed commit from `direct_url.json` and checks that the new
modules are present.

Pinning the SHA is not only for reproducibility. With `@main` unchanged and the
version still `0.1.0`, pip has grounds to skip the reinstall entirely.

---

## 3. Enable the right tools

Read-only set, plus the glossary:

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
disabled. The first captured trace had all of them enabled.

On `execute_sql_query`: it runs arbitrary SQL with whatever the connection's
credentials permit, including DDL and DML. `aggregate_dataset` covers the
analytical cases through an allowlist with schema-validated column names, so
prefer it and leave `execute_sql_query` off unless someone genuinely needs
ad-hoc SQL against a read-only connection.

Wrap anything mutating in **Human approval**.

---

## 4. Build the structured agent

Blocks, in order. Names match the DSS block palette.

**Routing** — first block. Branch on whether the question concerns data at all.
Send greetings and meta questions to a plain response; send data questions
onward. This stops trivial messages from spinning up tool calls.

**Manual and Mandatory Tool Call** — force `lookup_concept` with the user's
question before any dataset is touched. This is the block that earns the
structured agent. The glossary stops being advice and becomes a step that
cannot be skipped.

**Routing** (second) — branch on whether the lookup matched:

- matched → continue to the loop with the agreed dataset, measure and filter
- no match → ask which dataset is meant, and stop

That second branch is the guardrail. Thirty-two datasets in BURUNDI_BIZOPS begin
`VFINERACT_CLIENTS`, and a free-running agent will happily pick
`..._QC_Final_1` and return a confident wrong number rather than an error. See
the *Conversational Disambiguation* how-to in the DSS docs for the same pattern
applied more generally.

**Agentic Loop** — the MCP tools, with the glossary entry already in state. Set
**Exit Conditions** so the loop ends once an aggregate has been computed rather
than wandering. Our unfixed baseline took six iterations and five LLM calls for
one question; the fixed path is one `aggregate_dataset` call.

**Context Compression** — worth adding once conversations run long. DSS replays
the whole message history on every iteration, so an oversized tool result is
re-billed on every subsequent turn. This is the same failure that made
`get_connections` cost ~50k tokens four times in a single run.

**Generate Text Output** — final answer. Template it to always carry the dataset
name, the measure, and the row counts behind the figure.

Other blocks worth knowing: **Delegate to Another Agent** if you later split by
domain; **Long-Term Memory** for cross-conversation recall; **Reflection** for
self-check on high-stakes answers; **Parallel** and **For Each** for fan-out.

### Wire format (building the graph via the API)

Learned empirically on DSS 14.7 by PUT-and-read-back against
`/projects/<key>/agents/<id>` — the UI names do not match the JSON:

- Block types: the "Agentic Loop" is `CORE_LOOP`; "Generate Text Output" that
  *calls an LLM* is `LLM_REQUEST` — `GENERATE_OUTPUT` is a CEL *template*
  block and silently drops `llmId`/prompt fields. Full legal list (from the
  API's own rejection message): `CONTEXT_COMPRESSION, ROUTING, GENERATE_OUTPUT,
  CORE_LOOP, STANDARD_REACT, SET_STATE_ENTRIES, SET_SCRATCHPAD_ENTRIES,
  LLM_REQUEST, FOR_EACH, REFLECTION, DELEGATE_TO_OTHER_AGENT,
  MANDATORY_TOOL_CALL, EMIT_OUTPUT, CUSTOM, GENERATE_ARTIFACT, PYTHON_CODE,
  EDIT_LAST_USER_MESSAGE, MANUAL_TOOL_CALL, PARALLEL`.
- **Blocks do not chain by array order.** Every block needs an explicit
  `nextBlock`, or the turn ends after it. This is exactly why the original
  stub returned nothing.
- **A routing clause prompt is the entire protocol.** DSS sends the clause
  text as system messages around the history with no added instructions; a
  descriptive clause ("the question concerns data") makes the model answer
  the question in prose and the EXACT matcher then falls through to the
  default. Write clauses as strict classifiers: "Reply with exactly true …
  exactly false … no other words."
- Instruction slots are `systemPromptBeforeHistory` / `systemPromptAfterHistory`
  on `LLM_REQUEST`, `CORE_LOOP` and routing clauses. `MANDATORY_TOOL_CALL`
  takes plain `systemPrompt`, and pins its subtool via `tool.subtoolName`.
- `CORE_LOOP` defaults `passConversationHistory` to **false** — set it true or
  the loop cannot see the question. `exitConditions: []` and
  `maxLoopIterations` are its caps.
- Unknown *fields* are dropped silently; unknown *types* reject the whole PUT
  (atomically — nothing saves). The discovery loop is therefore safe: PUT best
  guess, GET back, keep what survived.

Verified working graph, ~$0.13/question: `Routing` (strict-classifier clause →
`Glossary lookup`, defaultNextBlock → `Direct answer` [LLM_REQUEST]) →
`Glossary lookup` (MANDATORY_TOOL_CALL, subtoolName `lookup_concept`,
nextBlock `Answer loop`) → `Answer loop` (CORE_LOOP, MCP tool, history on,
maxLoopIterations 8).

### Prompts

Paste the description matching the tool's audience —
`MCP_DESCRIPTION_CONSUMER.txt` for the readonly tool
(`DATAIKU_MCP_TOOLSET=readonly`), `MCP_DESCRIPTION_CONTRIBUTOR.txt` for the
full one — into the Local MCP tool's description, and
`AGENT_PROMPT.md` into the agent's description, plus:

```
## Business terms

When a question uses a business term rather than naming a dataset - "clients",
"total credit", "distributions" - the glossary lookup has already run and its
result is in your context. Use the dataset, measure and filter it gives you.

Do not choose a dataset by name similarity. Names in this instance are
deliberately close: 32 datasets begin VFINERACT_CLIENTS and only one answers
"how many clients". Picking wrong returns a plausible number, not an error.

If the lookup found nothing, say the term is not defined and ask which dataset
is meant. Do not fall back to searching for a likely-looking name.
```

---

## 5. Test

Use **Agent Chat** to run questions, and **Tracing** to inspect the trajectory —
that is where you see which tools were called, in what order, with what
arguments. The raw backend log is also readable and is what we used to diagnose
the sampling failure.

Three cases:

| Ask | Expect |
|---|---|
| "How many clients do we have in Burundi?" | `lookup_concept` first, then `aggregate_dataset` on `VFINERACT_CLIENTS_BI`, `COUNT_DISTINCT(CLIENT_ID)` filtered to `CLIENTSTATUS = 'Active'`, answer **634,481** |
| "What is the total credit based on Credit_avec_CET?" | One `aggregate_dataset` call, **41,097,314,734** over 532,455 rows, and it should *mention* that only 418,746 rows are non-null |
| "What's our total revenue?" | Not defined — the agent should say so and ask, not find something plausible |

Failure signs: going straight to `search_project_objects`; landing on a `_QC_`
or `_prepared` dataset; using `get_dataset_sample` to compute a figure;
reporting a number without naming the dataset.

Enable **Agent Interaction Logging** before letting anyone else use it, so you
have a record of real questions to evaluate against. **Agent Review** and
**Agent Evaluation** turn those into a regression set.

---

## 6. Publish

**Agent Hub** exposes the agent to business users inside DSS. For the chat
surfaces in your roadmap, DSS 14 has first-party **Slack Integration** and
**Microsoft Teams Integration** — start with Slack, since it is supported
natively and avoids building a bridge. Google Chat and Gmail have no native
integration and would need the API node plus a custom connector.

Before any of that: deploy to the automation node with a pinned SHA, not
`@main`. A branch-tracking package spec means the agent's behaviour changes
whenever someone merges, silently, with no signal that tool descriptors moved.

---

## 7. Troubleshooting

Every one of these was hit during the build.

| Symptom | Cause | Fix |
|---|---|---|
| `No matching distribution found for fastmcp` | Code env on Python 3.9 | New env on 3.11+; and drop `fastmcp` entirely — this server does not use it |
| `No recorded image tag for env` | Containerized execution on | Switch the tool to local execution |
| `[Errno 13] Permission denied` on project lib | User Isolation: `config/` is 0700 `dataiku`, code runs as `dssuser_*` | Do not use the project library; pip-install from Git |
| `No such file or directory: '"/data/..."'` | Literal quotes in the command field | Remove the quotes |
| `.../bin/dataiku-mcp` not found | Wrong console script name | Use `dataiku-mcp-server` |
| `ModuleNotFoundError: No module named 'scripts'` | setuptools flat-layout drops `scripts/` | Entrypoint lives in `dataiku_mcp/cli.py` |
| `Connection closed` at startup | Something wrote to stdout; stdio reserves it for JSON-RPC | All logging to stderr (`cli.py` forces this) |
| `SSLError: record layer failure` | HTTPS sent to a plain-HTTP listener on :10000 | Fix the scheme. `DSS_INSECURE_TLS` will not help — that is for cert errors |
| `NotAuthenticatedException: Unknown API Key` | Key rotated or stale in `.env` | Update the key where the MCP reads it |
| New tools do not appear | Descriptor cached | Press **Load tools** again |
| Code changes do not take effect | Image rebuilt, host venv untouched | Run the code env update; verify with `mcp_env_diagnostic` |
| `relation "X" does not exist` | SQL built from the DSS dataset name | Use `resolve_dataset_sql_location`; `aggregate_dataset` does it for you |
| Glossary empty but package imports | `context/*.md` not shipped | `[tool.setuptools.package-data]` in `pyproject.toml` |
| `ValidationException: toolSpec.name … length less than or equal to 64` (Bedrock) | MCP tool's **name** is too long: DSS exposes each subtool as `<sanitised name>_<hash>__<subtool>` | Rename the tool. Budget: **name ≤ 24 chars** for the full toolset, **≤ 26** for readonly (see below) |

### Naming a Local MCP tool

Bedrock rejects any tool name over 64 characters, and DSS builds the exposed
name by prefixing every subtool with the sanitised tool name plus a 6-char
hash — 10 characters of overhead beyond the name itself. Non-alphanumerics
become underscores, so `Dataiku MCP (contributor, full)` becomes a 41-character
prefix and blows the budget on the eight longest subtools.

```
len(tool_name) + 10 + len(longest_subtool) <= 64
```

Longest subtool is `clear_jupyter_notebook_outputs` (30) in the full set and
`get_jupyter_notebook_outputs` (28) in the readonly set, giving **24** and
**26** characters respectively. `Dataiku MCP full` and `Dataiku MCP RO` both
fit with room to spare.

The failure is silent until an agent actually runs: DSS saves the tool, loads
its descriptor and lists the subtools happily. Only the model provider rejects
it, so the error surfaces as a failed *chat*, not a failed configuration.

---

## 8. Security

The API key is the real permission boundary. Every tool acts with that key's
privileges no matter who is talking to the agent, so scope it to the project and
prefer read-only connections.

Prompt injection reaches these tools through dataset descriptions, wiki bodies
and discussion threads — all of which the agent reads and none of which are
trusted input. A read-only tool set is the reliable mitigation; human approval
is the second line.

Do not put a PAT in the code env package list. It is visible to anyone with
admin on that env and lands in build logs. Use DSS-level Git credentials, or
`git+ssh://` with a read-only deploy key readable by the `dataiku` account.

Rotate anything that has been exposed, and confirm the old key is deleted rather
than merely replaced.

---

## Maintaining the glossary

Entries live in `dataiku_mcp/context/`, one file per domain; format and rules are
in `_conventions.md` (files starting with `_` are documentation and are not
loaded).

Adding a concept is a pull request: write the entry, verify the number against
the data, set `verified` to today's date. That review step is the point — it is
where "which dataset means clients" gets decided once, by people who know,
rather than repeatedly and invisibly by a model.

Keep entries short, since they enter an agent's context. Put the *dataset* name
in the entry, never the physical table — `resolve_dataset_sql_location` reads
that from DSS on demand, and hard-coding it means the glossary rots silently
when a table moves.

Because the files ship inside the package, updating the glossary currently means
a code env update. If that cadence becomes painful, move entries to DSS wiki
articles and read them with the `get_wiki_article` tools — editable in the UI
with no rebuild, at the cost of version control and the review gate.

---

## Reference

- [AI Agents](https://doc.dataiku.com/dss/latest/agents/index.html)
- [Structured Visual Agents](https://doc.dataiku.com/dss/latest/agents/structured-visual-agents/index.html)
- [Blocks](https://doc.dataiku.com/dss/latest/agents/structured-visual-agents/blocks/index.html)
- [Conversational Disambiguation how-to](https://doc.dataiku.com/dss/latest/agents/structured-visual-agents/how-to/conversational-disambiguation.html)
- [Local MCP](https://doc.dataiku.com/dss/latest/agents/tools/local-mcp.html)
- [Human approval](https://doc.dataiku.com/dss/latest/agents/tools/human-approval.html)
- [Tracing](https://doc.dataiku.com/dss/latest/agents/tracing.html)
- [Agent Evaluation](https://doc.dataiku.com/dss/latest/agents/evaluation.html)
- [Slack Integration](https://doc.dataiku.com/dss/latest/agents/slack.html)
- [User Isolation](https://doc.dataiku.com/dss/latest/user-isolation/index.html)
