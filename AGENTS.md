# Codex Instructions

## Temporary Scripts

Always write one-off or throwaway Python/shell scripts to `tmp/` at the repo root (e.g. `tmp/explore.py`). This folder is gitignored. Delete the file when done; if multiple temp files accumulate, clean the whole folder.

## DSS Connection

The `.env` file is at `dataiku_factory/.env` (not the repo root). Always load it with:

```python
load_dotenv(dotenv_path='dataiku_factory/.env')
```

## Python Path

Always add `dataiku_factory` to `sys.path` before importing project modules:

```python
sys.path.insert(0, 'dataiku_factory')
```

## Deployed agents

Agent and MCP-tool IDs, the consumer graph, and the invariants that are easy to
relearn the hard way live in `dataiku_factory/DEPLOYED_AGENTS.md`. Read it
before touching anything in DSS project `DATAIKU_MAINTENANCE`.

Two that bite immediately:

- `subtool_count` on the MCP tool is the only reliable signal of which toolset
  is live (`minimal` = 14, `readonly` = 43, `full` = 83). Env vars, installed
  commit and token counts have each been misleading.
- `DATAIKU_MCP_TOOLSET` goes on the **tool's** env list, not the project
  variables — the latter never reaches `os.environ`.
