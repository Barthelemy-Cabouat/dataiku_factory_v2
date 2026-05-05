"""
Dataiku DSS client wrapper for MCP integration.
"""

import os
import warnings
from typing import Any, Dict, Optional

import dataikuapi
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

_CLIENT_INSTANCE: Optional[dataikuapi.DSSClient] = None


def get_client() -> dataikuapi.DSSClient:
    """
    Get a configured Dataiku DSS client instance.
    
    Returns:
        dataikuapi.DSSClient: Configured DSS client
        
    Raises:
        ValueError: If required environment variables are missing
        ConnectionError: If connection to DSS fails
    """
    global _CLIENT_INSTANCE
    
    if _CLIENT_INSTANCE is None:
        _CLIENT_INSTANCE = _create_client()
    
    return _CLIENT_INSTANCE


def _create_client() -> dataikuapi.DSSClient:
    """
    Create a new DSS client instance.
    
    Returns:
        dataikuapi.DSSClient: New DSS client instance
    """
    # Get configuration from environment
    dss_host = os.environ.get("DSS_HOST")
    dss_api_key = os.environ.get("DSS_API_KEY")
    insecure_tls = os.environ.get("DSS_INSECURE_TLS", "true").lower() == "true"
    
    if not dss_host:
        raise ValueError("DSS_HOST environment variable is required")
    
    if not dss_api_key:
        raise ValueError("DSS_API_KEY environment variable is required")
    
    try:
        client = dataikuapi.DSSClient(
            dss_host,
            dss_api_key,
            insecure_tls=insecure_tls
        )
        
        # Test connection
        client.get_instance_info()
        
        return client
        
    except Exception as e:
        raise ConnectionError(f"Failed to connect to DSS at {dss_host}: {e}")


def reset_client():
    """
    Reset the client instance (useful for testing).
    """
    global _CLIENT_INSTANCE
    _CLIENT_INSTANCE = None


def get_project(project_key: str) -> dataikuapi.dss.project.DSSProject:
    """
    Get a DSS project by key.
    
    Args:
        project_key: The project key
        
    Returns:
        dataikuapi.DSSProject: Project instance
    """
    client = get_client()
    return client.get_project(project_key)


def list_projects() -> list[str]:
    """
    List all accessible project keys.
    
    Returns:
        list[str]: List of project keys
    """
    client = get_client()
    return client.list_project_keys()


def get_dss_version() -> str:
    """
    Get the DSS version.

    Returns:
        str: DSS version string
    """
    client = get_client()
    return client.get_instance_info()._data.get("dssVersion", "Unknown")


def _get_normalized_host() -> str:
    """Return DSS base URL, normalizing the legacy HTTP :10000 form to HTTPS."""
    host = os.environ.get("DSS_HOST", "").rstrip("/")
    if host.startswith("http://") and ":10000" in host:
        host = "https://" + host[len("http://"):].split(":10000")[0]
    return host


def _rest_session() -> requests.Session:
    """Return a requests Session pre-configured with DSS credentials."""
    session = requests.Session()
    session.auth = (os.environ.get("DSS_API_KEY", ""), "")
    insecure = os.environ.get("DSS_INSECURE_TLS", "true").lower() == "true"
    session.verify = not insecure
    return session


def rest_get_json(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """
    GET a DSS public-API path and return the parsed JSON body.

    Args:
        path: Path relative to /public/api  (e.g. "/projects/KEY/jobs/")
        params: Optional query parameters

    Returns:
        Parsed JSON (dict or list)

    Raises:
        requests.HTTPError: on non-2xx responses
    """
    url = f"{_get_normalized_host()}/public/api{path}"
    r = _rest_session().get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def rest_get_text(path: str, params: Optional[Dict[str, Any]] = None) -> str:
    """
    GET a DSS public-API path and return the raw text body.

    Args:
        path: Path relative to /public/api  (e.g. "/projects/KEY/jobs/ID/log")
        params: Optional query parameters

    Returns:
        Response text

    Raises:
        requests.HTTPError: on non-2xx responses
    """
    url = f"{_get_normalized_host()}/public/api{path}"
    r = _rest_session().get(url, params=params, timeout=120)
    r.raise_for_status()
    return r.text