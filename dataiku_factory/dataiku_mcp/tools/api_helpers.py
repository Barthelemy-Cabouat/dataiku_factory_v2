"""Small compatibility helpers for the Dataiku public API client."""

from typing import Any, Dict, List, Optional


def item_get(item: Any, key: str, default: Any = None) -> Any:
    """Read a field from a Dataiku list item or dict."""
    if isinstance(item, dict):
        return item.get(key, default)
    if hasattr(item, "get"):
        try:
            return item.get(key, default)
        except Exception:
            pass
    return getattr(item, key, default)


def scenario_list_item_id(item: Any) -> Optional[str]:
    """Return the actual scenario id from a DSSScenarioListItem."""
    return item_get(item, "id") or getattr(item, "id", None)


def recipe_definition(recipe: Any) -> Any:
    """Return a recipe definition/settings object using the supported API."""
    return recipe.get_definition_and_payload()


def recipe_io(recipe: Any) -> Dict[str, List[str]]:
    """Return flat input/output refs for a recipe."""
    definition = recipe_definition(recipe)
    return {
        "inputs": definition.get_flat_input_refs(),
        "outputs": definition.get_flat_output_refs(),
    }


def recipe_type(recipe: Any) -> Optional[str]:
    try:
        return recipe_definition(recipe).type
    except Exception:
        return None


def scenario_raw_settings(scenario: Any) -> Dict[str, Any]:
    try:
        return scenario.get_settings().get_raw()
    except Exception:
        return {}


def is_sensitive_name(name: str) -> bool:
    lowered = name.lower()
    sensitive_fragments = (
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "access_key",
        "private_key",
        "credential",
        "bearer",
    )
    return any(fragment in lowered for fragment in sensitive_fragments)
