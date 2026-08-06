# Dataiku Factory - MCP Tool Suite

A comprehensive Model Context Protocol (MCP) tool suite for Dataiku DSS integration. It exposes **72 tools** covering recipes, datasets, scenarios, jobs, Jupyter and SQL notebooks, wiki articles, flow zones and discussions — usable from Claude Code, Codex, or as a **Local MCP tool inside Dataiku DSS itself**.

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Dataiku DSS instance with API access
- Valid DSS API key

### Installation

```bash
git clone <repository-url>
cd dataiku_factory

# Recommended
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e .

# Or use the helper script
./install.sh
```

This installs the `dataiku-mcp-server` console script into your environment's `bin/` (or `Scripts\` on Windows). That launcher is the supported entrypoint everywhere.

### Configuration

The server reads its connection settings from environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `DSS_HOST` | yes | DSS base URL, e.g. `https://dss.example.com:10000` |
| `DSS_API_KEY` | yes | DSS API key. Scope it to the projects the agent should reach |
| `DSS_INSECURE_TLS` | no | `true` to skip certificate verification (self-signed certs only) |

For local development, copy the template and edit it:

```bash
cp .env.sample .env
```

`client.py` loads `.env` from the package's parent directory, so this works from a source checkout. **In any deployed setup, pass the variables explicitly via the MCP client config instead** — once the package is pip-installed, the `.env` lookup resolves inside `site-packages` and will not find your file.

Verify the install:

```bash
dataiku-mcp-server --help
```

### CLI

```
dataiku-mcp-server [--transport stdio|sse] [--host HOST] [--port PORT] [--verbose]
```

`stdio` is the default and the only transport used by Claude Code, Codex and Dataiku. Log output always goes to **stderr** — stdout carries the JSON-RPC frames and must stay clean.

## 🔌 Client Integration

### Claude Code

```bash
claude mcp add dataiku-factory \
    -e DSS_HOST=https://your-dss-instance.com:10000 \
    -e DSS_API_KEY=your-api-key-here \
    -e DSS_INSECURE_TLS=true \
    -- /path/to/.venv/bin/dataiku-mcp-server
```

### Codex

```powershell
codex mcp add dataiku-factory `
  --env DSS_HOST=https://your-dss-instance.com:10000 `
  --env DSS_API_KEY=your-api-key-here `
  --env DSS_INSECURE_TLS=true `
  -- C:\path\to\dataiku_factory\.venv\Scripts\dataiku-mcp-server.exe `
     --transport stdio
```

Verify with `codex mcp list` / `codex mcp get dataiku-factory`.

### Dataiku DSS (Local MCP tool)

DSS 14+ can run this server as a managed **Local MCP** agent tool. Setup notes, in the order they bite:

**1. Create a dedicated code environment**, Python **3.11+**. `fastmcp`/`mcp` requires ≥3.10 and this package requires ≥3.11, so an existing 3.9 env will fail at package resolution.

**2. Install this package into that code env** rather than dropping the repo in the DSS project library. Add to the env's requested packages:

```
git+https://github.com/<org>/dataiku_factory_v2.git@<commit-sha>#subdirectory=dataiku_factory
```

Pin the SHA for anything beyond a design-node trial. Code envs resolve packages at **build time**, so tracking a branch means the server changes only when the env is rebuilt — silently, and without a signal that tool descriptors moved.

> **Why not the project library?** With User Isolation enabled, DSS code runs as `dssuser_*`, while `$DIP_HOME/config/` is mode `0700` owned by `dataiku`. The MCP subprocess cannot read the project library at all — you get `[Errno 13] Permission denied`.

**3. Configure the tool** (type: Local MCP):

```
command: /path/to/dss_data/code-envs/python/<env-name>/bin/dataiku-mcp-server
args:    (none)
env:     DSS_HOST=https://your-dss:10000
         DSS_API_KEY=<scoped key>
         DSS_INSECURE_TLS=false
```

**4. Use local (non-containerized) execution.** Absolute host paths do not resolve inside a DSS container image; a containerized tool reports `[Errno 2] No such file or directory` for a launcher that plainly exists on the host.

**5. Enable tools selectively.** All MCP tools are disabled by default in DSS. See the safety ratings in the catalog below, and wrap anything mutating in DSS's **Human approval**.

