"""
Productivity tools for Dataiku MCP integration.
"""

import json
import yaml
import copy
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataiku_mcp.client import get_client, get_project

def duplicate_project_structure(
    source_project_key: str,
    target_project_key: str,
    include_data: bool = False
) -> Dict[str, Any]:
    """
    Copy project structure to new project.
    
    Args:
        source_project_key: Source project identifier
        target_project_key: Target project identifier
        include_data: Whether to copy data (default: False)
        
    Returns:
        Dict containing duplication results
    """
    try:
        client = get_client()
        source_project = get_project(source_project_key)
        
        # Create target project
        try:
            target_project = client.create_project(
                target_project_key,
                target_project_key,
                owner=None  # Will use current user
            )
        except Exception as e:
            if "already exists" in str(e).lower():
                target_project = get_project(target_project_key)
            else:
                return {
                    "status": "error",
                    "message": f"Failed to create target project: {str(e)}"
                }
        
        copied_objects = {
            "datasets": [],
            "recipes": [],
            "scenarios": [],
            "variables": [],
            "connections": [],
            "errors": []
        }
        
        # Copy project variables
        try:
            source_variables = source_project.get_variables()
            target_project.set_variables(source_variables)
            copied_objects["variables"] = list(source_variables.get("standard", {}).keys()) + list(source_variables.get("local", {}).keys())
        except Exception as e:
            copied_objects["errors"].append(f"Failed to copy variables: {str(e)}")
        
        # Copy datasets
        datasets = source_project.list_datasets()
        for dataset in datasets:
            try:
                source_dataset = source_project.get_dataset(dataset["name"])
                source_settings = source_dataset.get_settings()
                source_schema = source_dataset.get_schema()
                
                # Create dataset in target project
                dataset_name = dataset["name"]
                dataset_type = dataset["type"]
                
                if dataset_type == "UploadedFiles":
                    # Skip uploaded files as they can't be easily copied
                    copied_objects["errors"].append(f"Skipped uploaded file dataset: {dataset_name}")
                    continue
                
                # Create dataset with same settings
                target_dataset = target_project.create_dataset(
                    dataset_name,
                    dataset_type,
                    params=source_settings.get_raw().get("params", {}),
                    formatType=source_settings.get_raw().get("formatType", "csv")
                )
                
                # Set schema
                target_dataset.set_schema(source_schema)
                
                # Copy data if requested
                if include_data and dataset_type in ["managed", "filesystem"]:
                    try:
                        # Get sample data and write to target
                        source_df = source_dataset.get_dataframe()
                        target_dataset.write_with_schema(source_df)
                    except Exception as e:
                        copied_objects["errors"].append(f"Failed to copy data for {dataset_name}: {str(e)}")
                
                copied_objects["datasets"].append({
                    "name": dataset_name,
                    "type": dataset_type,
                    "data_copied": include_data
                })
                
            except Exception as e:
                copied_objects["errors"].append(f"Failed to copy dataset {dataset['name']}: {str(e)}")
        
        # Copy recipes
        recipes = source_project.list_recipes()
        for recipe in recipes:
            try:
                source_recipe = source_project.get_recipe(recipe["name"])
                source_settings = source_recipe.get_settings()
                source_definition = source_recipe.get_definition()
                
                # Create recipe in target project
                recipe_name = recipe["name"]
                recipe_type = recipe["type"]
                
                # Map inputs and outputs to target project
                inputs = [inp["ref"] for inp in source_definition["inputs"]]
                outputs = []
                for out in source_definition["outputs"]:
                    outputs.append({
                        "name": out["ref"],
                        "new": False  # Assume datasets already exist
                    })
                
                # Create recipe builder
                builder = target_project.new_recipe(recipe_type, name=recipe_name)
                
                # Add inputs
                for inp in inputs:
                    try:
                        builder.with_input(inp)
                    except:
                        copied_objects["errors"].append(f"Failed to add input {inp} to recipe {recipe_name}")
                
                # Add outputs
                for out in outputs:
                    try:
                        builder.with_output(out["name"])
                    except:
                        copied_objects["errors"].append(f"Failed to add output {out['name']} to recipe {recipe_name}")
                
                # Create recipe
                target_recipe = builder.build()
                
                # Copy settings and code
                target_settings = target_recipe.get_settings()
                
                # Copy recipe-specific settings
                if recipe_type in ["python", "r", "sql", "pyspark", "scala", "shell"]:
                    # Copy code
                    try:
                        code = source_settings.get_code()
                        target_settings.set_code(code)
                    except Exception as e:
                        copied_objects["errors"].append(f"Failed to copy code for recipe {recipe_name}: {str(e)}")
                
                # Copy other recipe parameters
                try:
                    source_params = source_settings.get_recipe_params()
                    target_settings.set_recipe_params(source_params)
                except Exception as e:
                    copied_objects["errors"].append(f"Failed to copy parameters for recipe {recipe_name}: {str(e)}")
                
                target_settings.save()
                
                copied_objects["recipes"].append({
                    "name": recipe_name,
                    "type": recipe_type,
                    "inputs": inputs,
                    "outputs": [out["name"] for out in outputs]
                })
                
            except Exception as e:
                copied_objects["errors"].append(f"Failed to copy recipe {recipe['name']}: {str(e)}")
        
        # Copy scenarios
        scenarios = source_project.list_scenarios()
        for scenario in scenarios:
            try:
                source_scenario = source_project.get_scenario(scenario["id"])
                source_settings = source_scenario.get_settings()
                source_metadata = source_scenario.get_metadata()
                
                # Create scenario in target project
                scenario_name = scenario["name"]
                scenario_type = scenario["type"]
                
                target_scenario = target_project.create_scenario(
                    scenario_name,
                    scenario_type,
                    definition=source_settings.get_definition()
                )
                
                # Copy settings
                target_settings = target_scenario.get_settings()
                target_settings.raw_steps = copy.deepcopy(source_settings.raw_steps)
                target_settings.raw_triggers = copy.deepcopy(source_settings.raw_triggers)
                target_settings.active = source_settings.active
                target_settings.save()
                
                # Copy metadata
                target_scenario.set_metadata(source_metadata)
                
                copied_objects["scenarios"].append({
                    "name": scenario_name,
                    "type": scenario_type,
                    "id": target_scenario.scenario_id,
                    "steps": len(source_settings.raw_steps),
                    "triggers": len(source_settings.raw_triggers)
                })
                
            except Exception as e:
                copied_objects["errors"].append(f"Failed to copy scenario {scenario['name']}: {str(e)}")
        
        # Summary statistics
        duplication_summary = {
            "source_project": source_project_key,
            "target_project": target_project_key,
            "include_data": include_data,
            "datasets_copied": len(copied_objects["datasets"]),
            "recipes_copied": len(copied_objects["recipes"]),
            "scenarios_copied": len(copied_objects["scenarios"]),
            "variables_copied": len(copied_objects["variables"]),
            "total_errors": len(copied_objects["errors"]),
            "success_rate": (
                (len(copied_objects["datasets"]) + len(copied_objects["recipes"]) + len(copied_objects["scenarios"])) /
                (len(datasets) + len(recipes) + len(scenarios)) * 100
                if (len(datasets) + len(recipes) + len(scenarios)) > 0 else 0
            )
        }
        
        return {
            "status": "ok",
            "duplication_summary": duplication_summary,
            "copied_objects": copied_objects
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to duplicate project structure: {str(e)}"
        }


