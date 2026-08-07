"""
Cost-reporting wrapper agent for the Slack integration.

Paste this into the Code tab of the DSS agent
"Mugisha AI (cost-reporting)" (id: YMqznxXq) in project DATAIKU_MAINTENANCE,
then point the Slack webapp's llm_id at agent:YMqznxXq.

WHY THIS EXISTS
---------------
An agent cannot report the cost of its own reply: the figure does not exist
until the turn finishes. Instructing it to do so via a tool made it re-run the
user's question as a fresh prompt and report *that* cost instead -- understating
the real cost by ~366x, and injecting an ungrounded answer into its context.

This wrapper sidesteps that. It proxies the real agent, so the inner call has
already completed -- and its trace carries genuine usage -- before this code
builds the footer. No extra LLM spend, and no prompt can talk it out of
reporting accurately.
"""

import dataiku
from dataiku.llm.python import BaseLLM

# The agent that does the actual work.
INNER_AGENT_ID = "agent:qZisMtc4"

# Set False to show only cost, omitting token counts and call count.
SHOW_TOKEN_DETAIL = True


def _is_billed_span(name):
    """
    True for spans that carry real billing metadata.

    An agent turn emits DKU_LLM_MESH_LLM_CALL_STREAMED (one per iteration),
    not the bare DKU_LLM_MESH_LLM_CALL, so this prefix-matches. The
    _FIRST_CHUNK / _STREAM_COMPLETE sub-spans sit inside a billed span and
    carry no usage of their own.
    """
    if not isinstance(name, str) or not name.startswith("DKU_LLM_MESH_LLM_CALL"):
        return False
    return not (name.endswith("_FIRST_CHUNK") or name.endswith("_STREAM_COMPLETE"))


def _has_real_usage(usage):
    """
    True only if a usageMetadata dict reports actual consumption.

    The outer DKU_LLM_MESH_LLM_CALL span on an agent turn carries an empty
    usageMetadata ({}) -- it wraps the billed inner calls rather than being one.
    Counting it reported "3 LLM calls" for a turn that made 2.
    """
    if not isinstance(usage, dict):
        return False
    return bool(
        usage.get("totalTokens")
        or usage.get("promptTokens")
        or usage.get("completionTokens")
        or usage.get("estimatedCost")
    )


def _collect_usage(node, out):
    """Walk the trace tree, collecting usage from genuinely billed spans."""
    if not isinstance(node, dict):
        return
    if _is_billed_span(node.get("name")) and _has_real_usage(node.get("usageMetadata")):
        out.append(node["usageMetadata"])
    for child in node.get("children", []) or []:
        _collect_usage(child, out)


def _format_cost_footer(trace):
    """
    Build a Slack-mrkdwn footer from a completed trace.

    Returns '' when no usage is present -- some connection types (SageMaker,
    Databricks Mosaic AI, Snowflake Cortex, local Hugging Face) are excluded
    from Dataiku cost tracking, and a silent omission beats a fake $0.00.
    """
    usages = []
    _collect_usage(trace, usages)
    if not usages:
        return ""

    cost = sum(u.get("estimatedCost", 0.0) or 0.0 for u in usages)
    if not SHOW_TOKEN_DETAIL:
        return "\n\n_${:.4f}_".format(cost)

    tokens = sum(u.get("totalTokens", 0) or 0 for u in usages)
    plural = "s" if len(usages) != 1 else ""
    return "\n\n_${:.4f} · {:,} tokens · {} LLM call{}_".format(
        cost, tokens, len(usages), plural
    )


class CostReportingAgent(BaseLLM):
    """Proxies INNER_AGENT_ID and appends the true cost of the turn."""

    def process(self, query, settings, trace):
        project = dataiku.api_client().get_default_project()
        inner = project.get_llm(INNER_AGENT_ID).new_completion()

        # Forward the conversation verbatim. Extending cq["messages"] preserves
        # multipart messages (inline images from Slack) exactly as received;
        # rebuilding them with with_message() would silently drop attachments.
        inner.cq["messages"].extend(query.get("messages", []))

        # Forward the request context. This carries dkuOnBehalfOf, which drives
        # per-user impersonation and document-level security -- dropping it
        # would run every Slack user's query as the webapp's own identity.
        context = query.get("context")
        if context:
            inner.with_context(context)

        response = inner.execute()

        # Nest the inner trace under this one so Trace Explorer still shows the
        # full picture rather than an opaque single span.
        inner_trace = getattr(response, "trace", None)
        if inner_trace:
            try:
                trace.append_trace(inner_trace)
            except Exception:
                pass  # tracing is best-effort; never fail the reply over it

        text = response.text or ""
        if not response.success:
            # Pass the failure through unchanged; no cost line on a failed turn.
            return {"text": text or "The agent was unable to produce a response."}

        return {"text": text + _format_cost_footer(inner_trace)}
