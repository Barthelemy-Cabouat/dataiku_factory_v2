"""
Scenario management tools for Dataiku DSS.

This module provides functions for creating, updating, deleting, and managing scenarios
in Dataiku DSS projects through the dataiku-api-client.
"""

from typing import Dict, List, Optional, Union, Any
import dataikuapi
import dataikuapi.dss.project
import dataikuapi.dss.scenario
from dataiku_mcp.client import get_client, get_project
from dataiku_mcp.tools.api_helpers import item_get, scenario_list_item_id


def create_scenario(
    project_key: str,
    scenario_name: str,
    scenario_type: str,
    definition: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a new scenario in a Dataiku DSS project.
    
    Args:
        project_key: The project key where the scenario will be created
        scenario_name: Name of the scenario to create
        scenario_type: Type of scenario ('step_based' or 'custom_python')
        definition: Optional scenario definition dict. If None, defaults to {'params': {}}
    
    Returns:
        Dict with status and scenario details or error message
    """
    # Validate scenario type before attempting connection
    valid_types = ['step_based', 'custom_python']
    if scenario_type not in valid_types:
        return {
            "status": "error",
            "message": f"Invalid scenario type '{scenario_type}'. Must be one of: {valid_types}"
        }
    
    try:
        project = get_project(project_key)
        
        # Set default definition if not provided
        if definition is None:
            definition = {'params': {}}
        
        # Create the scenario
        scenario = project.create_scenario(
            scenario_name=scenario_name,
            type=scenario_type,
            definition=definition
        )
        
        return {
            "status": "ok",
            "scenario_name": scenario_name,
            "scenario_id": scenario.id,
            "scenario_type": scenario_type,
            "project_key": project_key,
            "message": f"Scenario '{scenario_name}' created successfully"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to create scenario '{scenario_name}': {str(e)}"
        }


def update_scenario(
    project_key: str,
    scenario_id: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Update an existing scenario's settings.
    
    Args:
        project_key: The project key containing the scenario
        scenario_id: ID of the scenario to update
        **kwargs: Update parameters including:
            - name: New scenario name
            - description: Scenario description
            - active: Whether the scenario is active (bool)
            - tags: List of tags
            - custom_fields: Dict of custom metadata fields
            - definition: Scenario definition dict
            - step_script: Python script code to update in a custom_python step
            - step_index: Index of the step to update (default: 0)
    
    Returns:
        Dict with status and update details or error message
    """
    try:
        project = get_project(project_key)
        scenario = project.get_scenario(scenario_id)
        
        updated_fields = []
        
        # Update scenario metadata if provided
        if any(key in kwargs for key in ['description', 'tags', 'custom_fields']):
            metadata = scenario.get_metadata()
            
            if 'description' in kwargs:
                metadata['description'] = kwargs['description']
                updated_fields.append('description')
            
            if 'tags' in kwargs:
                metadata['tags'] = kwargs['tags']
                updated_fields.append('tags')
            
            if 'custom_fields' in kwargs:
                if 'customFields' not in metadata:
                    metadata['customFields'] = {}
                metadata['customFields'].update(kwargs['custom_fields'])
                updated_fields.append('custom_fields')
            
            scenario.set_metadata(metadata)
        
        # Update scenario settings
        if any(key in kwargs for key in ['name', 'active', 'definition', 'step_script']):
            settings = scenario.get_settings()
            
            if 'name' in kwargs:
                settings.name = kwargs['name']
                updated_fields.append('name')
            
            if 'active' in kwargs:
                settings.active = kwargs['active']
                updated_fields.append('active')
            
            if 'definition' in kwargs:
                # Update the scenario definition through the scenario handle.
                try:
                    current_definition = scenario.get_definition()
                    current_definition.update(kwargs['definition'])
                    scenario.set_definition(current_definition)
                    updated_fields.append('definition')
                except Exception:
                    # Fallback: direct update of settings data
                    raw = settings.get_raw()
                    raw.update(kwargs['definition'])
                    updated_fields.append('definition')
            
            if 'step_script' in kwargs:
                # Update Python script in the first custom_python step
                step_index = kwargs.get('step_index', 0)  # Default to first step
                script_code = kwargs['step_script']
                
                # Access raw steps directly
                raw_steps = settings.raw_steps
                if step_index < len(raw_steps):
                    step = raw_steps[step_index]
                    if step.get('type') == 'custom_python':
                        if 'params' not in step:
                            step['params'] = {}
                        step['params']['script'] = script_code
                        updated_fields.append('step_script')
                    else:
                        raise ValueError(f"Step {step_index} is not a custom_python step")
                else:
                    raise ValueError(f"Step index {step_index} is out of range")
            
            settings.save()
        
        return {
            "status": "ok",
            "scenario_id": scenario_id,
            "updated_fields": updated_fields,
            "message": f"Scenario '{scenario_id}' updated successfully"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to update scenario '{scenario_id}': {str(e)}"
        }


def delete_scenario(
    project_key: str,
    scenario_id: str
) -> Dict[str, Any]:
    """
    Delete a scenario from a Dataiku DSS project.
    
    Args:
        project_key: The project key containing the scenario
        scenario_id: ID of the scenario to delete
    
    Returns:
        Dict with status and deletion details or error message
    """
    try:
        project = get_project(project_key)
        scenario = project.get_scenario(scenario_id)
        
        # Store scenario info before deletion (DSSScenario has no name/type attributes;
        # those live in settings.get_raw())
        try:
            raw = scenario.get_settings().get_raw()
        except Exception:
            raw = {}
        scenario_info = {
            "id": scenario_id,
            "name": raw.get('name', scenario_id),
            "type": raw.get('type', 'unknown')
        }
        
        # Delete the scenario
        scenario.delete()
        
        return {
            "status": "ok",
            "deleted_scenario": scenario_info,
            "message": f"Scenario '{scenario_id}' deleted successfully"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to delete scenario '{scenario_id}': {str(e)}"
        }


def add_scenario_trigger(
    project_key: str,
    scenario_id: str,
    trigger_type: str,
    **params
) -> Dict[str, Any]:
    """
    Add a trigger to a scenario.
    
    Args:
        project_key: The project key containing the scenario
        scenario_id: ID of the scenario to add trigger to
        trigger_type: Type of trigger ('time', 'dataset', 'periodic', 'hourly', 'daily', 'monthly')
        **params: Trigger-specific parameters:
            For 'periodic': every_minutes (int)
            For 'hourly': starting_hour (int), minute_of_hour (int), repeat_every (int)
            For 'daily': hour (int), minute (int), year (int), month (int), day (int), repeat_every (int)
            For 'monthly': day (int), hour (int), minute (int), year (int), month (int)
            For 'dataset': dataset_name (str), project_key (str, optional)
            For 'time': Use one of the specific time trigger types above
    
    Returns:
        Dict with status and trigger details or error message
    """
    # Validate trigger type before attempting connection
    valid_trigger_types = ['periodic', 'hourly', 'daily', 'monthly', 'dataset']
    if trigger_type == 'time':
        return {
            "status": "error",
            "message": "Use specific time trigger types: periodic, hourly, daily, or monthly"
        }
    
    if trigger_type not in valid_trigger_types:
        return {
            "status": "error",
            "message": f"Unsupported trigger type '{trigger_type}'. Supported types: {', '.join(valid_trigger_types)}"
        }
    
    # Validate dataset trigger parameters
    if trigger_type == 'dataset' and 'dataset_name' not in params:
        return {
            "status": "error",
            "message": "dataset_name is required for dataset triggers"
        }
    
    try:
        project = get_project(project_key)
        scenario = project.get_scenario(scenario_id)
        settings = scenario.get_settings()
        
        # Map trigger types to actual methods
        trigger_added = False
        trigger_details = {"type": trigger_type}
        
        if trigger_type == 'periodic':
            every_minutes = params.get('every_minutes', 60)
            settings.add_periodic_trigger(every_minutes=every_minutes)
            trigger_details['every_minutes'] = every_minutes
            trigger_added = True
            
        elif trigger_type == 'hourly':
            starting_hour = params.get('starting_hour', 0)
            minute_of_hour = params.get('minute_of_hour', 0)
            repeat_every = params.get('repeat_every', 1)
            settings.add_hourly_trigger(
                starting_hour=starting_hour,
                minute_of_hour=minute_of_hour,
                repeat_every=repeat_every
            )
            trigger_details.update({
                'starting_hour': starting_hour,
                'minute_of_hour': minute_of_hour,
                'repeat_every': repeat_every
            })
            trigger_added = True
            
        elif trigger_type == 'daily':
            hour = params.get('hour', 2)
            minute = params.get('minute', 0)
            year = params.get('year')
            month = params.get('month')
            day = params.get('day')
            repeat_every = params.get('repeat_every', 1)
            timezone = params.get('timezone', 'SERVER')
            
            settings.add_daily_trigger(
                hour=hour,
                minute=minute,
                year=year,
                month=month,
                day=day,
                repeat_every=repeat_every,
                timezone=timezone
            )
            trigger_details.update({
                'hour': hour,
                'minute': minute,
                'year': year,
                'month': month,
                'day': day,
                'repeat_every': repeat_every,
                'timezone': timezone
            })
            trigger_added = True
            
        elif trigger_type == 'monthly':
            day = params.get('day', 1)
            hour = params.get('hour', 2)
            minute = params.get('minute', 0)
            year = params.get('year')
            month = params.get('month')
            
            settings.add_monthly_trigger(
                day=day,
                hour=hour,
                minute=minute,
                year=year,
                month=month
            )
            trigger_details.update({
                'day': day,
                'hour': hour,
                'minute': minute,
                'year': year,
                'month': month
            })
            trigger_added = True
            
        elif trigger_type == 'dataset':
            dataset_name = params.get('dataset_name')
            dataset_project_key = params.get('project_key', project_key)

            # The Python API does not expose an `add_dataset_trigger` helper;
            # mutate raw_triggers directly.
            trigger = {
                "type": "dataset_changes",
                "name": params.get('name', f"Trigger on {dataset_name}"),
                "active": True,
                "params": {
                    "datasetsToMonitor": [
                        {
                            "projectKey": dataset_project_key,
                            "datasetName": dataset_name,
                        }
                    ],
                    "minIntervalBetweenRuns": params.get('min_interval_seconds', 60),
                },
            }
            settings.raw_triggers.append(trigger)
            trigger_details.update({
                'dataset_name': dataset_name,
                'project_key': dataset_project_key,
            })
            trigger_added = True
        
        if trigger_added:
            settings.save()
            trigger_idx = len(settings.raw_triggers) - 1
            return {
                "status": "ok",
                "scenario_id": scenario_id,
                "trigger_idx": trigger_idx,
                "trigger_details": trigger_details,
                "message": f"Trigger '{trigger_type}' added to scenario '{scenario_id}' at index {trigger_idx}",
            }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to add trigger to scenario '{scenario_id}': {str(e)}"
        }


