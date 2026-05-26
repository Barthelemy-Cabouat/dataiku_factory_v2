"""
Debugging and monitoring tools for Dataiku MCP integration.
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataiku_mcp.client import get_client, get_project
from dataiku_mcp.tools.api_helpers import item_get, scenario_list_item_id

def get_recent_runs(
    project_key: str,
    limit: int = 50,
    status_filter: Optional[str] = None
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
        client = get_client()
        
        all_runs = []
        
        # Get scenario runs
        # list_scenarios() returns DSSScenarioListItem objects (not dicts) by default
        scenarios = project.list_scenarios()
        for scenario in scenarios:
            try:
                scenario_id = scenario_list_item_id(scenario)
                scenario_name = item_get(scenario, "name", scenario_id)
                scenario_obj = project.get_scenario(scenario_id)
                runs = scenario_obj.get_last_runs(limit=limit)

                for run in runs:
                    # DSSScenarioRun: .id (property), .outcome (property), .start_time (datetime),
                    # .end_time (datetime), .duration (float). end_time may raise if not finished.
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
                        "duration": getattr(run, 'duration', None),
                        "trigger_type": (run.trigger.get('type') if isinstance(getattr(run, 'trigger', None), dict) else 'unknown')
                    }

                    # Filter by status if specified
                    if status_filter is None or outcome == status_filter:
                        all_runs.append(run_info)

            except Exception:
                continue
        
        # Get job runs (from recipes and other activities)
        # list_jobs() returns dicts; no 'limit' parameter exists on this API method
        try:
            jobs_list = project.list_jobs()
            for job_dict in jobs_list[:limit]:
                job_def = job_dict.get("def", {})
                job_state = job_dict.get("state", "UNKNOWN")
                job_id = job_def.get("id", "")
                start_ms = job_dict.get("startTime")
                end_ms = job_dict.get("endTime")
                start_str = datetime.fromtimestamp(start_ms / 1000).isoformat() if start_ms else None
                end_str = datetime.fromtimestamp(end_ms / 1000).isoformat() if end_ms else None
                duration = ((end_ms - start_ms) / 1000) if start_ms and end_ms else None

                job_info = {
                    "type": "job",
                    "object_id": job_id,
                    "object_name": job_id,
                    "run_id": job_id,
                    "outcome": job_state,
                    "start_time": start_str,
                    "end_time": end_str,
                    "duration": duration,
                    "trigger_type": "manual"
                }

                # Filter by status if specified
                if status_filter is None or job_state == status_filter:
                    all_runs.append(job_info)

        except Exception as e:
            # Surface the error so callers know job listing is unavailable
            all_runs.append({
                "type": "error",
                "message": f"Could not list jobs: {str(e)}"
            })
        
        # Sort by start time (most recent first)
        all_runs.sort(key=lambda x: x["start_time"] or "", reverse=True)
        
        # Limit results
        if len(all_runs) > limit:
            all_runs = all_runs[:limit]
        
        # Calculate summary statistics
        total_runs = len(all_runs)
        success_runs = len([r for r in all_runs if r["outcome"] in ["SUCCESS", "DONE"]])
        failed_runs = len([r for r in all_runs if r["outcome"] in ["FAILED", "ABORTED"]])
        running_runs = len([r for r in all_runs if r["outcome"] in ["RUNNING", "PENDING"]])
        
        # Calculate average duration for completed runs
        completed_runs = [r for r in all_runs if r["duration"] and r["outcome"] in ["SUCCESS", "DONE", "FAILED"]]
        avg_duration = sum(r["duration"] for r in completed_runs) / len(completed_runs) if completed_runs else 0
        
        # Group by outcome
        outcome_summary = {}
        for run in all_runs:
            outcome = run["outcome"]
            if outcome not in outcome_summary:
                outcome_summary[outcome] = 0
            outcome_summary[outcome] += 1
        
        # Group by type
        type_summary = {}
        for run in all_runs:
            run_type = run["type"]
            if run_type not in type_summary:
                type_summary[run_type] = 0
            type_summary[run_type] += 1
        
        # Recent failures analysis
        recent_failures = [r for r in all_runs if r["outcome"] in ["FAILED", "ABORTED"]][:10]
        
        summary = {
            "total_runs": total_runs,
            "success_runs": success_runs,
            "failed_runs": failed_runs,
            "running_runs": running_runs,
            "success_rate": (success_runs / total_runs * 100) if total_runs > 0 else 0,
            "average_duration": avg_duration,
            "outcome_summary": outcome_summary,
            "type_summary": type_summary,
            "recent_failures_count": len(recent_failures)
        }
        
        return {
            "status": "ok",
            "project_key": project_key,
            "runs": all_runs,
            "recent_failures": recent_failures,
            "summary": summary,
            "filters_applied": {
                "limit": limit,
                "status_filter": status_filter
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get recent runs: {str(e)}"
        }


def get_job_details(
    project_key: str,
    job_id: str
) -> Dict[str, Any]:
    """
    Get detailed job execution information.
    
    Args:
        project_key: The project key
        job_id: Job identifier
        
    Returns:
        Dict containing detailed job information
    """
    try:
        client = get_client()
        project = get_project(project_key)
        
        # DSSJob is obtained via project.get_job(id), not client.get_job
        job = project.get_job(job_id)

        # The DSSJob class only exposes: abort(), get_status() -> dict, get_log() -> str.
        # All job state/timing info lives in get_status() result.
        try:
            job_status_raw = job.get_status() or {}
        except Exception as e:
            job_status_raw = {"_error": f"Could not get status: {str(e)}"}

        base_status = job_status_raw.get("baseStatus", {}) if isinstance(job_status_raw, dict) else {}
        job_def = base_status.get("def", {}) if isinstance(base_status, dict) else {}
        start_ms = base_status.get("startTime")
        end_ms = base_status.get("endTime")
        start_str = datetime.fromtimestamp(start_ms / 1000).isoformat() if start_ms else None
        end_str = datetime.fromtimestamp(end_ms / 1000).isoformat() if end_ms else None
        duration = ((end_ms - start_ms) / 1000) if start_ms and end_ms else None

        job_info = {
            "job_id": job_id,
            "job_name": job_def.get("name", f"Job {job_id}"),
            "state": base_status.get("state", "UNKNOWN"),
            "start_time": start_str,
            "end_time": end_str,
            "duration": duration,
            "initiator": base_status.get("initiator", "unknown"),
            "type": job_def.get("type", "unknown"),
            "definition": {
                "type": job_def.get("type", "unknown"),
                "projectKey": job_def.get("projectKey", project_key),
                "outputs": job_def.get("outputs", []),
            },
            "status": {
                "state": base_status.get("state", "unknown"),
                "progress": base_status.get("progress", 0),
                "warning": base_status.get("hasWarning", False),
                "messages": base_status.get("messages", []),
            },
        }

        # Get job log (last 100 lines to avoid excessive response size)
        logs = []
        try:
            log_content = job.get_log()
            if log_content:
                tail_lines = log_content.splitlines()[-100:]
                logs.append({
                    "type": "main_log",
                    "content": "\n".join(tail_lines),
                    "truncated": True,
                    "timestamp": start_str,
                })
        except Exception as e:
            logs.append({
                "type": "error",
                "content": f"Could not retrieve job log: {str(e)}",
                "timestamp": start_str,
            })

        # Activities are surfaced via the status payload; expose them when present
        activities = []
        if isinstance(job_status_raw, dict):
            activities = job_status_raw.get("activities", []) or []
        activity_info = {
            "activity_count": len(activities),
            "activities": [
                {
                    "type": a.get("type", "unknown"),
                    "name": a.get("name", "unknown"),
                    "state": a.get("baseStatus", {}).get("state", a.get("state", "unknown")),
                    "start_time": a.get("baseStatus", {}).get("startTime") or a.get("startTime"),
                    "end_time": a.get("baseStatus", {}).get("endTime") or a.get("endTime"),
                }
                for a in activities[:10]
            ],
        }

        timeline = []
        if start_str:
            timeline.append({"event": "job_started", "timestamp": start_str, "description": "Job execution started"})
        if end_str:
            timeline.append({"event": "job_completed", "timestamp": end_str, "description": f"Job completed with status: {job_info['state']}"})

        return {
            "status": "ok",
            "project_key": project_key,
            "job_info": job_info,
            "logs": logs,
            "activity_info": activity_info,
            "timeline": timeline,
            "log_count": len(logs),
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get job details: {str(e)}"
        }


def cancel_running_jobs(
    project_key: str,
    job_ids: List[str]
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
        client = get_client()
        project = get_project(project_key)
        
        cancelled_jobs = []
        failed_cancellations = []

        def _job_state(j):
            try:
                s = j.get_status() or {}
                return (s.get("baseStatus", {}) or {}).get("state", "UNKNOWN")
            except Exception:
                return "UNKNOWN"

        for job_id in job_ids:
            try:
                # DSSJob is obtained via project.get_job(id)
                job = project.get_job(job_id)

                job_state = _job_state(job)
                if job_state not in ["RUNNING", "PENDING"]:
                    failed_cancellations.append({
                        "job_id": job_id,
                        "error": f"Job is not running (state: {job_state})",
                        "current_state": job_state,
                    })
                    continue

                # abort() returns a confirmation dict
                job.abort()

                # Verify cancellation
                try:
                    import time
                    time.sleep(1)
                    new_state = _job_state(project.get_job(job_id))
                    cancelled_jobs.append({
                        "job_id": job_id,
                        "previous_state": job_state,
                        "new_state": new_state,
                        "cancelled_successfully": new_state in ["ABORTED", "CANCELLED", "DONE", "FAILED"],
                    })
                except Exception as e:
                    cancelled_jobs.append({
                        "job_id": job_id,
                        "previous_state": job_state,
                        "new_state": "unknown",
                        "cancelled_successfully": True,
                        "verification_error": str(e),
                    })

            except Exception as e:
                failed_cancellations.append({
                    "job_id": job_id,
                    "error": f"Failed to cancel job: {str(e)}",
                })

        # Get summary of results
        successful_cancellations = len([j for j in cancelled_jobs if j.get("cancelled_successfully", False)])
        failed_count = len(failed_cancellations)

        # Try to get current running jobs for context.
        # project.list_jobs() returns dicts (not objects) and accepts no kwargs.
        current_running_jobs = []
        try:
            jobs = project.list_jobs()
            for j in jobs:
                state = j.get("state", "")
                if state in ["RUNNING", "PENDING"]:
                    job_def = j.get("def", {})
                    current_running_jobs.append({
                        "job_id": job_def.get("id"),
                        "job_name": job_def.get("name", job_def.get("id")),
                        "state": state,
                        "start_time": j.get("startTime"),
                    })
        except Exception:
            pass
        
        cancellation_summary = {
            "total_requested": len(job_ids),
            "successful_cancellations": successful_cancellations,
            "failed_cancellations": failed_count,
            "success_rate": (successful_cancellations / len(job_ids) * 100) if job_ids else 0,
            "remaining_running_jobs": len(current_running_jobs)
        }
        
        return {
            "status": "ok",
            "project_key": project_key,
            "cancelled_jobs": cancelled_jobs,
            "failed_cancellations": failed_cancellations,
            "cancellation_summary": cancellation_summary,
            "current_running_jobs": current_running_jobs
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to cancel running jobs: {str(e)}"
        }
