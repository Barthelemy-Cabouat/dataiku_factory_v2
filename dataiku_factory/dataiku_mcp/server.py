"""
MCP Server for Dataiku DSS integration.
"""

from mcp.server.fastmcp import FastMCP
from typing import Any, Dict, List, Optional
import json
import logging

from dataiku_mcp.client import get_client, get_project, list_projects

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP("Dataiku DSS MCP Server")

# Server description
mcp.description = """
A Model Context Protocol server for Dataiku DSS integration.
Provides tools for managing recipes, datasets, and scenarios.
"""

# Tool implementations will be imported from tools modules
from dataiku_mcp.tools import recipes, datasets, scenarios
from dataiku_mcp.tools import advanced_scenarios, code_development, project_exploration
from dataiku_mcp.tools import environment_config, monitoring_debug, productivity
from dataiku_mcp.tools import notebooks, wiki

# Register Recipe Tools
@mcp.tool()
def create_recipe(
    project_key: str,
    recipe_type: str,
    recipe_name: str,
    inputs: List[str],
    outputs: List[Dict[str, Any]],
    code: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new recipe in a Dataiku project.
    
    Args:
        project_key: The project key
        recipe_type: Type of recipe (e.g., 'python', 'sql', 'join')
        recipe_name: Name for the new recipe
        inputs: List of input dataset names
        outputs: List of output dataset configurations
        code: Optional code for the recipe
        
    Returns:
        Dict containing recipe creation result
    """
    return recipes.create_recipe(
        project_key, recipe_type, recipe_name, inputs, outputs, code
    )

@mcp.tool()
def update_recipe(
    project_key: str,
    recipe_name: str,
    code: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    custom_fields: Optional[Dict[str, Any]] = None,
    engine_type: Optional[str] = None,
    container_conf: Optional[Dict[str, Any]] = None,
    resource_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Update an existing recipe.
    
    Args:
        project_key: The project key
        recipe_name: Name of the recipe to update
        code: New code content for code recipes
        description: Updated recipe description
        tags: Updated recipe tags
        custom_fields: Updated custom metadata fields
        engine_type: Updated engine selection
        container_conf: Updated container configuration
        resource_settings: Updated resource settings
        
    Returns:
        Dict containing update result
    """
    return recipes.update_recipe(
        project_key,
        recipe_name,
        code=code,
        description=description,
        tags=tags,
        custom_fields=custom_fields,
        engine_type=engine_type,
        container_conf=container_conf,
        resource_settings=resource_settings,
    )

@mcp.tool()
def delete_recipe(
    project_key: str,
    recipe_name: str
) -> Dict[str, Any]:
    """
    Delete a recipe from a project.
    
    Args:
        project_key: The project key
        recipe_name: Name of the recipe to delete
        
    Returns:
        Dict containing deletion result
    """
    return recipes.delete_recipe(project_key, recipe_name)

@mcp.tool()
def run_recipe(
    project_key: str,
    recipe_name: str,
    build_mode: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run a recipe to build its outputs.
    
    Args:
        project_key: The project key
        recipe_name: Name of the recipe to run
        build_mode: Optional build mode
        
    Returns:
        Dict containing run result
    """
    return recipes.run_recipe(project_key, recipe_name, build_mode)

# Register Dataset Tools
@mcp.tool()
def create_dataset(
    project_key: str,
    dataset_name: str,
    dataset_type: str,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a new dataset in a project.
    
    Args:
        project_key: The project key
        dataset_name: Name for the new dataset
        dataset_type: Type of dataset (e.g., 'filesystem', 'sql')
        params: Dataset configuration parameters
        
    Returns:
        Dict containing dataset creation result
    """
    return datasets.create_dataset(project_key, dataset_name, dataset_type, params)

@mcp.tool()
def update_dataset(
    project_key: str,
    dataset_name: str,
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Update dataset settings.
    
    Args:
        project_key: The project key
        dataset_name: Name of the dataset to update
        **kwargs: Dataset settings to update
        
    Returns:
        Dict containing update result
    """
    return datasets.update_dataset(project_key, dataset_name, **kwargs)

@mcp.tool()
def delete_dataset(
    project_key: str,
    dataset_name: str,
    drop_data: bool = False
) -> Dict[str, Any]:
    """
    Delete a dataset from a project.
    
    Args:
        project_key: The project key
        dataset_name: Name of the dataset to delete
        drop_data: Whether to drop the underlying data
        
    Returns:
        Dict containing deletion result
    """
    return datasets.delete_dataset(project_key, dataset_name, drop_data)

@mcp.tool()
def build_dataset(
    project_key: str,
    dataset_name: str,
    mode: Optional[str] = None,
    partition: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build a dataset.
    
    Args:
        project_key: The project key
        dataset_name: Name of the dataset to build
        mode: Optional build mode
        partition: Optional partition specification
        
    Returns:
        Dict containing build result
    """
    return datasets.build_dataset(project_key, dataset_name, mode, partition)

@mcp.tool()
def inspect_dataset_schema(
    project_key: str,
    dataset_name: str
) -> Dict[str, Any]:
    """
    Get dataset schema information.
    
    Args:
        project_key: The project key
        dataset_name: Name of the dataset
        
    Returns:
        Dict containing schema information
    """
    return datasets.inspect_dataset_schema(project_key, dataset_name)

@mcp.tool()
def check_dataset_metrics(
    project_key: str,
    dataset_name: str
) -> Dict[str, Any]:
    """
    Get latest dataset metrics.
    
    Args:
        project_key: The project key
        dataset_name: Name of the dataset
        
    Returns:
        Dict containing metrics data
    """
    return datasets.check_dataset_metrics(project_key, dataset_name)

# Register Scenario Tools
@mcp.tool()
def create_scenario(
    project_key: str,
    scenario_name: str,
    scenario_type: str,
    definition: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a new scenario in a project.
    
    Args:
        project_key: The project key
        scenario_name: Name for the new scenario
        scenario_type: Type of scenario
        definition: Optional scenario definition
        
    Returns:
        Dict containing scenario creation result
    """
    return scenarios.create_scenario(project_key, scenario_name, scenario_type, definition)

@mcp.tool()
def update_scenario(
    project_key: str,
    scenario_id: str,
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Update scenario settings.
    
    Args:
        project_key: The project key
        scenario_id: ID of the scenario to update
        **kwargs: Scenario settings to update
        
    Returns:
        Dict containing update result
    """
    return scenarios.update_scenario(project_key, scenario_id, **kwargs)

@mcp.tool()
def delete_scenario(
    project_key: str,
    scenario_id: str
) -> Dict[str, Any]:
    """
    Delete a scenario from a project.
    
    Args:
        project_key: The project key
        scenario_id: ID of the scenario to delete
        
    Returns:
        Dict containing deletion result
    """
    return scenarios.delete_scenario(project_key, scenario_id)

@mcp.tool()
def add_scenario_trigger(
    project_key: str,
    scenario_id: str,
    trigger_type: str,
    **params: Any
) -> Dict[str, Any]:
    """
    Add a trigger to a scenario.
    
    Args:
        project_key: The project key
        scenario_id: ID of the scenario
        trigger_type: Type of trigger to add
        **params: Trigger parameters
        
    Returns:
        Dict containing trigger addition result
    """
    return scenarios.add_scenario_trigger(project_key, scenario_id, trigger_type, **params)

@mcp.tool()
def remove_scenario_trigger(
    project_key: str,
    scenario_id: str,
    trigger_idx: int
) -> Dict[str, Any]:
    """
    Remove a trigger from a scenario.
    
    Args:
        project_key: The project key
        scenario_id: ID of the scenario
        trigger_idx: Index of the trigger to remove
        
    Returns:
        Dict containing trigger removal result
    """
    return scenarios.remove_scenario_trigger(project_key, scenario_id, trigger_idx)

@mcp.tool()
def run_scenario(
    project_key: str,
    scenario_id: str
) -> Dict[str, Any]:
    """
    Run a scenario manually.
    
    Args:
        project_key: The project key
        scenario_id: ID of the scenario to run
        
    Returns:
        Dict containing run result
    """
    return scenarios.run_scenario(project_key, scenario_id)

# Register Advanced Scenario Tools
@mcp.tool()
def get_scenario_logs(
    project_key: str,
    scenario_id: str,
    run_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get detailed run logs and error messages for failed scenarios.
    
    Args:
        project_key: The project key
        scenario_id: ID of the scenario
        run_id: Specific run ID (defaults to latest)
        
    Returns:
        Dict containing logs and run information
    """
    return advanced_scenarios.get_scenario_logs(project_key, scenario_id, run_id)

@mcp.tool()
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
    return advanced_scenarios.get_scenario_steps(project_key, scenario_id)

@mcp.tool()
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
    return advanced_scenarios.clone_scenario(project_key, source_scenario_id, new_scenario_name, modifications)

# Register Code Development Tools
@mcp.tool()
def get_recipe_code(
    project_key: str,
    recipe_name: str
) -> Dict[str, Any]:
    """
    Extract actual Python/SQL code from recipes.
    
    Args:
        project_key: The project key
        recipe_name: Name of the recipe
        
    Returns:
        Dict containing code and recipe information
    """
    return code_development.get_recipe_code(project_key, recipe_name)

@mcp.tool()
def validate_recipe_syntax(
    project_key: str,
    recipe_name: str,
    code: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validate Python/SQL syntax before execution.
    
    Args:
        project_key: The project key
        recipe_name: Name of the recipe
        code: Optional code to validate
        
    Returns:
        Dict containing validation results
    """
    return code_development.validate_recipe_syntax(project_key, recipe_name, code)

@mcp.tool()
def test_recipe_dry_run(
    project_key: str,
    recipe_name: str,
    sample_rows: int = 100
) -> Dict[str, Any]:
    """
    Test recipe logic without actual execution.
    
    Args:
        project_key: The project key
        recipe_name: Name of the recipe
        sample_rows: Number of sample rows to test with
        
    Returns:
        Dict containing test results
    """
    return code_development.test_recipe_dry_run(project_key, recipe_name, sample_rows)

# Register Project Exploration Tools
@mcp.tool()
def get_project_flow(
    project_key: str
) -> Dict[str, Any]:
    """
    Get complete data flow/pipeline structure.
    
    Args:
        project_key: The project key
        
    Returns:
        Dict containing flow structure and dependencies
    """
    return project_exploration.get_project_flow(project_key)

@mcp.tool()
def search_project_objects(
    project_key: str,
    search_term: str,
    object_types: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Search for datasets, recipes, scenarios by name/pattern.
    
    Args:
        project_key: The project key
        search_term: Search pattern
        object_types: List of object types to search
        
    Returns:
        Dict containing search results
    """
    return project_exploration.search_project_objects(project_key, search_term, object_types)

@mcp.tool()
def get_dataset_sample(
    project_key: str,
    dataset_name: str,
    rows: int = 100,
    columns: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Get sample data from datasets.
    
    Args:
        project_key: The project key
        dataset_name: Name of the dataset
        rows: Number of sample rows
        columns: Specific columns to include
        
    Returns:
        Dict containing sample data and schema
    """
    return project_exploration.get_dataset_sample(project_key, dataset_name, rows, columns)

# Register Environment Configuration Tools
@mcp.tool()
def get_code_environments(
    project_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    List available Python/R environments.
    
    Args:
        project_key: Project identifier (optional)
        
    Returns:
        Dict containing code environments information
    """
    return environment_config.get_code_environments(project_key)

@mcp.tool()
def get_project_variables(
    project_key: str
) -> Dict[str, Any]:
    """
    Get project-level variables and configuration.
    
    Args:
        project_key: The project key
        
    Returns:
        Dict containing project variables and metadata
    """
    return environment_config.get_project_variables(project_key)

@mcp.tool()
def get_connections(
    project_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    List available data connections.
    
    Args:
        project_key: Project identifier (optional)
        
    Returns:
        Dict containing connection information
    """
    return environment_config.get_connections(project_key)

# Register Monitoring and Debug Tools
@mcp.tool()
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
        status_filter: Filter by status
        
    Returns:
        Dict containing recent runs and summary
    """
    return monitoring_debug.get_recent_runs(project_key, limit, status_filter)

@mcp.tool()
def get_job_details(
    project_key: str,
    job_id: str,
    log_lines: int = 100,
    log_from_end: bool = True,
) -> Dict[str, Any]:
    """
    Get detailed job execution information including per-activity breakdown.

    Args:
        project_key: The project key
        job_id: Job identifier
        log_lines: Number of log lines to include in the response (0 to skip)
        log_from_end: If True (default), return the last N lines; False for first N

    Returns:
        Dict containing job summary, per-activity breakdown, and log excerpt
    """
    return monitoring_debug.get_job_details(project_key, job_id, log_lines, log_from_end)


@mcp.tool()
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

    Args:
        project_key: The project key
        job_id: Job identifier
        lines: Maximum lines to return after filtering (default 200)
        from_end: If True (default), return the last N matching lines;
                  False returns the first N
        grep_pattern: Case-insensitive substring filter on log lines
                      (e.g. "ERROR", "gspread", "PERMISSION_DENIED")
        severity: Keep only lines at this DSS log level:
                  ERROR, WARNING, INFO, or DEBUG
        activity_id: Keep only lines for this activity/recipe
                     (matches "running <id>" and "act.<id>" patterns)

    Returns:
        Dict with filtered log content and metadata
    """
    return monitoring_debug.get_job_log(
        project_key, job_id, lines, from_end, grep_pattern, severity, activity_id
    )


@mcp.tool()
def get_job_activities(
    project_key: str,
    job_id: str,
) -> Dict[str, Any]:
    """
    Get the per-activity execution breakdown for a job (no log fetching).

    Lighter-weight alternative to get_job_details when you only need the
    activity list and failure summary.

    Args:
        project_key: The project key
        job_id: Job identifier

    Returns:
        Dict with job state, error message, and ordered activity list
    """
    return monitoring_debug.get_job_activities(project_key, job_id)


@mcp.tool()
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
    return monitoring_debug.cancel_running_jobs(project_key, job_ids)

# Register Productivity Tools
@mcp.tool()
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
        include_data: Whether to copy data
        
    Returns:
        Dict containing duplication results
    """
    return productivity.duplicate_project_structure(source_project_key, target_project_key, include_data)

@mcp.tool()
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
    return productivity.export_project_config(project_key, format)

@mcp.tool()
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
        object_type: Type of objects to update
        pattern: Pattern to match objects
        updates: Updates to apply
        
    Returns:
        Dict containing update results
    """
    return productivity.batch_update_objects(project_key, object_type, pattern, updates)

# Register Wiki Tools
@mcp.tool()
def list_wiki_articles(project_key: str) -> Dict[str, Any]:
    """
    List all wiki articles in a project.

    Args:
        project_key: The project key

    Returns:
        Dict with list of articles (id, name) and total count
    """
    return wiki.list_articles(project_key)

@mcp.tool()
def get_wiki_article(project_key: str, article_id: int) -> Dict[str, Any]:
    """
    Get the content of a wiki article by id.

    Args:
        project_key: The project key
        article_id:  Integer article id (obtain via list_wiki_articles)

    Returns:
        Dict with article name and body text
    """
    return wiki.get_article(project_key, article_id)

@mcp.tool()
def create_wiki_article(
    project_key: str,
    article_name: str,
    body: str,
    parent_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create a new wiki article.

    Args:
        project_key:  The project key
        article_name: Title of the new article
        body:         Markdown / HTML content
        parent_id:    Optional parent article id for nesting

    Returns:
        Dict with new article id
    """
    return wiki.create_article(project_key, article_name, body, parent_id)

@mcp.tool()
def update_wiki_article(
    project_key: str,
    article_id: int,
    body: Optional[str] = None,
    article_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update an existing wiki article's body and/or title.

    Args:
        project_key:  The project key
        article_id:   Integer article id (obtain via list_wiki_articles)
        body:         New markdown / HTML content (omit to keep existing)
        article_name: New article title (omit to keep existing)

    Returns:
        Dict with updated fields
    """
    return wiki.update_article(project_key, article_id, body, article_name)

# Register Notebook Tools
@mcp.tool()
def list_jupyter_notebooks(
    project_key: str,
    active: bool = False,
) -> Dict[str, Any]:
    """
    List Jupyter notebooks in a Dataiku project.

    Args:
        project_key: The project key
        active: If true, only list currently running notebooks

    Returns:
        Dict with notebook summaries and total count
    """
    return notebooks.list_jupyter_notebooks(project_key, active)

@mcp.tool()
def get_jupyter_notebook(
    project_key: str,
    notebook_name: str,
    include_outputs: bool = True,
) -> Dict[str, Any]:
    """
    Get the full content of a Jupyter notebook.

    Args:
        project_key: The project key
        notebook_name: Name of the notebook
        include_outputs: Whether to include cell outputs

    Returns:
        Dict with raw notebook content
    """
    return notebooks.get_jupyter_notebook(project_key, notebook_name, include_outputs)

@mcp.tool()
def create_jupyter_notebook(
    project_key: str,
    notebook_name: str,
    notebook_content: Optional[Dict[str, Any]] = None,
    cells: Optional[List[Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a Jupyter notebook from raw notebook JSON or a list of cells.

    Args:
        project_key: The project key
        notebook_name: Name of the notebook to create
        notebook_content: Raw nbformat-compatible notebook content
        cells: Convenience list of code cells or raw cell dictionaries
        metadata: Optional notebook metadata when using cells

    Returns:
        Dict containing creation result
    """
    return notebooks.create_jupyter_notebook(
        project_key, notebook_name, notebook_content, cells, metadata
    )

@mcp.tool()
def update_jupyter_notebook(
    project_key: str,
    notebook_name: str,
    notebook_content: Optional[Dict[str, Any]] = None,
    cells: Optional[List[Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Replace the content of an existing Jupyter notebook.

    Args:
        project_key: The project key
        notebook_name: Name of the notebook to update
        notebook_content: Raw nbformat-compatible notebook content
        cells: Convenience list of code cells or raw cell dictionaries
        metadata: Optional notebook metadata when using cells

    Returns:
        Dict containing update result
    """
    return notebooks.update_jupyter_notebook(
        project_key, notebook_name, notebook_content, cells, metadata
    )

@mcp.tool()
def edit_jupyter_notebook_cells(
    project_key: str,
    notebook_name: str,
    operation: str,
    cells: Optional[List[Any]] = None,
    index: Optional[int] = None,
    count: int = 1,
) -> Dict[str, Any]:
    """
    Edit cells in an existing Jupyter notebook without recreating it.

    Args:
        project_key: The project key
        notebook_name: Name of the notebook to edit
        operation: One of append, insert, replace, or delete
        cells: Cells to append, insert, or replace; strings become code cells
        index: Zero-based cell index for insert, replace, or delete
        count: Number of cells to replace or delete

    Returns:
        Dict containing edit result
    """
    return notebooks.edit_jupyter_notebook_cells(
        project_key, notebook_name, operation, cells, index, count
    )

@mcp.tool()
def delete_jupyter_notebook(
    project_key: str,
    notebook_name: str,
) -> Dict[str, Any]:
    """
    Delete a Jupyter notebook and stop any active sessions.

    Args:
        project_key: The project key
        notebook_name: Name of the notebook to delete

    Returns:
        Dict containing deletion result
    """
    return notebooks.delete_jupyter_notebook(project_key, notebook_name)

@mcp.tool()
def clear_jupyter_notebook_outputs(
    project_key: str,
    notebook_name: str,
) -> Dict[str, Any]:
    """
    Clear outputs from a Jupyter notebook.

    Args:
        project_key: The project key
        notebook_name: Name of the notebook

    Returns:
        Dict containing clear result
    """
    return notebooks.clear_jupyter_notebook_outputs(project_key, notebook_name)

@mcp.tool()
def list_sql_notebooks(project_key: str) -> Dict[str, Any]:
    """
    List SQL notebooks in a Dataiku project.

    Args:
        project_key: The project key

    Returns:
        Dict with notebook summaries and total count
    """
    return notebooks.list_sql_notebooks(project_key)

@mcp.tool()
def get_sql_notebook(
    project_key: str,
    notebook_id: str,
    include_history: bool = False,
) -> Dict[str, Any]:
    """
    Get the content of a SQL notebook.

    Args:
        project_key: The project key
        notebook_id: ID of the SQL notebook
        include_history: Whether to include raw query run history

    Returns:
        Dict with raw notebook content
    """
    return notebooks.get_sql_notebook(project_key, notebook_id, include_history)

@mcp.tool()
def create_sql_notebook(
    project_key: str,
    notebook_content: Optional[Dict[str, Any]] = None,
    cells: Optional[List[Any]] = None,
    connection: Optional[str] = None,
    language: str = "SQL",
) -> Dict[str, Any]:
    """
    Create a SQL notebook from raw notebook JSON or query cells.

    Args:
        project_key: The project key
        notebook_content: Raw Dataiku SQL notebook content
        cells: Convenience list of SQL strings or raw cell dictionaries
        connection: Optional DSS connection name
        language: SQL dialect, such as SQL, HIVE, IMPALA, or SPARKSQL

    Returns:
        Dict containing creation result
    """
    return notebooks.create_sql_notebook(
        project_key, notebook_content, cells, connection, language
    )

@mcp.tool()
def update_sql_notebook(
    project_key: str,
    notebook_id: str,
    notebook_content: Optional[Dict[str, Any]] = None,
    cells: Optional[List[Any]] = None,
    connection: Optional[str] = None,
    language: str = "SQL",
) -> Dict[str, Any]:
    """
    Replace the content of an existing SQL notebook.

    Args:
        project_key: The project key
        notebook_id: ID of the SQL notebook
        notebook_content: Raw Dataiku SQL notebook content
        cells: Convenience list of SQL strings or raw cell dictionaries
        connection: Optional DSS connection name
        language: SQL dialect, such as SQL, HIVE, IMPALA, or SPARKSQL

    Returns:
        Dict containing update result
    """
    return notebooks.update_sql_notebook(
        project_key, notebook_id, notebook_content, cells, connection, language
    )

@mcp.tool()
def edit_sql_notebook_cells(
    project_key: str,
    notebook_id: str,
    operation: str,
    cells: Optional[List[Any]] = None,
    index: Optional[int] = None,
    count: int = 1,
) -> Dict[str, Any]:
    """
    Edit cells in an existing SQL notebook without recreating it.

    Args:
        project_key: The project key
        notebook_id: ID of the SQL notebook to edit
        operation: One of append, insert, replace, or delete
        cells: Cells to append, insert, or replace; strings become query cells
        index: Zero-based cell index for insert, replace, or delete
        count: Number of cells to replace or delete

    Returns:
        Dict containing edit result
    """
    return notebooks.edit_sql_notebook_cells(
        project_key, notebook_id, operation, cells, index, count
    )

@mcp.tool()
def delete_sql_notebook(
    project_key: str,
    notebook_id: str,
) -> Dict[str, Any]:
    """
    Delete a SQL notebook.

    Args:
        project_key: The project key
        notebook_id: ID of the SQL notebook

    Returns:
        Dict containing deletion result
    """
    return notebooks.delete_sql_notebook(project_key, notebook_id)

@mcp.tool()
def clear_sql_notebook_history(
    project_key: str,
    notebook_id: str,
    cell_id: Optional[str] = None,
    num_runs_to_retain: int = 0,
) -> Dict[str, Any]:
    """
    Clear SQL notebook query history.

    Args:
        project_key: The project key
        notebook_id: ID of the SQL notebook
        cell_id: Optional cell ID to clear; omit for all cells
        num_runs_to_retain: Number of recent runs to retain

    Returns:
        Dict containing clear result
    """
    return notebooks.clear_sql_notebook_history(
        project_key, notebook_id, cell_id, num_runs_to_retain
    )

# Add resource for listing projects
@mcp.resource("projects://")
def list_available_projects() -> str:
    """
    List all available Dataiku projects.
    
    Returns:
        JSON string of available projects
    """
    projects = list_projects()
    return json.dumps({"projects": projects})

# Add resource for project info
@mcp.resource("project://{project_key}")
def get_project_info(project_key: str) -> str:
    """
    Get information about a specific project.
    
    Args:
        project_key: The project key
        
    Returns:
        JSON string of project information
    """
    try:
        project = get_project(project_key)
        project_info = {
            "key": project_key,
            "name": project.get_metadata()["name"],
            "description": project.get_metadata().get("description", ""),
        }
        return json.dumps(project_info)
    except Exception as e:
        return json.dumps({"error": str(e)})

def create_server():
    """Create and configure the MCP server."""
    return mcp
