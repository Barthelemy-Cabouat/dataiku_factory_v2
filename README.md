# Dataiku Factory

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that gives AI coding assistants direct access to [Dataiku DSS](https://www.dataiku.com/). It exposes tools for recipes, datasets, scenarios, project exploration, monitoring, notebooks, and wiki workflows so you can manage Dataiku through natural language.

## Repository Structure

```text
dataiku_factory_v2/
|- dataiku_factory/          # Canonical MCP server for Claude Code, Codex, and VS Code
`- dataiku-copilot-skill/    # Older wrapper kept only for reference
```

Use `dataiku_factory` as the source of truth. `dataiku-copilot-skill` is an older wrapper and may drift out of date.

## Prerequisites

- Python 3.11+
- A running Dataiku DSS instance
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
DSS_INSECURE_TLS=true
```

Test the entrypoint:

```bash
python scripts/mcp_server.py --help
```

## Claude Code Integration

```bash
claude mcp add dataiku-factory \
    -e DSS_HOST=http://your-dss-instance:10000 \
    -e DSS_API_KEY=your-api-key-here \
    -e DSS_INSECURE_TLS=true \
    -- python scripts/mcp_server.py
```

## Codex Integration

Codex can register the same stdio server directly. On Windows:

```powershell
codex mcp add dataiku-factory -- `
  C:\Users\Bart\Documents\GitHub\dataiku_factory_v2\dataiku_factory\.venv\Scripts\python.exe `
  C:\Users\Bart\Documents\GitHub\dataiku_factory_v2\dataiku_factory\scripts\mcp_server.py `
  --transport stdio
```

If you prefer not to rely on the local `.env` file, pass the DSS settings explicitly:

```powershell
codex mcp add dataiku-factory `
  --env DSS_HOST=http://your-dss-instance:10000 `
  --env DSS_API_KEY=your-api-key-here `
  --env DSS_INSECURE_TLS=true `
  -- C:\Users\Bart\Documents\GitHub\dataiku_factory_v2\dataiku_factory\.venv\Scripts\python.exe `
     C:\Users\Bart\Documents\GitHub\dataiku_factory_v2\dataiku_factory\scripts\mcp_server.py `
     --transport stdio
```

Verify the registration:

```powershell
codex mcp list
codex mcp get dataiku-factory
```

## Available Tools

The canonical server in `dataiku_factory` currently registers tool groups for:

- Recipes
- Datasets
- Scenarios
- Advanced scenarios
- Code development
- Project exploration
- Environment and configuration
- Monitoring and debugging
- Productivity
- Wiki
- Jupyter notebooks
- SQL notebooks

See [dataiku_factory/README.md](dataiku_factory/README.md) for the detailed catalog and examples.

## Security

- Store credentials in `.env` or pass them as environment variables; never commit them.
- All operations respect the DSS permissions of the configured API key.
- Prefer the canonical `dataiku_factory` config path so dependency drift stays in one place.
