"""
Debugging and monitoring tools for Dataiku MCP integration.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from dataiku_mcp.client import get_client, get_project, rest_get_json, rest_get_text


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ms_to_iso(ms: Optional[int]) -> Optional[str]:
    return datetime.fromtimestamp(ms / 1000).isoformat() if ms else None


def _duration_s(start_ms: Optional[int], end_ms: Optional[int]) -> Optional[float]:
    if start_ms and end_ms:
        return round((end_ms - start_ms) / 1000, 1)
    return None


def _parse_activities(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse the activities dict returned by GET /projects/{key}/jobs/{id}/
    into a sorted list with normalised fields.
    """
    rows = []
    for act_id, act in raw.items():
        start_ms = act.get("startTime")
        end_ms = act.get("endTime")
        msgs = act.get("messages", {}).get("messages", [])
        rows.append({
            "activity_id": act_id,
            "recipe_name": act.get("recipeName", act_id),
            "recipe_type": act.get("recipeType") or act.get("activityType", "unknown"),
            "state": act.get("state", "UNKNOWN"),
            "execution_order": act.get("partialExecutionOrder", 999),
            "start_time": _ms_to_iso(start_ms),
            "end_time": _ms_to_iso(end_ms),
            "duration": _duration_s(start_ms, end_ms),
            "warnings": act.get("warnings", {}).get("totalCount", 0),
            "error_messages": [
                {"severity": m.get("severity"), "title": m.get("title"), "message": m.get("message")}
                for m in msgs
                if m.get("severity") in ("ERROR", "FATAL")
            ],
        })
    rows.sort(key=lambda x: (x["execution_order"], x["start_time"] or ""))
    return rows


def _filter_log_lines(
    lines: List[str],
    grep_pattern: Optional[str],
    severity: Optional[str],
    activity_id: Optional[str],
) -> List[str]:
    """Apply grep / severity / activity filters to a list of log lines."""
    severity_tag = f"[{severity.upper()}]" if severity else None
    act_patterns = [activity_id, f"act.{activity_id}"] if activity_id else None

    result = []
    for line in lines:
        if severity_tag and severity_tag not in line:
            continue
        if act_patterns and not any(p in line for p in act_patterns):
            continue
        if grep_pattern and grep_pattern.lower() not in line.lower():
            continue
        result.append(line)
    return result


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------

