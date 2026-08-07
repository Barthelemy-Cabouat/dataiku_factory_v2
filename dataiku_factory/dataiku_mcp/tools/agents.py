"""
Agent and LLM Mesh tools for Dataiku MCP integration.

Read, test and observe DSS-managed agents. Deliberately read-only: nothing here
mutates an agent's configuration. See AGENT_TOOLS_SCOPE.md for why the write
tools are held back from the agent-facing tool set.
"""

from typing import Any, Dict, List, Optional

from dataiku_mcp.client import get_client, get_project
from dataiku_mcp.tools.api_helpers import is_sensitive_name, item_get
from dataiku_mcp.tools.llm_cost import _is_billed_span

# Agent type -> the version-settings sub-dict that actually holds its config.
# The dataikuapi convenience properties (e.g. DSSAgentVersionSettings.tools)
# raise on the wrong type, so every read here dispatches on this map instead.
_AGENT_SETTINGS_KEY = {
    "TOOLS_USING_AGENT": "toolsUsingAgentSettings",
    "STRUCTURED_AGENT": "structuredAgentSettings",
    "PYTHON_AGENT": "pythonAgentSettings",
    "PLUGIN_AGENT": "pluginAgentSettings",
    "RAGLLM": "ragllmSettings",
}

_REDACTED = "***HIDDEN***"


def _redact(value: Any, key_hint: str = "") -> Any:
    """
    Recursively mask credentials in a settings structure.

    Handles two shapes seen in real agent-tool configs:
      * ordinary dicts, where the *key* names the secret ("apiKey": "...")
      * DSS env-var lists, where the secret is a sibling *field*
        ({"name": "DSS_API_KEY", "value": "...", "secret": true})

    The second shape is the one that matters: a stdio-MCP tool config carries
    the DSS API key of the account the agent runs as. Masking only on dict keys
    would return it in cleartext, since the key there is the innocuous "value".
    """
    if isinstance(value, dict):
        # DSS env-entry: redact on the entry's own name/secret flag.
        if "name" in value and "value" in value:
            entry = {k: _redact(v, k) for k, v in value.items() if k != "value"}
            if value.get("secret") is True or is_sensitive_name(str(value.get("name", ""))):
                entry["value"] = _REDACTED
            else:
                entry["value"] = value["value"]
            return entry
        return {
            k: (_REDACTED if is_sensitive_name(k) else _redact(v, k))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v, key_hint) for v in value]
    return value