def remove_scenario_trigger(
    project_key: str,
    scenario_id: str,
    trigger_idx: int
) -> Dict[str, Any]:
    """
    Remove a trigger from a scenario by index.
    
    Args:
        project_key: The project key containing the scenario
        scenario_id: ID of the scenario to remove trigger from
        trigger_idx: Index of the trigger to remove (0-based)
    
    Returns:
        Dict with status and removal details or error message
    """
    try:
        project = get_project(project_key)
        scenario = project.get_scenario(scenario_id)
        settings = scenario.get_settings()
        
        # Get current triggers (raw_triggers is a property on DSSScenarioSettings)
        triggers = settings.raw_triggers
        
        if trigger_idx < 0 or trigger_idx >= len(triggers):
            return {
                "status": "error",
                "message": f"Invalid trigger index {trigger_idx}. Valid range: 0-{len(triggers)-1}"
            }
        
        # Get trigger info before removal
        trigger_info = triggers[trigger_idx]
        
        # Remove the trigger
        del triggers[trigger_idx]
        
        # Save the settings
        settings.save()
        
        return {
            "status": "ok",
            "scenario_id": scenario_id,
            "removed_trigger": {
                "index": trigger_idx,
                "type": trigger_info.get('type', 'unknown'),
                "name": trigger_info.get('name', 'unnamed')
            },
            "remaining_triggers": len(triggers) - 1,
            "message": f"Trigger at index {trigger_idx} removed from scenario '{scenario_id}' successfully"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to remove trigger from scenario '{scenario_id}': {str(e)}"
        }


