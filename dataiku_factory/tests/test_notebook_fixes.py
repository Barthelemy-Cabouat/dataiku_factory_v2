"""Offline tests for the get_sql_notebook history fix and kernel fallback."""
import sys, types
sys.path.insert(0, "dataiku_factory")

client_stub = types.ModuleType("dataiku_mcp.client")
client_stub.get_client = lambda: None
client_stub.get_project = lambda k: None
client_stub._get_normalized_host = lambda: "http://stub"
sys.modules["dataiku_mcp.client"] = client_stub

import importlib
notebooks = importlib.import_module("dataiku_mcp.tools.notebooks")
nbexec = importlib.import_module("dataiku_mcp.tools.notebook_execution")

FAILS = []
def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else f"  <- {extra}"))
    if not cond: FAILS.append(name)

# ---- history fix: real DSSNotebookHistory has .history, NOT .get_raw() ----
class RealisticHistory:
    """Mirrors dataikuapi DSSNotebookHistory: re-indexed dict, no get_raw()."""
    def __init__(self, wire):
        self.history = {cid: {qr["id"]: qr for qr in runs} for cid, runs in wire.items()}

class FakeContent:
    def __init__(self, c): self._c = c
    def get_raw(self): return self._c

class FakeNotebook:
    def __init__(self, content, history=None, raises=False):
        self._c, self._h, self._raises = content, history, raises
    def get_content(self): return FakeContent(self._c)
    def get_history(self):
        if self._raises: raise RuntimeError("history endpoint 500")
        return self._h

class FakeProject:
    def __init__(self, nb): self._nb = nb
    def get_sql_notebook(self, nid): return self._nb

CONTENT = {"connection": "Production", "cells": [{"id": "c1", "code": "SELECT 1"}]}
WIRE = {"c1": [{"id": "r1", "state": "DONE", "sql": "SELECT 1"},
               {"id": "r2", "state": "FAILED", "sql": "SELECT 2"}]}

# get_raw() would raise AttributeError -- the original bug
try:
    RealisticHistory(WIRE).get_raw()
    check("history object genuinely lacks get_raw", False, "stub is wrong")
except AttributeError:
    check("history object genuinely lacks get_raw (reproduces bug)", True)

notebooks.get_project = lambda k: FakeProject(FakeNotebook(CONTENT, RealisticHistory(WIRE)))
r = notebooks.get_sql_notebook("P", "NB1", include_history=True)
check("history call now succeeds", r["status"] == "ok", r)
check("history flattened to wire shape",
      r["history"] == WIRE, r.get("history"))
check("no history_error on success", "history_error" not in r, r)

# history failure must not sink the whole call
notebooks.get_project = lambda k: FakeProject(FakeNotebook(CONTENT, None, raises=True))
r = notebooks.get_sql_notebook("P", "NB1", include_history=True)
check("content still returned when history fails", r["status"] == "ok" and r["content"] == CONTENT, r)
check("history error reported", r["history"] is None and "500" in r["history_error"], r)

# include_history=False untouched
notebooks.get_project = lambda k: FakeProject(FakeNotebook(CONTENT, RealisticHistory(WIRE)))
r = notebooks.get_sql_notebook("P", "NB1", include_history=False)
check("no history key when not requested", "history" not in r, r)

# ---- kernelspec defaults + fallback ----
content = notebooks._jupyter_content(None, ["print(1)"], None, "python")
check("new notebooks default to python3",
      content["metadata"]["kernelspec"]["name"] == "python3", content["metadata"])
custom = notebooks._jupyter_content(
    None, ["print(1)"], {"kernelspec": {"name": "python_env_MYENV", "language": "python"}}, "python")
check("explicit kernelspec respected",
      custom["metadata"]["kernelspec"]["name"] == "python_env_MYENV", custom["metadata"])

check("prefers python3", nbexec._pick_fallback_kernel(["ir", "python_env_X", "python3"]) == "python3")
check("falls back to language match", nbexec._pick_fallback_kernel(["ir", "python_env_X"]) == "python_env_X")
check("falls back to first available", nbexec._pick_fallback_kernel(["ir", "julia"]) == "ir")
check("none when nothing available", nbexec._pick_fallback_kernel([]) is None)

class FakeResp:
    def __init__(self, code, payload=None): self.status_code, self._p = code, payload
    def json(self): return self._p
class FakeSession:
    def __init__(self, resp): self._r = resp
    def get(self, url, timeout=None): return self._r

payload = {"default": "python3", "kernelspecs": {"ir": {}, "python3": {}, "python_env_X": {}}}
names = nbexec._list_kernel_names(FakeSession(FakeResp(200, payload)), "http://h")
check("lists kernels with default first", names[0] == "python3" and set(names) == {"ir", "python3", "python_env_X"}, names)
check("http error yields empty list", nbexec._list_kernel_names(FakeSession(FakeResp(403)), "http://h") == [])

print()
print(f"{'ALL PASSED' if not FAILS else str(len(FAILS)) + ' FAILED: ' + ', '.join(FAILS)}")
sys.exit(1 if FAILS else 0)
