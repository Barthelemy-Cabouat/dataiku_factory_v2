"""Offline unit tests for sql_execution: stubs the DSS client entirely."""
import sys, types

sys.path.insert(0, "dataiku_factory")
sys.path.insert(0, "dataiku_factory/.venv/Lib/site-packages")

# Stub dataiku_mcp.client so no real DSS connection or dataikuapi is needed
client_stub = types.ModuleType("dataiku_mcp.client")
client_stub.get_client = lambda: None
client_stub.get_project = lambda k: None
client_stub._get_normalized_host = lambda: "http://stub"
sys.modules["dataiku_mcp.client"] = client_stub

import importlib
sql_execution = importlib.import_module("dataiku_mcp.tools.sql_execution")

FAILS = []
def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else f"  <- {extra}"))
    if not cond: FAILS.append(name)

# ---- pure helpers -------------------------------------------------------
check("comment-only cell not runnable",
      sql_execution._is_runnable("-- just a note\n\n-- another") is False)
check("real sql is runnable", sql_execution._is_runnable("-- note\nSELECT 1") is True)
check("blank not runnable", sql_execution._is_runnable("   \n\t\n") is False)
check("strips trailing semicolons",
      sql_execution._strip_trailing_semicolon("SELECT 1 ;; \n") == "SELECT 1")
check("keeps inner semicolons",
      sql_execution._strip_trailing_semicolon("SELECT 'a;b';") == "SELECT 'a;b'")
check("cell code from list joins",
      sql_execution._cell_code({"code": ["SELECT 1", "FROM t"]}) == "SELECT 1\nFROM t")

tbl = sql_execution._render_table(["A", "B"], [[1, None], ["xx", "y"]], 8000)
check("render has header and rows", "A" in tbl and "xx" in tbl and len(tbl.splitlines()) == 4, tbl)
check("render handles None as blank", "None" not in tbl, tbl)

# ---- fake DSS query runner ---------------------------------------------
class FakeQuery:
    def __init__(self, cols, rows, fail_verify=False, schema_shape="dict"):
        self._cols, self._rows, self._fail = cols, rows, fail_verify
        self._shape = schema_shape
        self.verified = False
    def get_schema(self):
        cols = [{"name": c, "type": "string", "originalType": "TEXT"} for c in self._cols]
        # DSS is observed returning a bare list; the docstring says dict.
        return cols if self._shape == "list" else {"columns": cols}
    def iter_rows(self):
        for r in self._rows: yield r
    def verify(self):
        if self._fail: raise RuntimeError("boom")
        self.verified = True

class FakeClient:
    def __init__(self, cols, rows, fail_verify=False, schema_shape="dict"):
        self.calls = []
        self._q = FakeQuery(cols, rows, fail_verify, schema_shape)
    def sql_query(self, query, connection=None, type=None, project_key=None):
        self.calls.append({"query": query, "connection": connection,
                           "type": type, "project_key": project_key})
        return self._q

def use(client): sql_execution.get_client = lambda: client

# ad-hoc query, happy path
fc = FakeClient(["ID", "NAME"], [[1, "a"], [2, "b"]]); use(fc)
r = sql_execution.execute_sql_query("Production", "SELECT * FROM t;", max_rows=10)
check("query ok", r["status"] == "ok", r)
check("query columns", r["columns"] == ["ID", "NAME"], r)
check("query rows", r["row_count"] == 2 and r["truncated"] is False, r)
check("query verified", r["verified"] is True, r)
check("semicolon stripped before send", fc.calls[0]["query"] == "SELECT * FROM t", fc.calls)
check("connection passed through", fc.calls[0]["connection"] == "Production", fc.calls)

# truncation path
fc = FakeClient(["ID"], [[i] for i in range(50)]); use(fc)
r = sql_execution.execute_sql_query("Production", "SELECT 1", max_rows=5)
check("truncates at max_rows", r["row_count"] == 5 and r["truncated"] is True, r)
check("skips verify when truncated",
      r["verified"] is False and "truncated" in (r["verify_warning"] or ""), r)

# verify failure is surfaced, not raised
fc = FakeClient(["ID"], [[1]], fail_verify=True); use(fc)
r = sql_execution.execute_sql_query("Production", "SELECT 1")
check("verify failure surfaced", r["status"] == "ok" and "boom" in (r["verify_warning"] or ""), r)

# empty query rejected
r = sql_execution.execute_sql_query("Production", "-- nothing here")
check("comment-only query rejected", r["status"] == "error", r)

# driver error becomes error dict, not exception
class Boom(FakeClient):
    def sql_query(self, **kw): raise RuntimeError("SQL compilation error")
    def sql_query(self, query, connection=None, type=None, project_key=None):
        raise RuntimeError("SQL compilation error")
