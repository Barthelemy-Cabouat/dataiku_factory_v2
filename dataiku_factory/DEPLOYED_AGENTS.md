# Deployed agents and tools — live inventory

What exists on the DSS instance right now, with the identifiers you cannot
derive from this repo. Setup reasoning lives in `AGENT_SETUP.md`; scope
decisions in `AGENT_TOOLS_SCOPE.md`. This file is the map.

Instance: DSS 14.7, `dssdesign.oneacrefund.org`. All objects below are in
project **`DATAIKU_MAINTENANCE`**. Last verified 2026-08-07.

---

## Agents

| ID | Name | Type | Role |
|---|---|---|---|
| `YMqznxXq` | Mugisha AI (cost-reporting) | PYTHON_AGENT | **Slack entrypoint.** Proxies the consumer agent, appends the real cost footer |
| `mCwnNmE2` | Mugisha AI structured | STRUCTURED_AGENT | **Consumer.** Read-only, glossary-first. The one users talk to |
| `Brp6xq7c` | Mugisha AI structured (contributor) | STRUCTURED_AGENT | Same graph, full toolset, for people who edit Flows |
| `qZisMtc4` | Mugisha AI | TOOLS_USING_AGENT | **Superseded.** The original free-running agent. Pointing anything at it bypasses every guardrail built here |

**Slack** points at `agent:YMqznxXq`. Its `INNER_AGENT_ID` must be
`agent:mCwnNmE2` — the consumer. Source of truth for that code is
`agents/cost_wrapper.py`; the copy in DSS is a paste of it.

### The consumer graph (`mCwnNmE2`)

```
Routing (ROUTING, strict-classifier clause)
   ├─ matched  → Glossary lookup (MANDATORY_TOOL_CALL, subtoolName=lookup_concept)
   │                 └─ nextBlock → Answer loop (CORE_LOOP, tools=NuBmZ7N,
   │                                maxLoopIterations 8, history ON)
   │                        └─ defaultNextBlock → Report cost (PYTHON_CODE)
   └─ default  → Direct answer (LLM_REQUEST)
```

`Report cost` is inert — DSS gives Python blocks an empty SpanBuilder, so it
yields nothing. The wrapper does the job instead. Safe to remove when the
graph is next edited; the loop's `defaultNextBlock` would need repointing.

LLM throughout: `bedrock:aws-bedrock:anthropic.claude-sonnet-4-6`.

---

## MCP tools

| ID | Name | `DATAIKU_MCP_TOOLSET` | Tools served | Used by |
|---|---|---|---|---|
| `NuBmZ7N` | Dataiku MCP | `minimal` | 14 | `mCwnNmE2` |
| `QxsXmvx` | Dataiku MCP full | *(unset)* | 83 | `Brp6xq7c` |

Both run the same install:

```
command: /data/dataiku/dss_data/code-envs/python/agent-mcp-trial/bin/python
args:    -c   from dataiku_mcp.server import mcp; mcp.run()
env:     DSS_HOST, DSS_API_KEY (secret), DSS_INSECURE_TLS=false
         DATAIKU_MCP_TOOLSET=minimal        (consumer only)
```

Code env **`agent-mcp-trial`** (Python 3.11), package pinned by SHA. Non-
containerized execution — absolute host paths do not resolve in a container
image.

Descriptions to paste into each tool: `MCP_DESCRIPTION_CONSUMER.txt` and
`MCP_DESCRIPTION_CONTRIBUTOR.txt`.

---

## Invariants worth not relearning

**`subtool_count` is the only truth.** Not the env var, not the installed
commit, not the token count. `minimal` = 14, `readonly` = 43, `full` = 83. If
it disagrees, nothing downstream is worth interpreting.

**The toolset gate applies at import** (since `1649081`). It must, because the
tool config launches the server with `-c "…mcp.run()"`, which never calls
`create_server()`. A gate that depends on the entrypoint is not a gate.

**`subtoolsStateOverride` does not restrain an agent.** On 2026-08-07 an agent
whose config had `delete_dataset: false` called it and deleted a dataset.
Config-level gating is advisory; only non-registration holds.

**MCP tool names ≤ 24 characters** (26 for readonly). Bedrock caps
`toolSpec.name` at 64 and DSS prefixes every subtool with the sanitised tool
name plus ~10 characters. Fails only at chat time, never at save time.

**Project variables are not process env vars.** `DATAIKU_MCP_TOOLSET` belongs
on the tool's `env` list. A project variable never reaches `os.environ`.

**Code env update ≠ container image rebuild.** Only the former touches the
venv the MCP runs from.

**Analysis needs no read-only connection.** `aggregate_dataset` and
`count_entities` are safe by construction — allowlisted functions,
schema-validated columns. Only `execute_sql_query` needs the database to police
it.

---

## Baselines

Cost per question, "how many clients do we have?", Sonnet 4.6:

| Toolset | Prompt tokens | $/question |
|---|---|---|
| full (83) | 43,050 | $0.134 |
| readonly (43) | 22,027 | $0.072 |
| **minimal (14)** | **11,677** | **$0.041** |

Prompt caching is not available: DSS 14.7 accounts for cached tokens when a
provider reports them but exposes no way to emit Bedrock cache points.

Verified figures, for checking the agent still answers correctly:

- Active clients — 635,107 (`VFINERACT_CLIENTS_BI`, `COUNT_DISTINCT(CLIENT_ID)`,
  `CLIENTSTATUS='Active'`). Moves daily; the *method* is what's reproducible.
- Total credit 26B — 41,097,314,734 over 532,455 rows, 418,746 non-null.
- Clients with repayment but zero credit, 26A — 2,788.

---

## Open items

- **`QxsXmvx` has an empty `env`** — secrets do not survive API duplication.
  Add `DSS_HOST` / `DSS_API_KEY` / `DSS_INSECURE_TLS` or the contributor agent
  cannot reach DSS.
- **Clear `subtoolsStateOverride` on `NuBmZ7N`** and set
  `subtoolsEnabledByDefault: true`. With the server gate live the overrides are
  a second, weaker gate that will silently disable any tool later added to
  `MINIMAL_TOOLSET`.
- **Remove the unused `PYTHONPATH`** from `NuBmZ7N` — leftover from the
  abandoned library approach, and it precedes `site-packages`.
- **Confirm API key `dkuaps-335f…` is deleted** in DSS. It was committed to a
  briefly-public repo; history has been purged twice but revocation is the only
  real control.
- **Read-only Snowflake connection** — would let `execute_sql_query` return for
  consumers via `DATAIKU_MCP_SQL_CONNECTIONS`, with the database enforcing.
- **Advanced LLM Mesh licence** — reports `No`. Blocks Cost Control quotas and
  Semantic Models. Outstanding with the CSM.
