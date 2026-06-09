"""
Flow Zone management tools for Dataiku DSS.

This module provides functions for creating, listing, and populating Flow Zones,
and for inspecting which zone an object belongs to, through the dataiku-api-client.
"""

from typing import Dict, List, Optional, Any
from dataiku_mcp.client import get_project


def _zone_summary(zone) -> Dict[str, Any]:
    """Build a compact, JSON-safe summary of a DSSFlowZone."""
    summary: Dict[str, Any] = {"id": zone.id, "name": zone.name}
    try:
        summary["color"] = zone.color
    except Exception:
        pass
    try:
        items = zone.items
        items = items() if callable(items) else items
        summary["item_count"] = len(items)
    except Exception:
        pass
    return summary


def _resolve_object(project, object_type: str, object_name: str):
    """Return a DSS handle (dataset/recipe) for a name + type."""
    ot = (object_type or "").lower()
    if ot in ("dataset", "datasets"):
        return project.get_dataset(object_name)
    if ot in ("recipe", "recipes"):
        return project.get_recipe(object_name)
    if ot in ("folder", "managed_folder", "managedfolder"):
        return project.get_managed_folder(object_name)
    raise ValueError(
        f"Unsupported object_type '{object_type}'. Use 'dataset', 'recipe', or 'folder'."
    )


def create_zone(
    project_key: str,
    zone_name: str,
    color: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new Flow Zone in a project (idempotent on name).

    Args:
        project_key: The project key
        zone_name: Name for the new zone
        color: Optional hex color (e.g. '#2ab1ac')

    Returns:
        Dict with status and zone details or error message
    """
    try:
        project = get_project(project_key)
        flow = project.get_flow()

        # Idempotent: return the existing zone if one already has this name
        for z in flow.list_zones():
            if z.name == zone_name:
                return {
                    "status": "ok",
                    "created": False,
                    "zone": _zone_summary(z),
                    "message": f"Zone '{zone_name}' already exists",
                }

        zone = flow.create_zone(zone_name, color) if color else flow.create_zone(zone_name)
        return {
            "status": "ok",
            "created": True,
            "zone": _zone_summary(zone),
            "message": f"Zone '{zone_name}' created successfully",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to create zone '{zone_name}': {str(e)}",
        }


def list_zones(project_key: str) -> Dict[str, Any]:
    """
    List all Flow Zones in a project.

    Args:
        project_key: The project key

    Returns:
        Dict with the list of zones or error message
    """
    try:
        project = get_project(project_key)
        flow = project.get_flow()
        zones = [_zone_summary(z) for z in flow.list_zones()]
        return {
            "status": "ok",
            "project_key": project_key,
            "zones": zones,
            "zone_count": len(zones),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to list zones in project '{project_key}': {str(e)}",
        }


def move_to_zone(
    project_key: str,
    zone: str,
    items: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    Move datasets/recipes/folders into a Flow Zone.

    Args:
        project_key: The project key
        zone: Zone id or zone name to move items into
        items: List of {"type": "dataset"|"recipe"|"folder", "name": <object_name>}

    Returns:
        Dict with per-item results or error message
    """
    try:
        project = get_project(project_key)
        flow = project.get_flow()

        # Resolve zone by id first, then by name
        target = None
        try:
            target = flow.get_zone(zone)
        except Exception:
            target = None
        if target is None:
            for z in flow.list_zones():
                if z.name == zone:
                    target = z
                    break
        if target is None:
            return {"status": "error", "message": f"Zone '{zone}' not found"}

        moved, failed = [], []
        for spec in items:
            name = spec.get("name")
            otype = spec.get("type", "dataset")
            try:
                obj = _resolve_object(project, otype, name)
                target.add_item(obj)
                moved.append({"type": otype, "name": name})
            except Exception as e:
                failed.append({"type": otype, "name": name, "error": str(e)})

        return {
            "status": "ok" if not failed else "partial",
            "zone": _zone_summary(target),
            "moved": moved,
            "failed": failed,
            "message": f"Moved {len(moved)} item(s) into zone '{target.name}'"
                       + (f", {len(failed)} failed" if failed else ""),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to move items into zone '{zone}': {str(e)}",
        }


def get_zone_of_object(
    project_key: str,
    object_name: str,
    object_type: str = "dataset",
) -> Dict[str, Any]:
    """
    Get the Flow Zone an object currently belongs to.

    Args:
        project_key: The project key
        object_name: Name of the dataset/recipe/folder
        object_type: 'dataset' (default), 'recipe', or 'folder'

    Returns:
        Dict with the owning zone or error message
    """
    try:
        project = get_project(project_key)
        flow = project.get_flow()
        obj = _resolve_object(project, object_type, object_name)
        zone = flow.get_zone_of_object(obj)
        return {
            "status": "ok",
            "object": {"type": object_type, "name": object_name},
            "zone": _zone_summary(zone) if zone is not None else None,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get zone of '{object_name}': {str(e)}",
        }


def delete_zone(
    project_key: str,
    zone: str,
) -> Dict[str, Any]:
    """
    Delete a Flow Zone (its items move back to the default zone).

    Args:
        project_key: The project key
        zone: Zone id or zone name to delete

    Returns:
        Dict with status or error message
    """
    try:
        project = get_project(project_key)
        flow = project.get_flow()

        target = None
        try:
            target = flow.get_zone(zone)
        except Exception:
            target = None
        if target is None:
            for z in flow.list_zones():
                if z.name == zone:
                    target = z
                    break
        if target is None:
            return {"status": "error", "message": f"Zone '{zone}' not found"}

        zone_info = _zone_summary(target)
        target.delete()
        return {
            "status": "ok",
            "deleted_zone": zone_info,
            "message": f"Zone '{zone_info.get('name')}' deleted successfully",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to delete zone '{zone}': {str(e)}",
        }