use(Boom([], []))
r = sql_execution.execute_sql_query("Production", "SELECT bad")
check("driver error handled", r["status"] == "error" and "compilation" in r["message"], r)

# ---- schema shape tolerance (regression: live DSS returns a bare list) ----
for shape in ("dict", "list"):
    fc = FakeClient(["ID", "NAME"], [[1, "a"]], schema_shape=shape); use(fc)
    r = sql_execution.execute_sql_query("Production", "SELECT 1")
    check(f"schema as {shape}: columns parsed",
          r["columns"] == ["ID", "NAME"], r)
    check(f"schema as {shape}: types parsed",
          r["column_types"] == {"ID": "TEXT", "NAME": "TEXT"}, r)
    check(f"schema as {shape}: preview non-empty", bool(r["preview"]), r)

check("malformed schema degrades to no columns",
      sql_execution._schema_columns(None) == [] and sql_execution._schema_columns("x") == [])


# ---- notebook execution -------------------------------------------------
NB = {
    "connection": "Production", "language": "SQL",
    "cells": [
        {"id": "c1", "type": "QUERY", "name": "Q1", "code": "SELECT 1"},
        {"id": "c2", "type": "QUERY", "name": "Q2", "code": "-- only a comment"},
        {"id": "c3", "type": "MARKDOWN", "name": "M", "code": "# notes"},
        {"id": "c4", "type": "QUERY", "name": "Q3", "code": "SELECT 2;"},
    ],
}
class FakeContent:
    def __init__(self, c): self._c = c
    def get_raw(self): return self._c
class FakeNotebook:
    def __init__(self, c): self._c = c
    def get_content(self): return FakeContent(self._c)
class FakeProject:
    def __init__(self, c): self._c = c
    def get_sql_notebook(self, nid): return FakeNotebook(self._c)

def use_nb(nb, client):
    sql_execution.get_project = lambda k: FakeProject(nb)
    sql_execution.get_client = lambda: client

fc = FakeClient(["N"], [[1]]); use_nb(NB, fc)
r = sql_execution.execute_sql_notebook("P", "NB1")
by_id = {x["cell_id"]: x for x in r["results"]}
check("notebook ok", r["status"] == "ok", r)
check("ran 2 query cells", r["cells_executed"] == 2, r)
check("comment cell skipped", by_id["c2"]["status"] == "skipped", by_id["c2"])
check("markdown cell skipped", by_id["c3"]["status"] == "skipped", by_id["c3"])
check("uses notebook connection", fc.calls[0]["connection"] == "Production", fc.calls)
check("maps SQL -> sql type", fc.calls[0]["type"] == "sql", fc.calls)

# single cell selection
fc = FakeClient(["N"], [[1]]); use_nb(NB, fc)
r = sql_execution.execute_sql_notebook("P", "NB1", cell_id="c4")
check("single cell by id", r["cells_executed"] == 1 and len(fc.calls) == 1, r)
check("correct sql sent", fc.calls[0]["query"] == "SELECT 2", fc.calls)

r = sql_execution.execute_sql_notebook("P", "NB1", cell_id="nope")
check("unknown cell id errors", r["status"] == "error", r)
r = sql_execution.execute_sql_notebook("P", "NB1", cell_index=99)
check("out-of-range index errors", r["status"] == "error", r)

# stop_on_error
class FailFirst(FakeClient):
    def sql_query(self, query, connection=None, type=None, project_key=None):
        self.calls.append({"query": query})
        raise RuntimeError("nope")
use_nb(NB, FailFirst([], []))
r = sql_execution.execute_sql_notebook("P", "NB1", stop_on_error=True)
sts = [x["status"] for x in r["results"]]
check("stops after error", r["status"] == "error" and sts.count("error") == 1, sts)
check("later cell skipped after error", r["results"][-1]["status"] == "skipped", r["results"][-1])

# unsupported language
use_nb({**NB, "language": "SPARKSQL"}, FakeClient([], []))
r = sql_execution.execute_sql_notebook("P", "NB1")
check("rejects SPARKSQL clearly", r["status"] == "error" and "SPARKSQL" in r["message"], r)

# missing connection
use_nb({"language": "SQL", "cells": []}, FakeClient([], []))
r = sql_execution.execute_sql_notebook("P", "NB1")
check("missing connection errors", r["status"] == "error" and "connection" in r["message"], r)

print()
print(f"{'ALL PASSED' if not FAILS else str(len(FAILS)) + ' FAILED: ' + ', '.join(FAILS)}")
sys.exit(1 if FAILS else 0)