## 📚 MCP Tool Catalog

**72 tools.** Safety ratings: 🟢 read-only · 🟡 mutates metadata/objects · 🟠 executes code or consumes compute · 🔴 destructive.

### Orientation (3)

| Tool | Safety | Key Parameters |
|------|--------|----------------|
| `list_projects` | 🟢 | *(none)* |
| `list_concepts` | 🟢 | `topic` |
| `lookup_concept` | 🟢 | `query` |

These are the only three tools callable **without** a `project_key`, and that
matters more than it looks. The other 69 all require one and none of them can
produce one, so an agent that starts without a project key has no legal first
move. A Slack-hosted agent asked for "total credit in Burundi" guessed the key
`e2cf04` — a fragment of its own MCP namespace — then reported that it lacked
access, because a wrong key fails with exactly the error a missing permission
would produce.

`lookup_concept` resolves a business term to its agreed dataset, measure and
filter; see [Business glossary](#business-glossary) below.

### Recipes (7)

| Tool | Safety | Key Parameters |
|------|--------|----------------|
| `create_recipe` | 🟡 | `project_key`, `recipe_type`, `recipe_name`, `inputs`, `outputs`, `code` |
| `update_recipe` | 🟡 | `project_key`, `recipe_name`, `code`, `inputs`, `outputs`, `payload_json`, `engine_type`, … |
| `delete_recipe` | 🔴 | `project_key`, `recipe_name` |
| `run_recipe` | 🟠 | `project_key`, `recipe_name`, `build_mode` |
| `get_recipe_code` | 🟢 | `project_key`, `recipe_name` |
| `validate_recipe_syntax` | 🟢 | `project_key`, `recipe_name`, `code` |
| `test_recipe_dry_run` | 🟢 | `project_key`, `recipe_name`, `sample_rows` |

### Datasets (9)

| Tool | Safety | Key Parameters |
|------|--------|----------------|
| `create_dataset` | 🟡 | `project_key`, `dataset_name`, `dataset_type`, `params` |
| `update_dataset` | 🟡 | `project_key`, `dataset_name`, `kwargs` |
| `delete_dataset` | 🔴 | `project_key`, `dataset_name`, `drop_data` |
| `build_dataset` | 🟠 | `project_key`, `dataset_name`, `mode`, `partition` |
| `inspect_dataset_schema` | 🟢 | `project_key`, `dataset_name` |
| `resolve_dataset_sql_location` | 🟢 | `project_key`, `dataset_name` |
| `aggregate_dataset` | 🟢 | `project_key`, `dataset_name`, `aggregations`, `group_by`, `where`, `max_rows` |
| `check_dataset_metrics` | 🟢 | `project_key`, `dataset_name` |
| `get_dataset_sample` | 🟢 | `project_key`, `dataset_name`, `rows`, `columns`, `timeout`, `max_preview_rows` |

**Aggregates vs. samples.** `get_dataset_sample` reads only the leading rows;
its statistics describe that slice and not the dataset. On
`26B_Distribution_AppSheet_View`, a 1,000-row read reported 3.9% nulls in
`Credit_avec_CET` and a mean of 107,714, while a 5,000-row read of the same
column reported 21.1% and 112,526 — neither is the dataset's figure. Any total,
average or count must come from `aggregate_dataset`, which pushes the
computation into the database and runs it over every row.

`aggregate_dataset` composes SQL from an allowlist (`COUNT`, `COUNT_DISTINCT`,
`SUM`, `AVG`, `MIN`, `MAX`, `STDDEV`) and validates every column name against
the dataset's schema, so it is safe to enable for an agent that is *not*
permitted to run `execute_sql_query`. Its one raw-SQL surface is the optional
`where` argument, which is forwarded verbatim — leave it unused for untrusted
callers. Results always carry `total_row_count` and a `<column>__non_null_count`
for each aggregated column.

`resolve_dataset_sql_location` answers "which table is this actually?" — a DSS
dataset name is not the physical table name, and guessing produces
`relation "..." does not exist`. It expands `${projectKey}`-style variables and
quotes identifiers for the engine's dialect. The same information is now
returned in `inspect_dataset_schema` under `location`.

### Scenarios (9)

| Tool | Safety | Key Parameters |
|------|--------|----------------|
| `create_scenario` | 🟡 | `project_key`, `scenario_name`, `scenario_type`, `definition` |
| `update_scenario` | 🟡 | `project_key`, `scenario_id`, `kwargs` |
| `delete_scenario` | 🔴 | `project_key`, `scenario_id` |
| `run_scenario` | 🟠 | `project_key`, `scenario_id` |
| `clone_scenario` | 🟡 | `project_key`, `source_scenario_id`, `new_scenario_name`, `modifications` |
| `add_scenario_trigger` | 🟡 | `project_key`, `scenario_id`, `trigger_type`, `params` |
| `remove_scenario_trigger` | 🟡 | `project_key`, `scenario_id`, `trigger_idx` |
| `get_scenario_steps` | 🟢 | `project_key`, `scenario_id` |
| `get_scenario_logs` | 🟢 | `project_key`, `scenario_id`, `run_id` |

### Jobs & Monitoring (5)

| Tool | Safety | Key Parameters |
|------|--------|----------------|
| `get_recent_runs` | 🟢 | `project_key`, `limit`, `status_filter` |
| `get_job_details` | 🟢 | `project_key`, `job_id`, `log_lines`, `log_from_end` |
| `get_job_activities` | 🟢 | `project_key`, `job_id` |
| `get_job_log` | 🟢 | `project_key`, `job_id`, `lines`, `grep_pattern`, `severity`, `activity_id` |
| `cancel_running_jobs` | 🔴 | `project_key`, `job_ids` |

### Jupyter Notebooks (9)

| Tool | Safety | Key Parameters |
|------|--------|----------------|
| `list_jupyter_notebooks` | 🟢 | `project_key`, `active` |
| `get_jupyter_notebook` | 🟢 | `project_key`, `notebook_name`, `include_outputs` |
| `get_jupyter_notebook_outputs` | 🟢 | `project_key`, `notebook_name`, `max_output_chars` |
| `create_jupyter_notebook` | 🟡 | `project_key`, `notebook_name`, `notebook_content`, `cells`, `metadata` |
| `update_jupyter_notebook` | 🟡 | `project_key`, `notebook_name`, `notebook_content`, `cells`, `metadata` |
| `edit_jupyter_notebook_cells` | 🟡 | `project_key`, `notebook_name`, `operation`, `cells`, `index`, `count` |
| `clear_jupyter_notebook_outputs` | 🟡 | `project_key`, `notebook_name` |
| `delete_jupyter_notebook` | 🔴 | `project_key`, `notebook_name` |
| `run_jupyter_notebook` | 🟠 | `project_key`, `notebook_name`, `kernel_name`, `timeout_per_cell`, `stop_on_error`, `write_outputs` |

### SQL Notebooks & Queries (9)

| Tool | Safety | Key Parameters |
|------|--------|----------------|
| `list_sql_notebooks` | 🟢 | `project_key` |
| `get_sql_notebook` | 🟢 | `project_key`, `notebook_id`, `include_history` |
| `create_sql_notebook` | 🟡 | `project_key`, `notebook_content`, `cells`, `connection`, `language` |
| `update_sql_notebook` | 🟡 | `project_key`, `notebook_id`, `notebook_content`, `cells`, `connection`, `language` |
| `edit_sql_notebook_cells` | 🟡 | `project_key`, `notebook_id`, `operation`, `cells`, `index`, `count` |
| `clear_sql_notebook_history` | 🟡 | `project_key`, `notebook_id`, `cell_id`, `num_runs_to_retain` |
| `delete_sql_notebook` | 🔴 | `project_key`, `notebook_id` |
| `execute_sql_notebook` | 🟠 | `project_key`, `notebook_id`, `cell_index`, `connection`, `max_rows`, `stop_on_error` |
| `execute_sql_query` | 🟠 | `connection`, `query`, `project_key`, `max_rows`, `query_type`, `max_output_chars` |

> `execute_sql_query` runs arbitrary SQL against a DSS connection. Treat it as the highest-risk tool in the suite — it inherits whatever the connection's credentials permit, including DDL and DML.

### Wiki (4)

| Tool | Safety | Key Parameters |
|------|--------|----------------|
| `list_wiki_articles` | 🟢 | `project_key` |
| `get_wiki_article` | 🟢 | `project_key`, `article_id` |
| `create_wiki_article` | 🟡 | `project_key`, `article_name`, `body`, `parent_id` |
| `update_wiki_article` | 🟡 | `project_key`, `article_id`, `body`, `article_name` |

### Flow Zones (5)

| Tool | Safety | Key Parameters |
|------|--------|----------------|
| `list_zones` | 🟢 | `project_key` |
| `get_zone_of_object` | 🟢 | `project_key`, `object_name`, `object_type` |
| `create_zone` | 🟡 | `project_key`, `zone_name`, `color` |
| `move_to_zone` | 🟡 | `project_key`, `zone`, `items` |
| `delete_zone` | 🔴 | `project_key`, `zone` |

### Discussions (4)

| Tool | Safety | Key Parameters |
|------|--------|----------------|
| `list_object_discussions` | 🟢 | `project_key`, `object_type`, `object_id` |
| `get_object_discussion` | 🟢 | `project_key`, `object_type`, `object_id`, `discussion_id` |
| `create_object_discussion` | 🟡 | `project_key`, `object_type`, `object_id`, `topic`, `message` |
| `reply_to_object_discussion` | 🟡 | `project_key`, `object_type`, `object_id`, `discussion_id`, `message` |

### Project Exploration & Configuration (5)

| Tool | Safety | Key Parameters |
|------|--------|----------------|
| `get_project_flow` | 🟢 | `project_key` |
| `search_project_objects` | 🟢 | `project_key`, `search_term`, `object_types` |
| `get_project_variables` | 🟢 | `project_key` |
| `get_connections` | 🟢 | `project_key`, `scope`, `include_usage` |
| `get_code_environments` | 🟢 | `project_key`, `scope` |

**Payload note.** `get_connections` returns per-connection dataset and recipe
*counts* by default; the full name-by-name inventory arrives only with
`include_usage=true`. On BURUNDI_BIZOPS (1,065 datasets, 975 recipes) that
inventory is roughly 50k tokens, and because an agent framework replays the full
message history on every iteration, a single call re-bills itself on every
subsequent turn.

### Productivity (3)

| Tool | Safety | Key Parameters |
|------|--------|----------------|
| `export_project_config` | 🟢 | `project_key`, `format` |
| `duplicate_project_structure` | 🟡 | `source_project_key`, `target_project_key`, `include_data` |
| `batch_update_objects` | 🔴 | `project_key`, `object_type`, `pattern`, `updates` |

### Resources

| Resource URI | Description |
|--------------|-------------|
| `projects://` | List all available Dataiku projects |
| `project://{project_key}` | Metadata for a specific project |

### Suggested read-only starting set

When first wiring this into an agent, enable only:

```
list_projects, list_concepts, lookup_concept,
get_project_flow, search_project_objects, inspect_dataset_schema,
resolve_dataset_sql_location, aggregate_dataset, get_dataset_sample,
get_recipe_code, get_scenario_steps, get_scenario_logs,
get_recent_runs, get_job_details, get_job_log, get_connections,
get_code_environments, list_wiki_articles, get_wiki_article
```

Enable `list_projects` first. Without it the agent's very first tool call is a
guess, and every downstream failure is misattributed to permissions.

`aggregate_dataset` belongs in this set even though it reaches the database:
without it an agent asked for a total has only `get_dataset_sample`, and will
answer confidently and wrongly. It is the safe way to say yes to that question.

## 🔧 Usage Examples

#### Creating a Python recipe

```python
create_recipe(
    project_key="ANALYTICS_PROJECT",
    recipe_type="python",
    recipe_name="data_cleaner",
    inputs=["raw_data"],
    outputs=[{"name": "clean_data", "new": True, "connection": "filesystem_managed"}],
    code="""
import dataiku
df = dataiku.Dataset("raw_data").get_dataframe()
dataiku.Dataset("clean_data").write_with_schema(df.dropna())
""",
)
```

#### Diagnosing a failed pipeline

```python
get_recent_runs(project_key="DATA_PIPELINE", limit=20, status_filter="FAILED")
get_job_details(project_key="DATA_PIPELINE", job_id="job_12345")
get_job_log(project_key="DATA_PIPELINE", job_id="job_12345",
            severity="ERROR", lines=200, from_end=True)
```

#### Exploring a project

```python
get_project_flow(project_key="SALES_ANALYTICS")
search_project_objects(project_key="SALES_ANALYTICS", search_term="customer",
                       object_types=["datasets", "recipes", "scenarios"])
get_dataset_sample(project_key="FINANCE_PROJECT", dataset_name="transactions",
                   rows=500, columns=["customer_id", "amount"])
```

#### Running an ad-hoc query

```python
execute_sql_query(connection="snowflake_prod",
                  query="SELECT COUNT(*) FROM analytics.public.orders",
                  max_rows=100)
```

#### Working with notebooks

```python
list_jupyter_notebooks(project_key="ML_PROJECT", active=True)
run_jupyter_notebook(project_key="ML_PROJECT", notebook_name="feature_eng",
                     stop_on_error=True, write_outputs=True)
get_jupyter_notebook_outputs(project_key="ML_PROJECT", notebook_name="feature_eng")
```

## 🏗️ Architecture

```
dataiku_factory/
├── dataiku_mcp/
│   ├── __init__.py
│   ├── cli.py             # Console-script entrypoint (dataiku-mcp-server)
│   ├── client.py          # DSS client wrapper
│   ├── server.py          # FastMCP server + tool registration
│   └── tools/
│       ├── api_helpers.py          # Shared REST helpers
│       ├── recipes.py              # Recipe management
│       ├── datasets.py             # Dataset management
│       ├── scenarios.py            # Scenario management
│       ├── advanced_scenarios.py   # Logs, steps, cloning
│       ├── code_development.py     # Code extraction & validation
│       ├── project_exploration.py  # Flow, search, samples
│       ├── environment_config.py   # Connections, code envs, variables
│       ├── monitoring_debug.py     # Jobs, runs, logs
│       ├── productivity.py         # Duplication, export, batch updates
│       ├── notebooks.py            # Jupyter notebook CRUD
│       ├── notebook_execution.py   # Jupyter execution & outputs
│       ├── sql_execution.py        # SQL notebooks & ad-hoc queries
│       ├── wiki.py                 # Wiki articles
│       ├── flow_zones.py           # Flow zones
│       └── discussions.py          # Object discussions
├── scripts/
│   └── mcp_server.py      # Dev-only shim -> dataiku_mcp.cli
├── tests/
├── install.sh
├── setup.ps1
├── pyproject.toml
└── .env.sample
```

### Note on packaging

The console script points at `dataiku_mcp.cli:main`, **not** `scripts.mcp_server:main`. setuptools' flat-layout auto-discovery excludes top-level `scripts/`, `tests/`, `docs/`, `tools/`, `bin/` and `examples/` directories by default, so a `scripts`-based entrypoint installs a launcher that immediately dies with `ModuleNotFoundError: No module named 'scripts'`. `pyproject.toml` now declares package discovery explicitly:

```toml
[tool.setuptools.packages.find]
include = ["dataiku_mcp*"]
namespaces = false
```

`scripts/mcp_server.py` is retained purely so `python scripts/mcp_server.py` still works from a source checkout.

### Note on dependency pinning

`mcp` is pinned to `>=1.2,<2`. Version 2.0 removed `mcp.server.fastmcp`, which `server.py` imports; an unpinned install will break at import once 2.x is resolved.

## 🔒 Security

- **The API key is the real permission boundary.** All tools act with the privileges of `DSS_API_KEY`, regardless of which user is talking to the agent. Scope keys per project; never use an admin key.
- **Destructive tools ship enabled at the protocol level.** `delete_*`, `batch_update_objects` and `cancel_running_jobs` do what they say. Disable them in your MCP client and gate them behind human approval where the client supports it.
- **`execute_sql_query` is unrestricted SQL.** Point it at read-only connections, or leave it disabled.
- **Prompt injection reaches these tools.** Any untrusted text an agent reads — dataset descriptions, wiki bodies, discussion threads — can attempt to steer a tool call. Read-only tool sets are the reliable mitigation.
- **TLS**: `DSS_INSECURE_TLS=true` disables certificate verification. Development only.
- **Secrets**: keep `.env` out of version control (it is gitignored) and prefer explicit env vars in client configs.

## 📈 Logging

Logs are written to **stderr** at INFO by default, DEBUG with `--verbose`:

```bash
dataiku-mcp-server --verbose
```

This is deliberate: the stdio transport reserves stdout for JSON-RPC frames. Any `print()` or stdout log handler added to this codebase will corrupt the protocol stream and clients will report an opaque "Connection closed".

## 🐛 Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `No matching distribution found for fastmcp` / `mcp` | Code env is Python 3.9 | Create a new env on Python 3.11+; the version can't be changed in place |
| `ModuleNotFoundError: No module named 'scripts'` | Old entrypoint against an unpackaged directory | Reinstall; the entrypoint is now `dataiku_mcp.cli:main` |
| `[Errno 13] Permission denied` on a project-library path | User Isolation — `$DIP_HOME/config` is `0700`, owned by `dataiku` | Install the package into the code env instead of reading the DSS project library |
| `[Errno 2] No such file or directory` for a launcher that exists | Tool is running containerized; host paths don't resolve in the image | Switch to local execution, or use the in-container code env path |
| `No recorded image tag for env PYTHON <env>` | Code env flagged for containerized execution, image never built | Build the container image, or disable containerized execution |
| "Connection closed" right after start | Process crashed, or stdout polluted | Run the launcher manually and read stderr; check for `print()` / stdout handlers |
| Connection refused | Wrong `DSS_HOST`, or DSS not reachable | Verify URL and port, and network egress from the host |
| SSL certificate errors | Self-signed cert | `DSS_INSECURE_TLS=true` (development only) |
| Permission denied from DSS API | API key lacks project rights | Grant the key access, or scope the request to permitted projects |

### Manual smoke test

Confirms both that the process starts and that stdout is a clean JSON-RPC stream:

```python
import subprocess, json, threading, queue

p = subprocess.Popen(["dataiku-mcp-server"], stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                     text=True, bufsize=1)
q = queue.Queue()
threading.Thread(target=lambda: [q.put(l) for l in p.stdout], daemon=True).start()
send = lambda o: (p.stdin.write(json.dumps(o) + "\n"), p.stdin.flush())

send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2024-11-05", "capabilities": {},
    "clientInfo": {"name": "probe", "version": "0"}}})
print(json.loads(q.get(timeout=20))["result"]["serverInfo"])

send({"jsonrpc": "2.0", "method": "notifications/initialized"})
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
print(len(json.loads(q.get(timeout=30))["result"]["tools"]), "tools")
p.terminate()
```

Expected: a `serverInfo` dict, then `72 tools`.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

### Development Setup

```bash
pip install -e .[dev]

black dataiku_mcp/ scripts/
ruff check dataiku_mcp/ scripts/
pytest
```

New tools are registered with `@mcp.tool()` in `dataiku_mcp/server.py` and implemented in a module under `dataiku_mcp/tools/`. Keep the docstring accurate — MCP clients surface it verbatim, and it is what the model uses to decide when to call the tool.

## 📝 API Reference

### Supported Recipe Types

- **Code recipes**: `python`, `r`, `sql`, `pyspark`, `scala`, `shell`
- **Visual recipes**: `grouping`, `join`, `sync`, `split`, `distinct`, `sort`, `topn`

### Supported Dataset Types

- **Managed datasets**: `managed` (default filesystem storage)
- **Filesystem datasets**: `filesystem` (custom paths)
- **SQL datasets**: `sql` (database tables)
- **Cloud datasets**: `s3`, `gcs`, `azure`
- **Upload datasets**: `uploaded` (CSV uploads)

### Supported Scenario Types

- **Step-based scenarios**: `step_based` (visual workflow)
- **Custom Python scenarios**: `custom_python` (Python code)

### Trigger Types

- **Periodic**: `periodic` (every X minutes)
- **Hourly**: `hourly` (specific minutes past hour)
- **Daily**: `daily` (specific time daily)
- **Monthly**: `monthly` (specific day/time monthly)
- **Dataset**: `dataset` (on dataset changes)

## 📄 License

MIT — see the LICENSE file.

## 🙏 Acknowledgments

- Built for [Dataiku DSS](https://www.dataiku.com/)
- Uses the [Model Context Protocol](https://modelcontextprotocol.io/)
- Integrated with [Claude Code](https://claude.ai/code)