def run_scenario(
    project_key: str,
    scenario_id: str,
    wait: bool = True,
    no_fail: bool = False
) -> Dict[str, Any]:
    """
    Run a scenario and optionally wait for completion.
    
    Args:
        project_key: The project key containing the scenario
        scenario_id: ID of the scenario to run
        wait: Whether to wait for completion (default: True)
        no_fail: Whether to suppress failures (default: False)
    
    Returns:
        Dict with status and run details or error message
    """
    try:
        project = get_project(project_key)
        scenario = project.get_scenario(scenario_id)
        
        if wait:
            # Run scenario and wait for completion
            run_result = scenario.run_and_wait(no_fail=no_fail)
            
            # Extract run information
            run_info = {
                "scenario_id": scenario_id,
                "run_id": getattr(run_result, 'id', 'unknown'),
                "outcome": getattr(run_result, 'outcome', 'unknown'),
                "start_time": getattr(run_result, 'start_time', None),
                "end_time": getattr(run_result, 'end_time', None),
                "duration": getattr(run_result, 'duration', None),
                "waited_for_completion": True
            }
            
            # Check if run was successful
            outcome = run_info.get('outcome', '').upper()
            if outcome == 'SUCCESS':
                status = "ok"
                message = f"Scenario '{scenario_id}' ran successfully"
            elif outcome == 'FAILED':
                status = "error" if not no_fail else "ok"
                message = f"Scenario '{scenario_id}' run failed"
            else:
                status = "ok"
                message = f"Scenario '{scenario_id}' run completed with outcome: {outcome}"
            
            return {
                "status": status,
                "run_info": run_info,
                "message": message
            }
            
        else:
            # Run scenario without waiting
            trigger_fire = scenario.run()
            
            return {
                "status": "ok",
                "scenario_id": scenario_id,
                "trigger_fire_id": getattr(trigger_fire, 'id', 'unknown'),
                "waited_for_completion": False,
                "message": f"Scenario '{scenario_id}' run initiated successfully"
            }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to run scenario '{scenario_id}': {str(e)}"
        }


