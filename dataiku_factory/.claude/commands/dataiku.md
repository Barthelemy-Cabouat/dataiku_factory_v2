# Dataiku DSS — Project Status

You are working with a Dataiku DSS instance (http://dssdesign.oneacrefund.org:10000) via the `dataiku_mcp` Python package in `C:\Users\barth\dataiku_factory`.

**Default projects to work on:**
- `OCR_PROJECT`
- `BURUNDI_BIZOPS`
- `BURUNDI_LOGISTICS`
- `BURUNDI_INPUT_RECONCILIATIONS`

If the user has passed arguments (`$ARGUMENTS`), check whether they name a specific project, action, or object to focus on. Otherwise run the full overview below.

---

## What to do

Run all steps using `python -c "..."` in `C:\Users\barth\dataiku_factory`.

### Step 1 — Verify connection

```python
import sys
sys.path.insert(0, '.')
from dataiku_mcp.client import reset_client, get_dss_version, list_projects
reset_client()
print("DSS version:", get_dss_version())
```

If the connection fails, report the error clearly and stop.

### Step 2 — For each of the four projects, collect:

```python
import sys, json
sys.path.insert(0, '.')
from dataiku_mcp.client import reset_client
from dataiku_mcp.tools.datasets import list_datasets
from dataiku_mcp.tools.recipes import list_recipes
from dataiku_mcp.tools.monitoring_debug import get_recent_runs, get_job_details

reset_client()

PROJECTS = ["OCR_PROJECT", "BURUNDI_BIZOPS", "BURUNDI_LOGISTICS", "BURUNDI_INPUT_RECONCILIATIONS"]

for pk in PROJECTS:
    print(f"\n{'='*60}")
    print(f"PROJECT: {pk}")
    print('='*60)

    # Datasets
    ds = list_datasets(pk)
    if ds.get("status") == "ok":
        print(f"  Datasets ({ds['total_count']}):")
        for d in ds["datasets"][:20]:
            print(f"    - {d['name']}  [{d['type']}]")
        if ds["total_count"] > 20:
            print(f"    ... and {ds['total_count'] - 20} more")
    else:
        print(f"  Datasets: ERROR — {ds.get('message')}")

    # Recipes
    rc = list_recipes(pk)
    if rc.get("status") == "ok":
        print(f"  Recipes ({rc['total_count']}):")
        for r in rc["recipes"][:20]:
            print(f"    - {r['name']}  [{r['type']}]")
        if rc["total_count"] > 20:
            print(f"    ... and {rc['total_count'] - 20} more")
    else:
        print(f"  Recipes: ERROR — {rc.get('message')}")

    # Recent jobs / logs
    jobs = get_recent_runs(pk, limit=5)
    if jobs.get("status") == "ok":
        print(f"  Recent jobs (last 5):")
        for j in jobs.get("runs", []):
            print(f"    - [{j.get('outcome','?')}] {j.get('name','?')}  started={j.get('startTime','?')}")
    else:
        print(f"  Jobs: ERROR — {jobs.get('message')}")
```

### Step 3 — Present results

After running the scripts, present a clean markdown summary for each project with:
- **Connection status** (version, host)
- **Datasets** — count + list of names and types
- **Recipes** — count + list of names and types
- **Recent jobs** — last 5 with status, name, and start time

Highlight any errors (project not found, permission denied, etc.) clearly.

If `$ARGUMENTS` names a specific action such as "list datasets for X", "show recipes in Y", or "check jobs in Z", focus only on that instead of the full overview.
