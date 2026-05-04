# Dataiku Factory

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that gives AI coding assistants direct access to [Dataiku DSS](https://www.dataiku.com/). It exposes 34 tools covering recipes, datasets, scenarios, project exploration, monitoring, and more — letting you manage Dataiku workflows through natural language in your AI assistant.

## Repository structure

```
dataiku_factory_v2/
├── dataiku_factory/          # MCP server for Claude Code
└── dataiku-copilot-skill/    # MCP server variant for GitHub Copilot Chat
```

Both folders contain the same MCP implementation. `dataiku-copilot-skill` was adapted for the GitHub Copilot Chat extension format; `dataiku_factory` is the canonical version kept in sync from it.

## Prerequisites

- Python 3.11+
- A running Dataiku DSS instance (tested on DSS 14.x)
- A DSS API key with access to the relevant projects

## Setup

```bash
cd dataiku_factory

# Install dependencies
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -e .

# Configure connection
cp .env.sample .env
```

Edit `.env`:

```env
DSS_HOST=http://your-dss-instance:10000
DSS_API_KEY=your-api-key-here
DSS_INSECURE_TLS=true   # set to true for self-signed certificates
```

Test the connection:

```bash
python -c "
import sys; sys.path.insert(0, '.')
from dataiku_mcp.client import get_dss_version, list_projects
print('DSS version:', get_dss_version())
print('Projects accessible:', len(list_projects()))
"
```

## Claude Code integration

Register the MCP server with Claude Code:

```bash
claude mcp add dataiku-factory \
    -e DSS_HOST=http://your-dss-instance:10000 \
    -e DSS_API_KEY=your-api-key-here \
    -e DSS_INSECURE_TLS=true \
    -- python scripts/mcp_server.py
```

Once registered, Claude Code can manage your Dataiku projects directly from the chat. For example:

> *"Get the flow for project SALES_ANALYTICS and show me all datasets containing 'customer'"*

> *"Extract the code from recipe compute_kpis, fix the bug on line 42, and update it"*

> *"Show me the logs for the last failed run of scenario daily_etl"*

## Available tools

| Category | Tools |
|---|---|
| Recipes | `create_recipe`, `update_recipe`, `delete_recipe`, `run_recipe` |
| Datasets | `create_dataset`, `update_dataset`, `delete_dataset`, `build_dataset`, `inspect_dataset_schema`, `check_dataset_metrics` |
| Scenarios | `create_scenario`, `update_scenario`, `delete_scenario`, `add_scenario_trigger`, `remove_scenario_trigger`, `run_scenario` |
| Advanced scenarios | `get_scenario_logs`, `get_scenario_steps`, `clone_scenario` |
| Code development | `get_recipe_code`, `validate_recipe_syntax`, `test_recipe_dry_run` |
| Project exploration | `get_project_flow`, `search_project_objects`, `get_dataset_sample` |
| Environment & config | `get_code_environments`, `get_project_variables`, `get_connections` |
| Monitoring & debug | `get_recent_runs`, `get_job_details`, `cancel_running_jobs` |
| Productivity | `duplicate_project_structure`, `export_project_config`, `batch_update_objects` |

See [`dataiku_factory/README.md`](dataiku_factory/README.md) for full parameter documentation and usage examples for each tool.

## Security

- Store credentials in `.env` or pass them as environment variables — never commit them
- `.env` is listed in `.gitignore`
- All operations respect the DSS permissions of the configured API key
