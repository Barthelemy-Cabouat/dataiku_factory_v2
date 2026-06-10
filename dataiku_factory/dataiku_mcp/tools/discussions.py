"""
Discussion tools for Dataiku DSS objects.

Wraps `DSSObjectDiscussions` so the MCP can list/read/create/reply to
discussion threads attached to any commentable object (recipes, datasets,
notebooks, scenarios, ...).

`object_type` values are the DSS internal type names. The most useful ones:
    RECIPE, DATASET, MANAGED_FOLDER, NOTEBOOK, SQL_NOTEBOOK, SCENARIO,
    PROJECT, SAVED_MODEL, MODEL_EVALUATION_STORE, STREAMING_ENDPOINT, WIKI.

`object_id` is the object's identifier: for recipes/datasets/etc. this is its
name (e.g. "compute_27Q_Enrollment_Flatten_Clean"); for the project itself,
pass the project key.
"""

from typing import Any, Dict, Optional

from dataiku_mcp.client import get_client


def _get_handle(project_key: str, object_type: str, object_id: str):
    client = get_client()
    from dataikuapi.dss.discussion import DSSObjectDiscussions
    return DSSObjectDiscussions(client, project_key, object_type, object_id)


def _format_reply(r) -> Dict[str, Any]:
    data = r.get_raw_data()
    return {
        "author": data.get("author"),
        "text": data.get("text"),
        "time": data.get("time"),
        "edited_on": data.get("editedOn"),
    }


def list_discussions(project_key: str, object_type: str, object_id: str) -> Dict[str, Any]:
    try:
        handle = _get_handle(project_key, object_type, object_id)
        out = []
        for d in handle.list_discussions():
            md = d.get_metadata()
            out.append({
                "id": d.discussion_id,
                "topic": md.get("topic"),
                "status": md.get("status"),
                "created_on": md.get("createdOn"),
                "last_reply_on": md.get("lastReplyOn"),
                "reply_count": md.get("replyCount"),
            })
        return {"status": "ok", "project_key": project_key, "object_type": object_type,
                "object_id": object_id, "discussions": out, "total_count": len(out)}
    except Exception as e:
        return {"status": "error", "message": f"Failed to list discussions: {e}"}


def get_discussion(project_key: str, object_type: str, object_id: str,
                   discussion_id: str) -> Dict[str, Any]:
    try:
        handle = _get_handle(project_key, object_type, object_id)
        d = handle.get_discussion(discussion_id)
        md = d.get_metadata()
        replies = [_format_reply(r) for r in d.get_replies()]
        return {"status": "ok", "id": d.discussion_id, "topic": md.get("topic"),
                "status_": md.get("status"), "created_on": md.get("createdOn"),
                "replies": replies, "reply_count": len(replies)}
    except Exception as e:
        return {"status": "error", "message": f"Failed to get discussion: {e}"}


def create_discussion(project_key: str, object_type: str, object_id: str,
                      topic: str, message: str) -> Dict[str, Any]:
    try:
        handle = _get_handle(project_key, object_type, object_id)
        d = handle.create_discussion(topic, message)
        return {"status": "ok", "discussion_id": d.discussion_id, "topic": topic,
                "message": f"Discussion '{topic}' created on {object_type}/{object_id}"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to create discussion: {e}"}


def reply_to_discussion(project_key: str, object_type: str, object_id: str,
                        discussion_id: str, message: str) -> Dict[str, Any]:
    try:
        handle = _get_handle(project_key, object_type, object_id)
        d = handle.get_discussion(discussion_id)
        d.add_reply(message)
        return {"status": "ok", "discussion_id": discussion_id,
                "message": "Reply added"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to add reply: {e}"}