def export_project_config(
    project_key: str,
    format: str = "json"
) -> Dict[str, Any]:
    """
    Export project configuration as JSON/YAML.
    
    Args:
        project_key: The project key
        format: Export format (json/yaml)
        
    Returns:
        Dict containing exported configuration
    """
    try:
        project = get_project(project_key)
        
        # Gather all project configuration
        config = {
            "project_info": {},
            "variables": {},
            "datasets": [],
            "recipes": [],
            "scenarios": [],
            "connections": [],
            "settings": {}
        }
        
        # Get project metadata
        metadata = project.get_metadata()
        config["project_info"] = {
            "key": project_key,
            "name": metadata.get("name", project_key),
            "description": metadata.get("description", ""),
            "tags": metadata.get("tags", []),
            "owner": metadata.get("owner", "unknown"),
            "custom_fields": metadata.get("customFields", {}),
            "creation_date": metadata.get("creationDate", ""),
            "export_date": str(datetime.now()) if 'datetime' in globals() else "unknown"
        }
        
        # Get project variables
        variables = project.get_variables()
        config["variables"] = {
            "standard": variables.get("standard", {}),
            "local": variables.get("local", {})
        }
        
        # Get project settings
        settings = project.get_settings()
        config["settings"] = {
            "code_env_settings": settings.get_code_env_settings(),
            "bundle_export_options": settings.get_raw().get("bundleExportOptions", {}),
            "git_reference": settings.get_raw().get("gitReference", {}),
            "flow_display_settings": settings.get_raw().get("flowDisplaySettings", {})
        }
        
        # Export datasets
        datasets = project.list_datasets()
        for dataset in datasets:
            try:
                dataset_obj = project.get_dataset(dataset["name"])
                dataset_settings = dataset_obj.get_settings()
                dataset_schema = dataset_obj.get_schema()
                
                dataset_config = {
                    "name": dataset["name"],
                    "type": dataset["type"],
                    "description": dataset.get("description", ""),
                    "tags": dataset.get("tags", []),
                    "settings": dataset_settings.get_raw(),
                    "schema": dataset_schema
                }
                
                config["datasets"].append(dataset_config)
                
            except Exception as e:
                config["datasets"].append({
                    "name": dataset["name"],
                    "error": f"Failed to export dataset: {str(e)}"
                })
        
        # Export recipes
        recipes = project.list_recipes()
        for recipe in recipes:
            try:
                recipe_obj = project.get_recipe(recipe["name"])
                recipe_settings = recipe_obj.get_settings()
                recipe_definition = recipe_obj.get_definition()
                
                recipe_config = {
                    "name": recipe["name"],
                    "type": recipe["type"],
                    "description": recipe.get("description", ""),
                    "tags": recipe.get("tags", []),
                    "definition": recipe_definition,
                    "settings": recipe_settings.get_raw()
                }
                
                # Include code for code recipes
                if recipe["type"] in ["python", "r", "sql", "pyspark", "scala", "shell"]:
                    try:
                        code = recipe_settings.get_code()
                        recipe_config["code"] = code
                    except:
                        recipe_config["code"] = "# Could not retrieve code"
                
                config["recipes"].append(recipe_config)
                
            except Exception as e:
                config["recipes"].append({
                    "name": recipe["name"],
                    "error": f"Failed to export recipe: {str(e)}"
                })
        
        # Export scenarios
        scenarios = project.list_scenarios()
        for scenario in scenarios:
            try:
                scenario_obj = project.get_scenario(scenario["id"])
                scenario_settings = scenario_obj.get_settings()
                scenario_metadata = scenario_obj.get_metadata()
                
                scenario_config = {
                    "id": scenario["id"],
                    "name": scenario["name"],
                    "type": scenario["type"],
                    "description": scenario.get("description", ""),
                    "tags": scenario.get("tags", []),
                    "active": scenario.get("active", False),
                    "metadata": scenario_metadata,
                    "settings": scenario_settings.get_raw(),
                    "steps": scenario_settings.raw_steps,
                    "triggers": scenario_settings.raw_triggers
                }
                
                config["scenarios"].append(scenario_config)
                
            except Exception as e:
                config["scenarios"].append({
                    "id": scenario["id"],
                    "name": scenario["name"],
                    "error": f"Failed to export scenario: {str(e)}"
                })
        
        # Format output
        if format.lower() == "yaml":
            try:
                config_output = yaml.dump(config, default_flow_style=False, indent=2)
                content_type = "yaml"
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Failed to format as YAML: {str(e)}"
                }
        else:
            config_output = json.dumps(config, indent=2, default=str)
            content_type = "json"
        
        # Export statistics
        export_stats = {
            "project_key": project_key,
            "format": content_type,
            "datasets_exported": len([d for d in config["datasets"] if "error" not in d]),
            "recipes_exported": len([r for r in config["recipes"] if "error" not in r]),
            "scenarios_exported": len([s for s in config["scenarios"] if "error" not in s]),
            "variables_exported": len(config["variables"]["standard"]) + len(config["variables"]["local"]),
            "export_size": len(config_output),
            "total_objects": len(config["datasets"]) + len(config["recipes"]) + len(config["scenarios"])
        }
        
        return {
            "status": "ok",
            "export_stats": export_stats,
            "config": config,
            "config_output": config_output,
            "content_type": content_type
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to export project configuration: {str(e)}"
        }