def list_agents(project_key: str) -> Dict[str, Any]:
    """
    List DSS-managed agents in a project.

    Args:
        project_key: The project key

    Returns:
        Dict containing agent ids, names, types and active versions
    """
    try:
        project = get_project(project_key)
        agents = []
        for item in project.list_agents():
            entry = {"id": item.id, "name": item.name}
            try:
                settings = project.get_agent(item.id).get_settings()
                entry["type"] = settings.type
                entry["active_version"] = settings.active_version
                entry["versions"] = settings.get_version_ids()
            except Exception as e:
                entry["settings_error"] = str(e)
            agents.append(entry)

        return {
            "status": "ok",
            "project_key": project_key,
            "agents": agents,
            "agent_count": len(agents),
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to list agents: {e}"}


def list_agent_tools(
    project_key: str,
    include_shared: bool = False,
) -> Dict[str, Any]:
    """
    List agent tools defined in a project.

    Args:
        project_key: The project key
        include_shared: Also include tools shared from other projects

    Returns:
        Dict containing tool ids, types and names
    """
    try:
        project = get_project(project_key)
        tools = [
            {
                "id": item_get(t, "id"),
                "type": item_get(t, "type"),
                "name": item_get(t, "name"),
                "project_key": item_get(t, "projectKey"),
            }
            for t in project.list_agent_tools(include_shared=include_shared)
        ]
        return {
            "status": "ok",
            "project_key": project_key,
            "tools": tools,
            "tool_count": len(tools),
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to list agent tools: {e}"}


def list_llm_connections(
    project_key: str,
    purpose: str = "GENERIC_COMPLETION",
) -> Dict[str, Any]:
    """
    List LLM Mesh connections usable from a project.

    Args:
        project_key: The project key
        purpose: One of GENERIC_COMPLETION (default),
            TEXT_EMBEDDING_EXTRACTION, IMAGE_GENERATION

    Returns:
        Dict containing the available LLM ids and descriptions
    """
    try:
        project = get_project(project_key)
        llms = []
        for llm in project.list_llms(purpose=purpose):
            llms.append({
                "id": getattr(llm, "id", None),
                "description": getattr(llm, "description", None),
            })
        return {
            "status": "ok",
            "project_key": project_key,
            "purpose": purpose,
            "llms": llms,
            "llm_count": len(llms),
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to list LLM connections: {e}"}


def get_agent_config(
    project_key: str,
    agent_id: str,
    version_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Read an agent's configuration: system prompt, LLM, attached tools, and
    (for structured agents) its block graph.

    Args:
        project_key: The project key
        agent_id: The agent id (see list_agents)
        version_id: Agent version; defaults to the active version

    Returns:
        Dict containing the agent's resolved configuration
    """
    try:
        project = get_project(project_key)
        agent = project.get_agent(agent_id)
        settings = agent.get_settings()
        agent_type = settings.type

        resolved_version = version_id or settings.active_version
        if resolved_version is None:
            return {
                "status": "error",
                "message": f"Agent '{agent_id}' has no active version; pass version_id explicitly.",
            }

        version_settings = settings.get_version_settings(resolved_version)
        raw = version_settings.get_raw()
        config_key = _AGENT_SETTINGS_KEY.get(agent_type)
        config = raw.get(config_key) if config_key else None

        result: Dict[str, Any] = {
            "status": "ok",
            "project_key": project_key,
            "agent_id": agent_id,
            "agent_type": agent_type,
            "version_id": resolved_version,
            "available_versions": settings.get_version_ids(),
            "active_version": settings.active_version,
        }

        if config is None:
            result["config"] = _redact(raw)
            result["note"] = (
                f"Unrecognised agent type '{agent_type}'; returning the full raw "
                "version settings instead of a type-specific view."
            )
            return result

        result["llm_id"] = config.get("llmId")
        result["system_prompt"] = config.get("systemPromptAppend")
        result["tools"] = config.get("tools", [])
        result["completion_settings"] = config.get("completionSettings", {})
        result["interaction_logging"] = config.get("interactionLoggingSelection", {})
        result["short_term_memory_enabled"] = config.get("shortTermMemoryEnabled")
        result["max_loop_iterations"] = config.get("maxLoopIterations")
        result["code_env"] = config.get("codeEnvSelection", {})

        if agent_type == "STRUCTURED_AGENT":
            result["blocks"] = _summarize_blocks(config.get("blocks", []))
            result["starting_block_id"] = config.get("startingBlockId")
            result["next_turn_behaviour"] = config.get("nextTurnBehaviour")

        return result

    except Exception as e:
        return {"status": "error", "message": f"Failed to get agent config: {e}"}


def _summarize_blocks(blocks: List[Any]) -> List[Dict[str, Any]]:
    """Condense a structured agent's block graph to its routing-relevant fields."""
    summary = []
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        entry = {
            "id": block.get("id"),
            "type": block.get("type"),
            "llm_id": block.get("llmId"),
        }
        if block.get("type") == "ROUTING":
            entry["routing_mode"] = block.get("routingMode")
            entry["decisions"] = [
                {
                    "clause_type": (d.get("clause") or {}).get("type"),
                    "next_block": d.get("nextBlock"),
                    "prompt_before_history": (d.get("clause") or {}).get("systemPromptBeforeHistory"),
                    "prompt_after_history": (d.get("clause") or {}).get("systemPromptAfterHistory"),
                }
                for d in block.get("clausesBasedDecisions", []) or []
                if isinstance(d, dict)
            ]
            entry["default_next_block_behavior"] = block.get("emptyDefaultNextBlockBehavior")
        tool = block.get("tool")
        if isinstance(tool, dict):
            entry["tool_ref"] = tool.get("toolRef")
            entry["tool_output_handling"] = tool.get("outputHandling")
        summary.append(entry)
    return summary


def get_agent_tool_config(
    project_key: str,
    tool_id: str,
    include_descriptor: bool = False,
) -> Dict[str, Any]:
    """
    Read an agent tool's configuration, with credentials masked.

    For MCP-client tools this shows which MCP server is wired in: the command,
    args, environment, subtool enable/disable state and timeouts.

    Secrets (API keys, tokens, passwords) are always masked -- a stdio-MCP tool
    config carries the DSS API key of the account the agent runs as.

    Args:
        project_key: The project key
        tool_id: The tool id (see list_agent_tools)
        include_descriptor: Also return the tool's full descriptor, i.e. every
            subtool's name, description and input schema. Off by default: for a
            large MCP server this runs to tens of thousands of tokens, and an
            agent replays every tool result on each subsequent turn.

    Returns:
        Dict containing the redacted tool configuration
    """
    try:
        project = get_project(project_key)
        tool = project.get_agent_tool(tool_id)
        raw = tool.get_settings().get_raw()

        params = raw.get("params", {}) or {}
        result: Dict[str, Any] = {
            "status": "ok",
            "project_key": project_key,
            "tool_id": tool_id,
            "name": raw.get("name"),
            "type": raw.get("type"),
            "params": _redact(params),
            "additional_description_for_llm": raw.get("additionalDescriptionForLLM"),
            "require_human_approval": raw.get("requireHumanApproval"),
            "single_instance": raw.get("singleInstance"),
        }

        # Surface subtool gating explicitly -- this is how tools are withheld
        # from an agent without removing the whole MCP server.
        overrides = params.get("subtoolsStateOverride", {}) or {}
        result["subtools"] = {
            "enabled_by_default": params.get("subtoolsEnabledByDefault"),
            "overrides": overrides,
            "override_count": len(overrides),
            "explicitly_disabled": sorted(
                name for name, state in overrides.items() if state is False
            ),
        }

        if include_descriptor:
            try:
                descriptor = tool.get_descriptor()
                result["descriptor"] = descriptor
                subtools = descriptor.get("subtools", []) if isinstance(descriptor, dict) else []
                result["subtool_count"] = len(subtools)
            except Exception as e:
                result["descriptor_error"] = str(e)
        else:
            try:
                descriptor = tool.get_descriptor()
                subtools = descriptor.get("subtools", []) if isinstance(descriptor, dict) else []
                result["subtool_names"] = [s.get("name") for s in subtools if isinstance(s, dict)]
                result["subtool_count"] = len(subtools)
                result["descriptor_note"] = (
                    "Subtool names only. Pass include_descriptor=true for full "
                    "descriptions and input schemas (large)."
                )
            except Exception as e:
                result["descriptor_error"] = str(e)

        return result

    except Exception as e:
        return {"status": "error", "message": f"Failed to get agent tool config: {e}"}


def get_agent_status(project_key: str, agent_id: str, version_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get the running state of an agent's kernels.

    Reports how many instances are up and their request counters (active,
    successful, failed, cancelled) -- the quickest check for whether an agent
    is actually serving and whether it has been erroring.

    Args:
        project_key: The project key
        agent_id: The agent id
        version_id: Agent version; defaults to the active version

    Returns:
        Dict containing kernel status and aggregate request counters
    """
    try:
        project = get_project(project_key)
        agent = project.get_agent(agent_id)
        status = agent.status(version_id) if version_id else agent.status()

        kernels = status.get("kernels", []) or []
        totals = {
            "active_requests": sum(k.get("nbActiveRequests", 0) for k in kernels),
            "successful_requests": sum(k.get("nbSuccessfulRequests", 0) for k in kernels),
            "failed_requests": sum(k.get("nbFailedRequests", 0) for k in kernels),
            "cancelled_requests": sum(k.get("nbCancelledRequests", 0) for k in kernels),
        }

        return {
            "status": "ok",
            "project_key": project_key,
            "agent_id": agent_id,
            "agent_version_id": status.get("agentVersionId"),
            "kernel_count": len(kernels),
            "running": len(kernels) > 0,
            "kernels": kernels,
            "totals": totals,
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to get agent status: {e}"}


# ---------------------------------------------------------------------------
# Trace inspection
# ---------------------------------------------------------------------------

# Spans worth showing in a flattened trace. The full tree carries a lot of
# bookkeeping spans (enforcement, chunk boundaries) that add noise without
# explaining what the agent did.
_INTERESTING_SPANS = {
    "DKU_AGENT_CALL": "agent_call",
    "DKU_AGENT_ITERATION": "iteration",
    "DKU_AGENT_LLM_CALL": "llm_call",
    "DKU_AGENT_TOOL_CALLS": "tool_calls",
    "DKU_MANAGED_TOOL_CALL": "managed_tool_call",
    "PYTHON_AGENT_TOOL_CALL": "python_tool_call",
    "PYTHON_AGENT_MCP_SUBTOOL_CALL": "mcp_subtool_call",
    "DKU_LLM_MESH_QUERY_ENFORCEMENT": "guardrail_query",
    "DKU_LLM_MESH_RESPONSE_ENFORCEMENT": "guardrail_response",
}


def _flatten_trace(node: Any, steps: List[Dict[str, Any]], depth: int = 0) -> None:
    """Walk a trace tree, emitting one entry per interesting span."""
    if not isinstance(node, dict):
        return

    name = node.get("name")
    usage = node.get("usageMetadata") if isinstance(node.get("usageMetadata"), dict) else None
    billed = _is_billed_span(name)

    if name in _INTERESTING_SPANS or billed:
        attributes = node.get("attributes", {}) or {}
        step: Dict[str, Any] = {
            "depth": depth,
            "span": name,
            "kind": _INTERESTING_SPANS.get(name, "llm_billed_call" if billed else "other"),
            "duration_ms": node.get("duration"),
        }
        if attributes.get("llmId"):
            step["llm_id"] = attributes["llmId"]
        if usage:
            step["prompt_tokens"] = usage.get("promptTokens", 0)
            step["completion_tokens"] = usage.get("completionTokens", 0)
            step["estimated_cost_usd"] = usage.get("estimatedCost", 0.0)

        # Tool-call spans name the subtool, but spell it differently per span:
        # DKU_MANAGED_TOOL_CALL uses camelCase "subtoolName" (plus toolId/toolType),
        # PYTHON_AGENT_MCP_SUBTOOL_CALL uses snake_case "subtool_name".
        for key in ("subtoolName", "subtool_name", "toolName", "tool_name", "toolRef"):
            if attributes.get(key):
                step["tool"] = attributes[key]
                break
        if attributes.get("toolId"):
            step["tool_id"] = attributes["toolId"]
        if attributes.get("toolType"):
            step["tool_type"] = attributes["toolType"]
        # Args live in inputs.input on the managed span, in attributes on the MCP span
        args = attributes.get("subtool_args")
        if args is None:
            inputs = node.get("inputs")
            if isinstance(inputs, dict):
                args = inputs.get("input")
        if args is not None:
            step["tool_args"] = args
        if attributes.get("nbToolCalls") is not None:
            step["tool_call_count"] = attributes["nbToolCalls"]

        steps.append(step)
        depth += 1

    for child in node.get("children", []) or []:
        _flatten_trace(child, steps, depth)


def summarize_trace(trace: Any) -> Dict[str, Any]:
    """
    Flatten an LLM Mesh / agent trace into an ordered step list with costs.

    This is the default way to look at a trace. The raw nested JSON for a single
    agent turn runs to thousands of tokens and is mostly bookkeeping spans; the
    flattened form answers the questions people actually ask -- how many
    iterations, which tools ran, where the tokens went.
    """
    steps: List[Dict[str, Any]] = []
    _flatten_trace(trace, steps)

    billed = [s for s in steps if "estimated_cost_usd" in s]

    # One real tool invocation appears as a *nest* of spans -- managed_tool_call
    # wrapping python_tool_call wrapping mcp_subtool_call. Counting every span
    # reports 3 calls where 1 happened. The managed_tool_call span is the one
    # emitted once per actual invocation, so count only those.
    tool_steps = [s for s in steps if s["kind"] == "managed_tool_call"]
    # Read the subtool name off the managed span: it is emitted once per real
    # invocation and carries the richest attributes (tool id, type, args).
    tools_invoked = [
        {"tool": s.get("tool"), "tool_id": s.get("tool_id"), "args": s.get("tool_args")}
        for s in tool_steps
        if s.get("tool")
    ]

    return {
        "steps": steps,
        "step_count": len(steps),
        "iteration_count": sum(1 for s in steps if s["kind"] == "iteration"),
        "tool_call_count": len(tool_steps),
        "tools_invoked": tools_invoked,
        "llm_call_count": len(billed),
        "totals": {
            "prompt_tokens": sum(s.get("prompt_tokens", 0) for s in billed),
            "completion_tokens": sum(s.get("completion_tokens", 0) for s in billed),
            "total_tokens": sum(
                s.get("prompt_tokens", 0) + s.get("completion_tokens", 0) for s in billed
            ),
            "estimated_cost_usd": sum(s.get("estimated_cost_usd", 0.0) for s in billed),
        },
    }


def test_agent_prompt(
    project_key: str,
    agent_id: str,
    message: str,
    include_raw_trace: bool = False,
) -> Dict[str, Any]:
    """
    Send a test prompt to an agent and return its answer with a cost breakdown.

    Runs the agent for real -- it will call its tools and incur real LLM spend.
    The returned trace summary shows each iteration, which tools were invoked,
    and the tokens and cost attributable to each LLM call.

    Args:
        project_key: The project key
        agent_id: The agent id (see list_agents)
        message: The prompt to send
        include_raw_trace: Also return the full nested trace JSON. Off by
            default -- it is very large and rarely needed once the flattened
            summary is available.

    Returns:
        Dict containing the agent's reply, a step-by-step trace summary and
        total cost
    """
    try:
        project = get_project(project_key)
        agent = project.get_agent(agent_id)

        response = agent.as_llm().new_completion().with_message(message).execute()

        result: Dict[str, Any] = {
            "status": "ok" if response.success else "error",
            "project_key": project_key,
            "agent_id": agent_id,
            "success": response.success,
            "text": response.text,
        }

        trace = getattr(response, "trace", None)
        if trace:
            result["trace_summary"] = summarize_trace(trace)
            if include_raw_trace:
                result["raw_trace"] = trace
        else:
            result["trace_note"] = "No trace returned for this agent invocation."

        return result

    except Exception as e:
        return {"status": "error", "message": f"Failed to test agent prompt: {e}"}


def get_agent_run_cost(
    project_key: str,
    agent_id: str,
    message: str,
) -> Dict[str, Any]:
    """
    Measure what one agent turn costs, broken down per iteration.

    Same execution path as test_agent_prompt but returns only the cost view --
    use this when comparing models or measuring the price of a prompt change,
    and test_agent_prompt when the answer itself matters.

    Note this runs the agent for real; the cost reported is the cost of that
    run, and it was genuinely spent.

    Args:
        project_key: The project key
        agent_id: The agent id
        message: The prompt to send

    Returns:
        Dict containing per-call and total token/cost figures
    """
    try:
        project = get_project(project_key)
        agent = project.get_agent(agent_id)
        response = agent.as_llm().new_completion().with_message(message).execute()

        trace = getattr(response, "trace", None)
        if not trace:
            return {
                "status": "error",
                "message": "No trace returned; cannot determine cost for this agent.",
            }

        summary = summarize_trace(trace)
        billed = [s for s in summary["steps"] if "estimated_cost_usd" in s]

        return {
            "status": "ok",
            "project_key": project_key,
            "agent_id": agent_id,
            "iteration_count": summary["iteration_count"],
            "tool_call_count": summary["tool_call_count"],
            "llm_calls": [
                {
                    "llm_id": s.get("llm_id"),
                    "prompt_tokens": s.get("prompt_tokens", 0),
                    "completion_tokens": s.get("completion_tokens", 0),
                    "estimated_cost_usd": s.get("estimated_cost_usd", 0.0),
                }
                for s in billed
            ],
            "totals": summary["totals"],
        }

    except Exception as e:
        return {"status": "error", "message": f"Failed to get agent run cost: {e}"}


def get_llm_cost_quotas() -> Dict[str, Any]:
    """
    Read LLM Mesh cost quotas: limits, spend to date and blocking status.

    Requires an admin API key. With a non-admin key DSS returns
    "Action forbidden, you are not admin" and this tool reports that plainly
    rather than implying no quotas exist.

    Returns:
        Dict containing the cost-limiting counters
    """
    try:
        client = get_client()
        counters = client.get_llm_cost_limiting_counters()
        return {"status": "ok", "counters": counters}
    except Exception as e:
        message = str(e)
        if "not admin" in message.lower() or "forbidden" in message.lower():
            return {
                "status": "error",
                "message": (
                    "Reading cost quotas requires an admin DSS API key; the key this "
                    "MCP server is configured with is not an admin key. Quotas may "
                    "well be configured -- they just cannot be read from here. "
                    "View them at Administration > Settings > LLM Mesh > Quotas."
                ),
                "underlying_error": message,
            }
        return {"status": "error", "message": f"Failed to get LLM cost quotas: {message}"}