def get_recent_runs(
    project_key: str,
    limit: int = 50,
    status_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get recent run history across all scenarios/recipes.

    Args:
        project_key: The project key
        limit: Number of recent runs to retrieve
        status_filter: Filter by status (SUCCESS, FAILED, etc.)

    Returns:
        Dict containing recent runs and summary
    """
    try:
        project = get_project(project_key)

        all_runs = []

        # Scenario runs
        scenarios = project.list_scenarios()
        for scenario in scenarios:
            try:
                scenario_id = scenario.id if hasattr(scenario, "id") else scenario["id"]
                scenario_name = getattr(scenario, "name", None)
                if scenario_name is None and isinstance(scenario, dict):
                    scenario_name = scenario.get("name", scenario_id)
                scenario_obj = project.get_scenario(scenario_id)
                runs = scenario_obj.get_last_runs(limit=limit)

                for run in runs:
                    try:
                        end_time = run.end_time
                        end_str = end_time.isoformat() if end_time else None
                    except Exception:
                        end_str = None
                    try:
                        start_time = run.start_time
                        start_str = start_time.isoformat() if start_time else None
                    except Exception:
                        start_str = None
                    try:
                        outcome = run.outcome
                    except Exception:
                        outcome = None
                    run_info = {
                        "type": "scenario",
                        "object_id": scenario_id,
                        "object_name": scenario_name or scenario_id,
                        "run_id": run.id,
                        "outcome": outcome,
                        "start_time": start_str,
                        "end_time": end_str,
                        "duration": getattr(run, "duration", None),
                        "trigger_type": (
                            run.trigger.get("type")
                            if isinstance(getattr(run, "trigger", None), dict)
                            else "unknown"
                        ),
                    }
                    if status_filter is None or outcome == status_filter:
                        all_runs.append(run_info)
            except Exception:
                continue

        # Job runs via REST (list_jobs() returns dicts with no limit param)
        try:
            jobs_list = rest_get_json(f"/projects/{project_key}/jobs/")
            for job_dict in jobs_list[:limit]:
                job_def = job_dict.get("def", {})
                job_state = job_dict.get("state", "UNKNOWN")
                job_id = job_def.get("id", "")
                start_ms = job_dict.get("startTime")
                end_ms = job_dict.get("endTime")
                job_info = {
                    "type": "job",
                    "object_id": job_id,
                    "object_name": job_id,
                    "run_id": job_id,
                    "outcome": job_state,
                    "start_time": _ms_to_iso(start_ms),
                    "end_time": _ms_to_iso(end_ms),
                    "duration": _duration_s(start_ms, end_ms),
                    "trigger_type": "manual",
                }
                if status_filter is None or job_state == status_filter:
                    all_runs.append(job_info)
        except Exception as e:
            all_runs.append({"type": "error", "message": f"Could not list jobs: {e}"})

        all_runs.sort(key=lambda x: x["start_time"] or "", reverse=True)
        if len(all_runs) > limit:
            all_runs = all_runs[:limit]

        total = len(all_runs)
        success = len([r for r in all_runs if r["outcome"] in ("SUCCESS", "DONE")])
        failed = len([r for r in all_runs if r["outcome"] in ("FAILED", "ABORTED")])
        running = len([r for r in all_runs if r["outcome"] in ("RUNNING", "PENDING")])
        completed = [r for r in all_runs if r["duration"] and r["outcome"] in ("SUCCESS", "DONE", "FAILED")]
        avg_dur = sum(r["duration"] for r in completed) / len(completed) if completed else 0

        outcome_summary: Dict[str, int] = {}
        type_summary: Dict[str, int] = {}
        for run in all_runs:
            outcome_summary[run["outcome"]] = outcome_summary.get(run["outcome"], 0) + 1
            type_summary[run["type"]] = type_summary.get(run["type"], 0) + 1

        return {
            "status": "ok",
            "project_key": project_key,
            "runs": all_runs,
            "recent_failures": [r for r in all_runs if r["outcome"] in ("FAILED", "ABORTED")][:10],
            "summary": {
                "total_runs": total,
                "success_runs": success,
                "failed_runs": failed,
                "running_runs": running,
                "success_rate": (success / total * 100) if total > 0 else 0,
                "average_duration": avg_dur,
                "outcome_summary": outcome_summary,
                "type_summary": type_summary,
            },
            "filters_applied": {"limit": limit, "status_filter": status_filter},
        }

    except Exception as e:
        return {"status": "error", "message": f"Failed to get recent runs: {e}"}


def get_job_details(
    project_key: str,
    job_id: str,
    log_lines: int = 100,
    log_from_end: bool = True,
) -> Dict[str, Any]:
    """
    Get detailed job execution information including per-activity breakdown.

    Uses the DSS REST API directly to obtain the rich job object that includes
    the activities dict, global state, error message, and timing — the
    dataikuapi DSSJob.get_status() endpoint is not available on all DSS versions.

    Args:
        project_key: The project key
        job_id: Job identifier
        log_lines: Number of log lines to include (0 to skip log)
        log_from_end: If True (default) return the last N lines; False for first N

    Returns:
        Dict containing job summary, per-activity breakdown, and log excerpt
    """
    try:
        # Rich job object from the public API
        job_data = rest_get_json(f"/projects/{project_key}/jobs/{job_id}/")
    except Exception as e:
        return {"status": "error", "message": f"Failed to fetch job: {e}"}

    try:
        base = job_data.get("baseStatus", {})
        job_def = base.get("def", {})
        start_ms = base.get("startTime")
        end_ms = base.get("endTime")
        global_state = job_data.get("globalState", {})
        # globalState is a dict like {done:8, failed:1, total:9, ...}
        overall_state = (
            "FAILED" if global_state.get("failed", 0) > 0
            else "DONE" if global_state.get("total", 0) > 0
            else base.get("state", "UNKNOWN")
        )

        activities = _parse_activities(base.get("activities", {}))

        job_info = {
            "job_id": job_id,
            "job_name": job_def.get("name", job_id),
            "type": job_def.get("type", "unknown"),
            "state": overall_state,
            "global_state_counts": global_state,
            "error_message": job_data.get("errorMessage"),
            "initiator": job_data.get("initiator", {}).get("login", "unknown"),
            "start_time": _ms_to_iso(start_ms),
            "end_time": _ms_to_iso(end_ms),
            "duration": _duration_s(start_ms, end_ms),
        }

        # Identify the failing activity for quick diagnosis
        failed_activities = [a for a in activities if a["state"] == "FAILED"]

        log_excerpt: Optional[Dict[str, Any]] = None
        if log_lines > 0:
            try:
                raw_log = rest_get_text(f"/projects/{project_key}/jobs/{job_id}/log")
                all_lines = raw_log.splitlines()
                chosen = all_lines[-log_lines:] if log_from_end else all_lines[:log_lines]
                log_excerpt = {
                    "total_lines": len(all_lines),
                    "lines_returned": len(chosen),
                    "from_end": log_from_end,
                    "content": "\n".join(chosen),
                    "tip": (
                        "Use get_job_log() for filtering by activity, severity, or grep pattern, "
                        "or to retrieve a different window of lines."
                    ),
                }
            except Exception as e:
                log_excerpt = {"error": f"Could not retrieve log: {e}"}

        return {
            "status": "ok",
            "project_key": project_key,
            "job_info": job_info,
            "activities": activities,
            "failed_activities": failed_activities,
            "log_excerpt": log_excerpt,
        }

    except Exception as e:
        return {"status": "error", "message": f"Failed to parse job details: {e}"}


def get_job_log(
    project_key: str,
    job_id: str,
    lines: int = 200,
    from_end: bool = True,
    grep_pattern: Optional[str] = None,
    severity: Optional[str] = None,
    activity_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieve and filter the log for a specific job.

    Fetches the full job log and applies optional filters before returning
    the requested window of lines. Useful for large jobs where the default
    log excerpt in get_job_details is insufficient.

    Args:
        project_key: The project key
        job_id: Job identifier
        lines: Maximum number of lines to return after filtering (default 200)
        from_end: If True (default), take the last N matching lines;
                  if False, take the first N matching lines
        grep_pattern: Case-insensitive substring filter — only lines containing
                      this string are kept (e.g. "ERROR", "gspread", "FAILED")
        severity: Keep only lines at this log level: ERROR, WARNING, INFO, or DEBUG
                  (matches the bracketed token, e.g. "[ERROR]")
        activity_id: Keep only lines related to this activity / recipe
                     (matches both "running <id>" and "act.<id>" patterns)

    Returns:
        Dict with filtered log lines and metadata
    """
    try:
        raw_log = rest_get_text(f"/projects/{project_key}/jobs/{job_id}/log")
    except Exception as e:
        return {"status": "error", "message": f"Failed to fetch log: {e}"}

    all_lines = raw_log.splitlines()
    total_lines = len(all_lines)

    filtered = _filter_log_lines(all_lines, grep_pattern, severity, activity_id)
    total_after_filter = len(filtered)

    chosen = filtered[-lines:] if from_end else filtered[:lines]

    return {
        "status": "ok",
        "project_key": project_key,
        "job_id": job_id,
        "total_log_lines": total_lines,
        "lines_after_filter": total_after_filter,
        "lines_returned": len(chosen),
        "filters_applied": {
            "lines": lines,
            "from_end": from_end,
            "grep_pattern": grep_pattern,
            "severity": severity,
            "activity_id": activity_id,
        },
        "content": "\n".join(chosen),
    }


def get_job_activities(
    project_key: str,
    job_id: str,
) -> Dict[str, Any]:
    """
    Get the per-activity execution breakdown for a job.

    Lighter-weight alternative to get_job_details when you only need the
    activity list (no log fetching).

    Args:
        project_key: The project key
        job_id: Job identifier

    Returns:
        Dict with job state, error message, and ordered activity list
    """
    try:
        job_data = rest_get_json(f"/projects/{project_key}/jobs/{job_id}/")
    except Exception as e:
        return {"status": "error", "message": f"Failed to fetch job: {e}"}

    base = job_data.get("baseStatus", {})
    global_state = job_data.get("globalState", {})
    overall_state = (
        "FAILED" if global_state.get("failed", 0) > 0
        else "DONE" if global_state.get("total", 0) > 0
        else "UNKNOWN"
    )
    activities = _parse_activities(base.get("activities", {}))

    return {
        "status": "ok",
        "project_key": project_key,
        "job_id": job_id,
        "state": overall_state,
        "global_state_counts": global_state,
        "error_message": job_data.get("errorMessage"),
        "initiator": job_data.get("initiator", {}).get("login", "unknown"),
        "activities": activities,
        "failed_activities": [a for a in activities if a["state"] == "FAILED"],
    }


def cancel_running_jobs(
    project_key: str,
    job_ids: List[str],
) -> Dict[str, Any]:
    """
    Cancel running jobs/scenarios.

    Args:
        project_key: The project key
        job_ids: List of job IDs to cancel

    Returns:
        Dict containing cancellation results
    """
    try:
        project = get_project(project_key)

        cancelled_jobs = []
        failed_cancellations = []

        def _job_state(j):
            try:
                s = j.get_status() or {}
                return (s.get("baseStatus", {}) or {}).get("state", "UNKNOWN")
            except Exception:
                # Fallback to REST API
                try:
                    data = rest_get_json(f"/projects/{project_key}/jobs/{j.id}/")
                    gs = data.get("globalState", {})
                    if gs.get("running", 0) > 0:
                        return "RUNNING"
                    if gs.get("failed", 0) > 0:
                        return "FAILED"
                    if gs.get("done", 0) == gs.get("total", -1):
                        return "DONE"
                except Exception:
                    pass
                return "UNKNOWN"

        for job_id in job_ids:
            try:
                job = project.get_job(job_id)
                job_state = _job_state(job)
                if job_state not in ("RUNNING", "PENDING"):
                    failed_cancellations.append({
                        "job_id": job_id,
                        "error": f"Job is not running (state: {job_state})",
                        "current_state": job_state,
                    })
                    continue

                job.abort()

                import time
                time.sleep(1)
                new_job = project.get_job(job_id)
                new_state = _job_state(new_job)
                cancelled_jobs.append({
                    "job_id": job_id,
                    "previous_state": job_state,
                    "new_state": new_state,
                    "cancelled_successfully": new_state in ("ABORTED", "CANCELLED", "DONE", "FAILED"),
                })

            except Exception as e:
                failed_cancellations.append({"job_id": job_id, "error": f"Failed to cancel: {e}"})

        # Current running jobs for context
        current_running = []
        try:
            for j in rest_get_json(f"/projects/{project_key}/jobs/"):
                if j.get("state") in ("RUNNING", "PENDING"):
                    jd = j.get("def", {})
                    current_running.append({
                        "job_id": jd.get("id"),
                        "state": j.get("state"),
                        "start_time": _ms_to_iso(j.get("startTime")),
                    })
        except Exception:
            pass

        successful = len([j for j in cancelled_jobs if j.get("cancelled_successfully")])
        return {
            "status": "ok",
            "project_key": project_key,
            "cancelled_jobs": cancelled_jobs,
            "failed_cancellations": failed_cancellations,
            "cancellation_summary": {
                "total_requested": len(job_ids),
                "successful_cancellations": successful,
                "failed_cancellations": len(failed_cancellations),
                "success_rate": (successful / len(job_ids) * 100) if job_ids else 0,
                "remaining_running_jobs": len(current_running),
            },
            "current_running_jobs": current_running,
        }

    except Exception as e:
        return {"status": "error", "message": f"Failed to cancel running jobs: {e}"}
