# Scope: Agent & LLM tools for the Dataiku Factory MCP

Additions covering agent configuration, observability, testing and cost.
Every capability below was probed against the live instance (DSS 14.7.0,
`DATAIKU_MAINTENANCE`) before being listed — status reflects what actually
worked, not what the docs claim.

## Status

**Shipped** (`dataiku_mcp/tools/agents.py`, registered in `server.py`):
`list_agents`, `list_agent_tools`, `list_llm_connections`, `get_agent_config`,
`get_agent_tool_config`, `get_agent_status`, `test_agent_prompt`,
`get_agent_run_cost`, `get_llm_cost_quotas`, plus `get_llm_call_cost`
(`llm_cost.py`). All read-only.

**Write tools (§3) deliberately not built.** Decision: the agent-facing MCP does
not get configuration-mutation tools. If they are added later for operator use,
disable them for the agent via `subtoolsStateOverride` on the tool config —
`get_agent_tool_config` surfaces that state under `subtools.explicitly_disabled`.

## Verified constraints (read before implementing)

| Constraint | Evidence | Impact |
|---|---|---|
| MCP API key is **not admin** | `get_llm_cost_limiting_counters()` → `UnauthorizedException: not admin`; `project.get_settings()` → `Action forbidden` | Quota tools and project-level interaction-logging config are blocked on this key. Needs an admin key or a scope decision. |
| `agent.get_metrics_series()` **absent** on 14.7.0 | `AttributeError` despite being in v14 docs | Don't build on it; use `agent.status()` instead. |
| `vs.tools` raises on non-simple agents | `ValueError: Only valid for Simple Visual Agents` on a `STRUCTURED_AGENT` | All settings tools must dispatch on `settings.type` (`TOOLS_USING_AGENT`, `STRUCTURED_AGENT`, `PYTHON_AGENT`, `PLUGIN_AGENT`, `RAGLLM`). |
| Tool config contains **live secrets** | `NuBmZ7N` params include `DSS_API_KEY` (AES blob) in `env[]` | Any config-reading tool must redact via the existing `is_sensitive_name` helper. Non-negotiable. |
| Agent traces are **huge** | One test prompt: 17,585 prompt tokens, 2 iterations, ~$0.11 | Never return a raw trace by default. Same payload-bloat problem `get_connections` already documents — an agent replays every tool result each turn. |

## 1. Discovery & inventory (low risk, build first)

| Tool | Purpose | Status |
|---|---|---|
| `list_agents` | Agent ids, names, type, active version | ✅ verified |
| `list_agent_tools` | Tool ids/types/names, incl. `include_shared` | ✅ verified |
| `list_llm_connections` | LLM ids by purpose (completion / embedding / image) | ✅ verified — 3 purposes return distinct sets |
| `list_knowledge_banks` | KBs available for RAG | ✅ callable (currently empty) |
| `list_retrieval_augmented_llms` | RAG LLM handles | ✅ callable (currently empty) |

## 2. Configuration — read

| Tool | Purpose | Status |
|---|---|---|
| `get_agent_config` | Type-aware version settings: system prompt, llmId, tools, completion settings, logging selection | ✅ verified — must branch on agent type |
| `get_agent_tool_config` | For MCP tools: command, args, env, enabled subtools, timeouts, `additionalDescriptionForLLM` | ✅ verified — **must redact secrets** |
| `get_structured_agent_blocks` | Block graph for structured agents: routing clauses, tool-call blocks, start block, transitions | ✅ verified on `mCwnNmE2` |

## 3. Configuration — write (needs review gate)

| Tool | Purpose | Status |
|---|---|---|
| `update_agent_system_prompt` | Set `systemPromptAppend` | ✅ verified mutable + `save()` present |
| `add_agent_tool` / `remove_agent_tool` | Attach/detach a tool from an agent | ✅ `add_tool()` present |
| `set_agent_llm` | Swap `llmId` (e.g. Sonnet → Nova for cost) | ✅ field verified writable |
| `set_mcp_subtools_enabled` | Toggle individual MCP subtools via `subtoolsStateOverride` / `subtoolsEnabledByDefault` | ✅ fields verified present |
| `update_structured_agent_blocks` | Edit routing clauses / block wiring | ⚠️ verified readable; write path untested — highest-risk item, do last |

**Recommendation:** these mutate a production agent. Add a `dry_run: bool = True`
default that returns a before/after diff without saving, mirroring how
`test_recipe_dry_run` already works in this repo.

## 4. Testing

