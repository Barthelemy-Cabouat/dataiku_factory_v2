"""
LLM Mesh cost/usage tools for Dataiku MCP integration.
"""

from typing import Any, Dict, List, Optional
from dataiku_mcp.client import get_project


# Billed spans. A plain completion emits "DKU_LLM_MESH_LLM_CALL"; an agent turn
# emits "DKU_LLM_MESH_LLM_CALL_STREAMED" instead, once per agent iteration.
# Matching the bare name exactly silently returned zero cost for every agent
# call, which is worse than erroring -- a wrong cost still looks like a cost.
_BILLED_SPAN_PREFIX = "DKU_LLM_MESH_LLM_CALL"


def _is_billed_span(name: Any) -> bool:
    """
    True for spans that carry real billing metadata.

    Excludes the streamed sub-spans (..._FIRST_CHUNK, ..._STREAM_COMPLETE),
    which sit *inside* a billed span and carry no usage of their own -- counting
    them would be harmless today (no usageMetadata) but would double-count if
    Dataiku ever populates them.
    """
    if not isinstance(name, str) or not name.startswith(_BILLED_SPAN_PREFIX):
        return False
    return not (name.endswith("_FIRST_CHUNK") or name.endswith("_STREAM_COMPLETE"))


def _has_real_usage(usage: Any) -> bool:
    """
    True only if a usageMetadata dict actually reports consumption.

    On an agent turn the *outer* DKU_LLM_MESH_LLM_CALL span carries an empty
    ``usageMetadata: {}`` -- it wraps the billed inner calls rather than being
    one itself. Treating it as a call inflated "3 LLM calls" for a turn that
    made 2. Cost was unaffected (it sums to zero) but the count was wrong.
    """
    if not isinstance(usage, dict):
        return False
    return bool(
        usage.get("totalTokens")
        or usage.get("promptTokens")
        or usage.get("completionTokens")
        or usage.get("estimatedCost")
    )


def _collect_llm_call_usage(node: Any, calls: List[Dict[str, Any]]) -> None:
    """
    Walk a Dataiku LLM Mesh trace tree and collect usage/cost metadata.

    Usage metadata is attached at the billed LLM-call span -- the level at which
    cost is actually incurred, per Dataiku's own docs. A plain completion
    produces exactly one; an agent turn produces one per iteration, so the whole
    tree is walked and summed.
    """
    if not isinstance(node, dict):
        return

    if _is_billed_span(node.get("name")) and _has_real_usage(node.get("usageMetadata")):
        usage = node["usageMetadata"]
        attributes = node.get("attributes", {}) or {}
        calls.append({
            "llm_id": attributes.get("llmId"),
            "prompt_tokens": usage.get("promptTokens", 0),
            "completion_tokens": usage.get("completionTokens", 0),
            "total_tokens": usage.get("totalTokens", 0),
            "estimated_cost_usd": usage.get("estimatedCost", 0.0),
            "from_cache": (attributes.get("completionResponse", {}) or {}).get("fromCache", False),
        })

    for child in node.get("children", []) or []:
        _collect_llm_call_usage(child, calls)


def get_llm_call_cost(
    project_key: str,
    llm_id: str,
    message: str,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Run a single prompt against an LLM Mesh connection and report its token
    usage and estimated USD cost.

    Cost data comes straight from the LLM Mesh's own trace, at the point
    where the call is actually billed -- this is the same number Cost
    Control / LLM Cost Guard quotas are metered against, not a separate
    estimate.

    Important scope note: this reports the cost of the ONE prompt passed in
    here. It has no visibility into any other agent's conversation, and it
    cannot report "the cost of the response you're generating right now",
    because that number does not exist yet while a model is still producing
    output -- there is no way for an in-flight turn to know its own final
    cost before it finishes. Use this tool for cost lookups, estimates, and
    auditing of a specific prompt/model pair, not as a live meter bolted
    onto another agent's own answer.

    Args:
        project_key: The project key
        llm_id: LLM Mesh identifier to query, e.g.
            "bedrock:aws-bedrock:anthropic.claude-sonnet-4-6" (see
            get_connections or the project's LLM connections for valid ids)
        message: The prompt text to send
        max_tokens: Optional cap on generated tokens (maxOutputTokens)

    Returns:
        Dict containing the response text and usage/cost totals
    """
    try:
        project = get_project(project_key)

        try:
            llm = project.get_llm(llm_id)
        except Exception as e:
            return {
                "status": "error",
                "message": f"Could not resolve LLM id '{llm_id}': {e}",
            }

        completion = llm.new_completion().with_message(message)
        if max_tokens is not None:
            completion.settings["maxOutputTokens"] = max_tokens

        response = completion.execute()

        calls: List[Dict[str, Any]] = []
        trace = getattr(response, "trace", None)
        if trace:
            _collect_llm_call_usage(trace, calls)

        total_prompt_tokens = sum(c["prompt_tokens"] for c in calls)
        total_completion_tokens = sum(c["completion_tokens"] for c in calls)
        total_tokens = sum(c["total_tokens"] for c in calls)
        total_estimated_cost = sum(c["estimated_cost_usd"] for c in calls)

        return {
            "status": "ok" if response.success else "error",
            "llm_id": llm_id,
            "text": response.text,
            "usage": {
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_tokens,
                "estimated_cost_usd": total_estimated_cost,
            },
            "llm_calls": calls,
            "call_count": len(calls),
            "note": (
                None if calls else
                "No usage metadata found in the trace -- this LLM connection type "
                "may not support cost tracking (e.g. SageMaker, Databricks Mosaic AI, "
                "Snowflake Cortex, or local Hugging Face models are excluded)."
            ),
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get LLM call cost: {e}",
        }