def get_scenario_info(
    project_key: str,
    scenario_id: str
) -> Dict[str, Any]:
    """
    Get detailed information about a scenario.
    
    Args:
        project_key: The project key containing the scenario
        scenario_id: ID of the scenario to inspect
    
    Returns:
        Dict with scenario information or error message
    """
    try:
        project = get_project(project_key)
        scenario = project.get_scenario(scenario_id)
        
        # Get scenario metadata
        metadata = scenario.get_metadata()

        # Get scenario settings
        settings = scenario.get_settings()

        # Triggers are exposed as the `raw_triggers` property
        triggers = settings.raw_triggers

        # Get scenario status (DSSScenarioStatus)
        status_obj = scenario.get_status()
        status_raw = status_obj.get_raw() if hasattr(status_obj, 'get_raw') else {}

        # next_run is a property on DSSScenarioStatus, not on DSSScenario itself
        try:
            next_run_dt = status_obj.next_run
            next_run_str = next_run_dt.isoformat() if next_run_dt else None
        except Exception:
            next_run_str = None

        # The scenario is "active" when its automatic triggers are enabled;
        # this lives on DSSScenarioSettings.active
        is_active = bool(getattr(settings, 'active', False))

        last_state = status_raw.get("lastState", {}) or {}
        last_run = last_state.get("lastScenarioRun", {}) or status_raw.get("lastScenarioRun", {}) or {}

        return {
            "status": "ok",
            "scenario_info": {
                "id": scenario_id,
                "name": status_raw.get("name") or scenario_id,
                "type": status_raw.get("type", "unknown"),
                "active": is_active,
                "running": bool(status_raw.get("running", False)),
                "description": metadata.get("description", ""),
                "tags": metadata.get("tags", []),
                "custom_fields": metadata.get("customFields", {}),
                "triggers": [
                    {
                        "type": trigger.get('type', 'unknown'),
                        "name": trigger.get('name', 'unnamed'),
                        "active": trigger.get('active', False)
                    }
                    for trigger in triggers
                ],
                "trigger_count": len(triggers),
                "last_run": {
                    "outcome": (last_run.get("result", {}) or {}).get("outcome") or last_run.get("outcome"),
                    "start_time": last_run.get("start") or last_run.get("startTime"),
                    "end_time": last_run.get("end") or last_run.get("endTime"),
                    "duration": last_run.get("duration"),
                },
                "next_run": next_run_str,
                "is_active": is_active,
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get scenario info for '{scenario_id}': {str(e)}"
        }


def list_scenarios(
    project_key: str,
    scenario_type: Optional[str] = None,
    active_only: bool = False
) -> Dict[str, Any]:
    """
    List all scenarios in a project, optionally filtered by type or active status.
    
    Args:
        project_key: The project key to list scenarios from
        scenario_type: Optional filter by scenario type ('step_based' or 'custom_python')
        active_only: Whether to list only active scenarios (default: False)
    
    Returns:
        Dict with list of scenarios or error message
    """
    try:
        project = get_project(project_key)
        
        # list_scenarios() defaults to returning DSSScenarioListItem objects (not dicts)
        all_scenarios = project.list_scenarios()

        scenarios_info = []
        for scenario_data in all_scenarios:
            # DSSScenarioListItem has .id property; raw dict access works only for the
            # underlying _data field, so prefer the property.
            scenario_id = getattr(scenario_data, 'id', None)
            scenario_id = scenario_list_item_id(scenario_data) or scenario_id

            try:
                scenario = project.get_scenario(scenario_id)
                settings = scenario.get_settings()
                raw = settings.get_raw() if hasattr(settings, 'get_raw') else {}

                s_type = raw.get('type', 'unknown')
                s_active = bool(getattr(settings, 'active', raw.get('active', False)))
                s_name = raw.get('name') or item_get(scenario_data, "name", scenario_id)

                # Apply filters
                if scenario_type and s_type != scenario_type:
                    continue
                if active_only and not s_active:
                    continue

                scenarios_info.append({
                    "id": scenario_id,
                    "name": s_name,
                    "type": s_type,
                    "active": s_active,
                    "description": raw.get('description', ''),
                    "tags": raw.get('tags', item_get(scenario_data, "tags", [])),
                    "trigger_count": len(getattr(settings, 'raw_triggers', []) or []),
                })

            except Exception as e:
                scenarios_info.append({
                    "id": scenario_id,
                    "name": scenario_id,
                    "type": 'unknown',
                    "active": False,
                    "description": '',
                    "tags": [],
                    "trigger_count": 0,
                    "error": f"Could not get full details: {str(e)}"
                })
        
        return {
            "status": "ok",
            "scenarios": scenarios_info,
            "total_count": len(scenarios_info),
            "project_key": project_key,
            "filters": {
                "scenario_type": scenario_type,
                "active_only": active_only
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to list scenarios in project '{project_key}': {str(e)}"
        }


def get_scenario_run_history(
    project_key: str,
    scenario_id: str,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Get the run history for a scenario.
    
    Args:
        project_key: The project key containing the scenario
        scenario_id: ID of the scenario to get run history for
        limit: Maximum number of runs to return (default: 10)
    
    Returns:
        Dict with run history or error message
    """
    try:
        project = get_project(project_key)
        scenario = project.get_scenario(scenario_id)
        
        # Get scenario run history
        if hasattr(scenario, 'get_run_history'):
            run_history = scenario.get_run_history(limit=limit)
        else:
            # Fallback to get_last_runs if get_run_history is not available
            run_history = scenario.get_last_runs(limit=limit) if hasattr(scenario, 'get_last_runs') else []
        
        # Process run history
        processed_runs = []
        for run in run_history:
            # DSSScenarioRun exposes properties: .id, .outcome, .start_time, .end_time,
            # .duration, .trigger (dict). end_time may raise if run still in progress.
            try:
                start_time = run.start_time
                start_str = start_time.isoformat() if start_time else None
            except Exception:
                start_str = None
            try:
                end_time = run.end_time
                end_str = end_time.isoformat() if end_time else None
            except Exception:
                end_str = None
            try:
                outcome = run.outcome
            except Exception:
                outcome = 'unknown'
            trigger = getattr(run, 'trigger', {}) or {}
            run_info = {
                "run_id": getattr(run, 'id', 'unknown'),
                "outcome": outcome,
                "start_time": start_str,
                "end_time": end_str,
                "duration": getattr(run, 'duration', None),
                "trigger_name": trigger.get('name', 'unknown') if isinstance(trigger, dict) else 'unknown',
                "trigger_type": trigger.get('type', 'unknown') if isinstance(trigger, dict) else 'unknown',
            }

            processed_runs.append(run_info)
        
        return {
            "status": "ok",
            "scenario_id": scenario_id,
            "run_history": processed_runs,
            "total_runs": len(processed_runs),
            "message": f"Retrieved {len(processed_runs)} runs for scenario '{scenario_id}'"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get run history for scenario '{scenario_id}': {str(e)}"
        }