| Tool | Purpose | Status |
|---|---|---|
| `test_agent_prompt` | Send a prompt to an agent, return answer + per-iteration cost + tool calls made | ✅ verified end-to-end via `agent.as_llm().new_completion()` |
| `test_agent_tool` | Invoke one tool/subtool directly with a payload, bypassing the LLM | ✅ `tool.run(input, subtool_name=...)` present |

`test_agent_prompt` is the highest-value item here — it closes the
edit→test→inspect loop entirely inside the MCP, and its trace already carries
the cost data `get_llm_call_cost` extracts.

## 5. Observability

| Tool | Purpose | Status |
|---|---|---|
| `summarize_agent_trace` | **Default view.** Flatten a trace to an ordered step list: iterations, LLM calls, tool calls, per-step tokens/cost, total | ✅ verified — structure below |
| `get_agent_trace` | Raw nested trace JSON, explicitly opt-in, depth-capped | ✅ verified |
| `get_agent_status` | Running kernels, active/failed/successful request counts | ✅ verified |
| `control_agent_kernel` | `wake_up()` / `shutdown(force=)` | ⚠️ documented on `DSSAgent`, untested |
| `get_agent_interaction_logs` | Read the interaction-logging dataset if configured | ⚠️ blocked — needs `project.get_settings()` (403 on this key) |

Verified trace shape from a real agent call:

```
DKU_LLM_MESH_COMPLETION_QUERY
  DKU_LLM_MESH_LLM_CALL
    DKU_AGENT_CALL
      DKU_AGENT_ITERATION
        DKU_AGENT_LLM_CALL
          DKU_LLM_MESH_LLM_CALL_STREAMED   ← usageMetadata (tokens + estimatedCost)
        DKU_AGENT_TOOL_CALLS
          DKU_MANAGED_TOOL_CALL
            PYTHON_AGENT_TOOL_CALL
              PYTHON_AGENT_MCP_SUBTOOL_CALL  ← which subtool ran
      DKU_AGENT_ITERATION
        ...
```

Note `..._STREAMED` — `_collect_llm_call_usage` originally matched only
`DKU_LLM_MESH_LLM_CALL` exactly and silently reported **$0.00 for every agent
turn**. Fixed via `_is_billed_span()` (prefix match, excluding the
`_FIRST_CHUNK` / `_STREAM_COMPLETE` sub-spans). Verified live: a real agent turn
now reports $0.1154 where the old matcher found 0 calls.

Two further gotchas found during implementation, both fixed:

- **Tool-call double counting.** One invocation emits three nested spans
  (`DKU_MANAGED_TOOL_CALL` → `PYTHON_AGENT_TOOL_CALL` →
  `PYTHON_AGENT_MCP_SUBTOOL_CALL`). Counting all of them reported 3 calls where
  1 happened. Only `DKU_MANAGED_TOOL_CALL` is counted.
- **Subtool name spelling differs per span.** `DKU_MANAGED_TOOL_CALL` uses
  camelCase `subtoolName` (plus `toolId`, `toolType`, and args under
  `inputs.input`); `PYTHON_AGENT_MCP_SUBTOOL_CALL` uses snake_case
  `subtool_name` / `subtool_args`. Both are handled.

## 6. Cost

| Tool | Purpose | Status |
|---|---|---|
| `get_llm_call_cost` | Cost of a single prompt | ✅ shipped |
| `get_agent_run_cost` | Cost of a full agent turn, broken down per iteration and per tool call | ✅ data verified present in trace |
| `get_llm_cost_quotas` | Quota definitions, spend to date, blocking status | ⚠️ `get_llm_cost_limiting_counters()` exists but **requires admin** |

## Suggested build order

1. **Discovery + config read** (§1, §2) — read-only, immediately useful, no risk.
2. **`test_agent_prompt` + `summarize_agent_trace`** (§4, §5) — the debugging loop; also fixes the streamed-span gap in `llm_cost.py`.
3. **`get_agent_run_cost`** (§6) — falls out of step 2 nearly free.
4. **Config writes** (§3) with `dry_run=True` default.
5. **Admin-gated items** — only after deciding whether the MCP gets an admin key.

## Open decisions

- **Admin key?** Quotas and interaction logs need one. Granting admin to the MCP
  widens blast radius considerably — worth deciding deliberately rather than by
  default.
- **Write tools at all?** An agent that can rewrite its own system prompt and
  swap its own model is a notable self-modification surface. Consider keeping
  §3 out of the agent-facing subtool set (`subtoolsStateOverride`) while still
  exposing it to human operators via Claude Code.
- **Secret redaction** must land in the same PR as `get_agent_tool_config`, not
  after.
