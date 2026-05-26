# Dataiku DSS – GitHub Copilot Instructions

You are connected to a live **Dataiku DSS** instance via the `dataiku-factory` MCP server.
Use the tools below to manage Dataiku objects directly. Always confirm destructive actions
(delete, drop_data, cancel) with the user before executing them.

---

## Available MCP Tools (34 total)

### Recipe Management
| Tool | Purpose | Required args |
|------|---------|---------------|
| `create_recipe` | Create a new recipe | `project_key`, `recipe_type`, `recipe_name`, `inputs`, `outputs` |
| `update_recipe` | Update recipe settings | `project_key`, `recipe_name` |
| `delete_recipe` | **Destructive** – delete a recipe | `project_key`, `recipe_name` |
| `run_recipe` | Execute a recipe | `project_key`, `recipe_name` |
| `get_recipe_code` | Extract Python/SQL source | `project_key`, `recipe_name` |
| `validate_recipe_syntax` | Lint code before running | `project_key`, `recipe_name` |
| `test_recipe_dry_run` | Test without writing data | `project_key`, `recipe_name` |

### Dataset Management
| Tool | Purpose | Required args |
|------|---------|---------------|
| `create_dataset` | Create a new dataset | `project_key`, `dataset_name`, `dataset_type`, `params` |
| `update_dataset` | Update dataset settings | `project_key`, `dataset_name` |
| `delete_dataset` | **Destructive** – delete dataset | `project_key`, `dataset_name` |
| `build_dataset` | Build / refresh dataset | `project_key`, `dataset_name` |
| `inspect_dataset_schema` | Get column schema | `project_key`, `dataset_name` |
| `check_dataset_metrics` | Get row counts / metrics | `project_key`, `dataset_name` |
| `get_dataset_sample` | Preview data rows | `project_key`, `dataset_name` |

### Scenario Management
| Tool | Purpose | Required args |
|------|---------|---------------|
| `create_scenario` | Create scenario | `project_key`, `scenario_name`, `scenario_type` |
| `update_scenario` | Update scenario | `project_key`, `scenario_id` |
| `delete_scenario` | **Destructive** – delete scenario | `project_key`, `scenario_id` |
| `run_scenario` | Execute scenario manually | `project_key`, `scenario_id` |
| `add_scenario_trigger` | Add scheduled / dataset trigger | `project_key`, `scenario_id`, `trigger_type` |
| `remove_scenario_trigger` | Remove a trigger | `project_key`, `scenario_id`, `trigger_idx` |
| `get_scenario_logs` | Get run logs & errors | `project_key`, `scenario_id` |
| `get_scenario_steps` | Inspect step config/code | `project_key`, `scenario_id` |
| `clone_scenario` | Copy scenario with changes | `project_key`, `source_scenario_id`, `new_scenario_name` |

### Project Exploration
| Tool | Purpose | Required args |
|------|---------|---------------|
| `get_project_flow` | Full DAG of datasets & recipes | `project_key` |
| `search_project_objects` | Search by name pattern | `project_key`, `search_term` |

### Environment & Configuration
| Tool | Purpose | Required args |
|------|---------|---------------|
| `get_code_environments` | List Python/R envs | — |
| `get_project_variables` | Get project variables | `project_key` |
| `get_connections` | List data connections | — |

### Monitoring & Debugging
| Tool | Purpose | Required args |
|------|---------|---------------|
| `get_recent_runs` | Run history | `project_key` |
| `get_job_details` | Single job details | `project_key`, `job_id` |
| `cancel_running_jobs` | **Destructive** – cancel jobs | `project_key`, `job_ids` |

### Productivity
| Tool | Purpose | Required args |
|------|---------|---------------|
| `duplicate_project_structure` | Copy project skeleton | `source_project_key`, `target_project_key` |
| `export_project_config` | Export config as JSON/YAML | `project_key` |
| `batch_update_objects` | Bulk-update by pattern | `project_key`, `object_type`, `pattern`, `updates` |

---

## Coding Conventions

- **Python recipes** use `dataiku.Dataset("name").get_dataframe()` to read and
  `dataiku.Dataset("name").write_with_schema(df)` to write.
- **project_key** values are UPPER_CASE (e.g., `ANALYTICS_PROJECT`, `SALES_BI`).
- Prefer `RECURSIVE_BUILD` as the default `mode` for `build_dataset`.
- Always call `inspect_dataset_schema` before writing code that references specific columns.
- Call `validate_recipe_syntax` before `run_recipe` on new or heavily modified recipes.
- When the user asks to "explore" or "understand" a project, start with `get_project_flow`
  then `search_project_objects`.

## Safety Rules

1. Never call `delete_recipe`, `delete_dataset`, `delete_scenario`, or `cancel_running_jobs`
   without explicit user confirmation.
2. Never set `drop_data=True` in `delete_dataset` unless the user specifically asks to
   remove the underlying data.
3. When a scenario run fails, retrieve `get_scenario_logs` before suggesting fixes.

## Supported Recipe Types
`python` · `r` · `sql` · `pyspark` · `scala` · `shell` · `grouping` · `join` · `sync` · `split` · `distinct` · `sort` · `topn`

## Supported Trigger Types
`periodic` · `hourly` · `daily` · `monthly` · `dataset`