def batch_update_objects(
    project_key: str,
    object_type: str,
    pattern: str,
    updates: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update multiple objects with similar changes.
    
    Args:
        project_key: The project key
        object_type: Type of objects to update (datasets, recipes, scenarios)
        pattern: Pattern to match objects (regex supported)
        updates: Updates to apply
        
    Returns:
        Dict containing update results
    """
    try:
        project = get_project(project_key)
        
        # Compile pattern
        try:
            regex_pattern = re.compile(pattern, re.IGNORECASE)
        except re.error:
            # If regex fails, use simple string matching
            regex_pattern = None
        
        updated_objects = []
        failed_updates = []
        
        if object_type.lower() == "datasets":
            # Update datasets
            datasets = project.list_datasets()
            
            for dataset in datasets:
                dataset_name = dataset["name"]
                
                # Check if matches pattern
                matches = False
                if regex_pattern:
                    matches = regex_pattern.search(dataset_name)
                else:
                    matches = pattern.lower() in dataset_name.lower()
                
                if matches:
                    try:
                        dataset_obj = project.get_dataset(dataset_name)
                        
                        # Apply updates
                        if "description" in updates:
                            metadata = dataset_obj.get_metadata()
                            metadata["description"] = updates["description"]
                            dataset_obj.set_metadata(metadata)
                        
                        if "tags" in updates:
                            metadata = dataset_obj.get_metadata()
                            metadata["tags"] = updates["tags"]
                            dataset_obj.set_metadata(metadata)
                        
                        if "settings" in updates:
                            settings = dataset_obj.get_settings()
                            raw_settings = settings.get_raw()
                            raw_settings.update(updates["settings"])
                            settings.save()
                        
                        updated_objects.append({
                            "name": dataset_name,
                            "type": "dataset",
                            "updates_applied": list(updates.keys())
                        })
                        
                    except Exception as e:
                        failed_updates.append({
                            "name": dataset_name,
                            "type": "dataset",
                            "error": str(e)
                        })
        
        elif object_type.lower() == "recipes":
            # Update recipes
            recipes = project.list_recipes()
            
            for recipe in recipes:
                recipe_name = recipe["name"]
                
                # Check if matches pattern
                matches = False
                if regex_pattern:
                    matches = regex_pattern.search(recipe_name)
                else:
                    matches = pattern.lower() in recipe_name.lower()
                
                if matches:
                    try:
                        recipe_obj = project.get_recipe(recipe_name)
                        settings = recipe_obj.get_settings()
                        
                        # Apply updates
                        if "description" in updates:
                            metadata = recipe_obj.get_metadata()
                            metadata["description"] = updates["description"]
                            recipe_obj.set_metadata(metadata)
                        
                        if "tags" in updates:
                            metadata = recipe_obj.get_metadata()
                            metadata["tags"] = updates["tags"]
                            recipe_obj.set_metadata(metadata)
                        
                        if "code" in updates and recipe["type"] in ["python", "r", "sql", "pyspark", "scala", "shell"]:
                            settings.set_code(updates["code"])
                        
                        if "recipe_params" in updates:
                            settings.set_recipe_params(updates["recipe_params"])
                        
                        settings.save()
                        
                        updated_objects.append({
                            "name": recipe_name,
                            "type": "recipe",
                            "updates_applied": list(updates.keys())
                        })
                        
                    except Exception as e:
                        failed_updates.append({
                            "name": recipe_name,
                            "type": "recipe",
                            "error": str(e)
                        })
        
        elif object_type.lower() == "scenarios":
            # Update scenarios
            scenarios = project.list_scenarios()
            
            for scenario in scenarios:
                scenario_name = scenario["name"]
                
                # Check if matches pattern
                matches = False
                if regex_pattern:
                    matches = regex_pattern.search(scenario_name)
                else:
                    matches = pattern.lower() in scenario_name.lower()
                
                if matches:
                    try:
                        scenario_obj = project.get_scenario(scenario["id"])
                        
                        # Apply updates
                        if "description" in updates:
                            metadata = scenario_obj.get_metadata()
                            metadata["description"] = updates["description"]
                            scenario_obj.set_metadata(metadata)
                        
                        if "tags" in updates:
                            metadata = scenario_obj.get_metadata()
                            metadata["tags"] = updates["tags"]
                            scenario_obj.set_metadata(metadata)
                        
                        if "active" in updates:
                            settings = scenario_obj.get_settings()
                            settings.active = updates["active"]
                            settings.save()
                        
                        updated_objects.append({
                            "name": scenario_name,
                            "type": "scenario",
                            "id": scenario["id"],
                            "updates_applied": list(updates.keys())
                        })
                        
                    except Exception as e:
                        failed_updates.append({
                            "name": scenario_name,
                            "type": "scenario",
                            "id": scenario["id"],
                            "error": str(e)
                        })
        
        else:
            return {
                "status": "error",
                "message": f"Unsupported object type: {object_type}. Supported types: datasets, recipes, scenarios"
            }
        
        # Summary
        update_summary = {
            "object_type": object_type,
            "pattern": pattern,
            "updates_requested": updates,
            "objects_updated": len(updated_objects),
            "objects_failed": len(failed_updates),
            "success_rate": (len(updated_objects) / (len(updated_objects) + len(failed_updates)) * 100) if (len(updated_objects) + len(failed_updates)) > 0 else 0
        }
        
        return {
            "status": "ok",
            "project_key": project_key,
            "update_summary": update_summary,
            "updated_objects": updated_objects,
            "failed_updates": failed_updates
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to batch update objects: {str(e)}"
        }