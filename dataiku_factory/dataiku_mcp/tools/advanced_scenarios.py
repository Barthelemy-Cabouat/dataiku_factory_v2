"""
Advanced scenario management tools for Dataiku MCP integration.
"""

import json
import copy
from typing import Dict, Any, List, Optional
from dataiku_mcp.client import get_client, get_project

def get_scenario_logs(
    project_key: str,
    scenario_id: str,
    run_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get detailed run logs and error messages for scenarios.
    
    Args:
        project_key: The project key
        scenario_id: ID of the scenario
        run_id: Specific run ID (defaults to latest)
        
    Returns:
        Dict containing logs and run information
    """
    try:
        project = get_project(project_key)
        scenario = project.get_scenario(scenario_id)
        
        # Get run history
        runs = scenario.get_last_runs(limit=50)
        
        if not runs:
            return {
                "status": "ok",
                "message": "No runs found for this scenario",
                "logs": [],
                "run_info": {}
            }
        
        # Find the target run
        target_run = None
        if run_id:
            target_run = next((run for run in runs if run.run_id == run_id), None)
            if not target_run:
                return {
                    "status": "error",
                    "message": f"Run ID '{run_id}' not found"
                }
        else:
            # Use the latest run
            target_run = runs[0]
        
        # Extract run information
        run_info = {
            "run_id": target_run.run_id,
            "start_time": target_run.start_time,
            "end_time": target_run.end_time,
            "outcome": target_run.outcome,
            "duration": target_run.duration,
            "trigger": target_run.trigger_type if hasattr(target_run, 'trigger_type') else "unknown"
        }
        
        # Get logs from the run
        logs = []
        
        try:
            # Get main scenario log
            main_log = target_run.get_log()
            if main_log:
                logs.append({
                    "type": "scenario_log",
                    "content": main_log,
                    "timestamp": target_run.start_time
                })
        except Exception as e:
            logs.append({
                "type": "error",
                "content": f"Could not retrieve scenario log: {str(e)}",
                "timestamp": target_run.start_time
            })
        
        # Get step logs if available
        try:
            step_runs = target_run.get_step_runs()
            for i, step_run in enumerate(step_runs):
                try:
                    step_log = step_run.get_log()
                    if step_log:
                        logs.append({
                            "type": "step_log",
                            "step_index": i,
                            "step_name": step_run.step_name if hasattr(step_run, 'step_name') else f"Step {i}",
                            "content": step_log,
                            "timestamp": step_run.start_time if hasattr(step_run, 'start_time') else target_run.start_time
                        })
                except Exception as e:
                    logs.append({
                        "type": "step_error",
                        "step_index": i,
                        "content": f"Could not retrieve step log: {str(e)}",
                        "timestamp": target_run.start_time
                    })
        except Exception as e:
            logs.append({
                "type": "error",
                "content": f"Could not retrieve step runs: {str(e)}",
                "timestamp": target_run.start_time
            })
        
        # Get job logs if available
        try:
            jobs = target_run.get_jobs()
            for job in jobs:
                try:
                    job_log = job.get_log()
                    if job_log:
                        logs.append({
                            "type": "job_log",
                            "job_id": job.job_id,
                            "job_name": job.job_name if hasattr(job, 'job_name') else f"Job {job.job_id}",
                            "content": job_log,
                            "timestamp": job.start_time if hasattr(job, 'start_time') else target_run.start_time
                        })
                except Exception as e:
                    logs.append({
                        "type": "job_error",
                        "job_id": job.job_id,
                        "content": f"Could not retrieve job log: {str(e)}",
                        "timestamp": target_run.start_time
                    })
        except Exception as e:
            logs.append({
                "type": "error",
                "content": f"Could not retrieve jobs: {str(e)}",
                "timestamp": target_run.start_time
            })
        
        return {
            "status": "ok",
            "scenario_id": scenario_id,
            "run_info": run_info,
            "logs": logs,
            "log_count": len(logs)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get scenario logs: {str(e)}"
        }


def get_scenario_steps(
    project_key: str,
    scenario_id: str
) -> Dict[str, Any]:
    """
    Get detailed step configuration including Python code.
    
    Args:
        project_key: The project key
        scenario_id: ID of the scenario
        
    Returns:
        Dict containing step configurations
    """
    try:
        project = get_project(project_key)
        scenario = project.get_scenario(scenario_id)
        settings = scenario.get_settings()
        
        # Get raw steps from settings
        raw_steps = settings.raw_steps
        
        # Process each step
        steps = []
        for i, step in enumerate(raw_steps):
            step_info = {
                "index": i,
                "name": step.get("name", f"Step {i}"),
                "type": step.get("type", "unknown"),
                "enabled": step.get("enabled", True),
                "params": step.get("params", {})
            }
            
            # Extract specific information based on step type
            if step.get("type") == "custom_python":
                # Extract Python code
                script = step.get("params", {}).get("script", "")
                step_info["code"] = script
                step_info["code_lines"] = len(script.split('\n')) if script else 0
                
            elif step.get("type") == "build_flowitem":
                # Extract build step information
                items = step.get("params", {}).get("items", [])
                step_info["build_items"] = items
                step_info["build_count"] = len(items)
                
            elif step.get("type") == "invalidate_cache":
                # Extract cache invalidation info
                items = step.get("params", {}).get("items", [])
                step_info["invalidate_items"] = items
                
            elif step.get("type") == "sync_hive":
                # Extract Hive sync information
                items = step.get("params", {}).get("items", [])
                step_info["sync_items"] = items
                
            elif step.get("type") == "run_scenario":
                # Extract nested scenario run info
                scenario_runs = step.get("params", {}).get("scenarioRuns", [])
                step_info["nested_scenarios"] = scenario_runs
                
            steps.append(step_info)
        
        # Get scenario metadata
        scenario_info = {
            "id": scenario_id,
            "name": settings.name,
            "type": settings.type,
            "active": settings.active,
            "step_count": len(steps)
        }
        
        return {
            "status": "ok",
            "scenario_info": scenario_info,
            "steps": steps,
            "step_count": len(steps)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get scenario steps: {str(e)}"
        }


def clone_scenario(
    project_key: str,
    source_scenario_id: str,
    new_scenario_name: str,
    modifications: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Clone an existing scenario with modifications.
    
    Args:
        project_key: The project key
        source_scenario_id: Source scenario ID to clone
        new_scenario_name: Name for the new scenario
        modifications: Optional modifications to apply
        
    Returns:
        Dict containing cloned scenario information
    """
    try:
        project = get_project(project_key)
        source_scenario = project.get_scenario(source_scenario_id)
        source_settings = source_scenario.get_settings()
        
        # Get source scenario configuration
        source_metadata = source_scenario.get_metadata()
        
        # Create new scenario
        scenario_type = source_settings.type
        new_scenario = project.create_scenario(
            new_scenario_name,
            scenario_type,
            definition=source_settings.get_definition()
        )
        
        # Get new scenario settings to modify
        new_settings = new_scenario.get_settings()
        
        # Copy basic settings
        new_settings.name = new_scenario_name
        new_settings.active = source_settings.active
        
        # Copy steps
        new_settings.raw_steps = copy.deepcopy(source_settings.raw_steps)
        
        # Copy triggers
        new_settings.raw_triggers = copy.deepcopy(source_settings.raw_triggers)
        
        # Apply modifications if provided
        if modifications:
            # Modify metadata
            if "description" in modifications:
                new_metadata = new_scenario.get_metadata()
                new_metadata["description"] = modifications["description"]
                new_scenario.set_metadata(new_metadata)
            
            if "tags" in modifications:
                new_metadata = new_scenario.get_metadata()
                new_metadata["tags"] = modifications["tags"]
                new_scenario.set_metadata(new_metadata)
            
            # Modify settings
            if "active" in modifications:
                new_settings.active = modifications["active"]
            
            # Modify steps
            if "step_modifications" in modifications:
                step_mods = modifications["step_modifications"]
                for step_index, step_changes in step_mods.items():
                    if step_index < len(new_settings.raw_steps):
                        step = new_settings.raw_steps[step_index]
                        
                        # Update step parameters
                        if "params" in step_changes:
                            step["params"].update(step_changes["params"])
                        
                        # Update step code for custom_python steps
                        if "code" in step_changes and step.get("type") == "custom_python":
                            if "params" not in step:
                                step["params"] = {}
                            step["params"]["script"] = step_changes["code"]
                        
                        # Update step name
                        if "name" in step_changes:
                            step["name"] = step_changes["name"]
                        
                        # Update step enabled status
                        if "enabled" in step_changes:
                            step["enabled"] = step_changes["enabled"]
            
            # Modify triggers
            if "trigger_modifications" in modifications:
                trigger_mods = modifications["trigger_modifications"]
                for trigger_index, trigger_changes in trigger_mods.items():
                    if trigger_index < len(new_settings.raw_triggers):
                        trigger = new_settings.raw_triggers[trigger_index]
                        trigger.update(trigger_changes)
            
            # Add new triggers
            if "new_triggers" in modifications:
                new_settings.raw_triggers.extend(modifications["new_triggers"])
            
            # Remove triggers by index
            if "remove_triggers" in modifications:
                for trigger_index in sorted(modifications["remove_triggers"], reverse=True):
                    if trigger_index < len(new_settings.raw_triggers):
                        del new_settings.raw_triggers[trigger_index]
        
        # Save the new scenario
        new_settings.save()
        
        # Get final scenario info
        final_scenario_info = {
            "id": new_scenario.scenario_id,
            "name": new_scenario_name,
            "type": scenario_type,
            "active": new_settings.active,
            "step_count": len(new_settings.raw_steps),
            "trigger_count": len(new_settings.raw_triggers)
        }
        
        return {
            "status": "ok",
            "source_scenario_id": source_scenario_id,
            "new_scenario_id": new_scenario.scenario_id,
            "new_scenario_name": new_scenario_name,
            "scenario_info": final_scenario_info,
            "modifications_applied": list(modifications.keys()) if modifications else []
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to clone scenario: {str(e)}"
        }