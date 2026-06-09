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
