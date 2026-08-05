"""
Execute Jupyter notebooks inside Dataiku DSS and capture their outputs.

The public ``dataikuapi`` client can author notebooks but cannot *run* them.
DSS does, however, expose its embedded Jupyter server (with full ``dataiku``
project context) behind ``/jupyter/`` and accepts the DSS API key. This module
drives the standard Jupyter kernel protocol over that proxy:

1. GET ``/jupyter/`` once to obtain the tornado ``_xsrf`` cookie (required for
   POST/DELETE on the Jupyter REST API).
2. POST ``/jupyter/api/sessions`` with path ``"<PROJECT_KEY>/<notebook>.ipynb"``.
   DSS' session manager splits that on the last ``/`` -> head=project key
   (exported as ``DKU_CURRENT_PROJECT_KEY``), tail=notebook id. This is what
   gives the kernel its dataiku context.
3. Open a WebSocket to ``/jupyter/api/kernels/<id>/channels`` and send an
   ``execute_request`` per code cell, collecting iopub outputs until the kernel
   returns to ``idle`` and the shell reply arrives.
4. Optionally write the captured outputs back into the notebook (so they show
   up in the DSS UI) and DELETE the session to free the kernel.
"""

from __future__ import annotations

import base64
import json
import os
import ssl
import time
import uuid
from typing import Any, Dict, List, Optional

import requests
from websocket import create_connection
from websocket import WebSocketTimeoutException

from dataiku_mcp.client import get_project, _get_normalized_host


# --------------------------------------------------------------------------- #
# low-level helpers
# --------------------------------------------------------------------------- #
def _insecure() -> bool:
    return os.environ.get("DSS_INSECURE_TLS", "true").lower() == "true"


def _jupyter_session(host: str) -> requests.Session:
    """A requests session authenticated for the DSS Jupyter proxy, with xsrf."""
    s = requests.Session()
    s.auth = (os.environ.get("DSS_API_KEY", ""), "")
    s.verify = not _insecure()
    # Hitting any Jupyter HTML route sets the _xsrf cookie (404 is fine).
    s.get(host + "/jupyter/", timeout=30)
    xsrf = s.cookies.get("_xsrf")
    if xsrf:
        s.headers.update({"X-XSRFToken": xsrf})
    return s


def _source_to_str(source: Any) -> str:
    if isinstance(source, list):
        return "".join(source)
    return source or ""


def _list_kernel_names(session: requests.Session, host: str) -> List[str]:
    """Kernel spec names installed on the DSS Jupyter server, default first."""
    try:
        r = session.get(host + "/jupyter/api/kernelspecs", timeout=30)
        if r.status_code >= 300:
            return []
        payload = r.json()
        names = list((payload.get("kernelspecs") or {}).keys())
        default = payload.get("default")
        if default in names:
            names.remove(default)
            names.insert(0, default)
        return names
    except Exception:
        return []


def _pick_fallback_kernel(available: List[str], language: str = "python") -> Optional[str]:
    """Choose the most plausible substitute kernel for an unavailable one."""
    if not available:
        return None
    # Prefer the stock interpreter, then any kernel matching the language.
    for preferred in ("python3", "python2", "python"):
        if preferred in available:
            return preferred
    for name in available:
        if language in name.lower():
            return name
    return available[0]

def _ws_connect(host: str, kernel_id: str, client_session: str):
    ws_url = host.replace("https://", "wss://").replace("http://", "ws://")
    ws_url += f"/jupyter/api/kernels/{kernel_id}/channels?session_id={client_session}"
    auth = base64.b64encode(f"{os.environ.get('DSS_API_KEY','')}:".encode()).decode()
    sslopt = {"cert_reqs": ssl.CERT_NONE} if _insecure() else None
    return create_connection(
        ws_url,
        header=[f"Authorization: Basic {auth}"],
        sslopt=sslopt,
        timeout=30,
        max_size=None,
    )


def _send_execute(ws, client_session: str, code: str, msg_type: str = "execute_request",
                  content: Optional[Dict[str, Any]] = None) -> str:
    msg_id = uuid.uuid4().hex
    if content is None:
        content = {
            "code": code,
            "silent": False,
            "store_history": True,
            "user_expressions": {},
            "allow_stdin": False,
            "stop_on_error": True,
        }
    msg = {
        "header": {
            "msg_id": msg_id,
            "username": "mcp",
            "session": client_session,
            "msg_type": msg_type,
            "version": "5.3",
        },
        "parent_header": {},
        "metadata": {},
        "channel": "shell",
        "content": content,
    }
    ws.send(json.dumps(msg))
    return msg_id


def _wait_kernel_ready(ws, client_session: str, timeout: float) -> None:
    """Send a kernel_info_request and drain messages until we get the reply."""
    msg_id = _send_execute(ws, client_session, "", msg_type="kernel_info_request", content={})
    deadline = time.time() + timeout
    ws.settimeout(1.0)
    while time.time() < deadline:
        try:
            m = json.loads(ws.recv())
        except WebSocketTimeoutException:
            continue
        except Exception:
            return
        if m.get("parent_header", {}).get("msg_id") == msg_id and \
                m.get("header", {}).get("msg_type") == "kernel_info_reply":
            return


def _run_cell(ws, client_session: str, code: str, timeout: float) -> Dict[str, Any]:
    """Execute one code cell, return nbformat outputs + a text summary."""
    msg_id = _send_execute(ws, client_session, code)
    nb_outputs: List[Dict[str, Any]] = []
    text_chunks: List[str] = []
    status = "ok"
    exec_count = None
    idle = reply = False
    deadline = time.time() + timeout
    ws.settimeout(1.0)

    while time.time() < deadline and not (idle and reply):
        try:
            raw = ws.recv()
        except WebSocketTimeoutException:
            continue
        except Exception as e:  # connection dropped
            status = "error"
            text_chunks.append(f"[websocket error] {e}")
            break
        m = json.loads(raw)
        if m.get("parent_header", {}).get("msg_id") != msg_id:
            continue
        mt = m["header"]["msg_type"]
        c = m.get("content", {})

        if mt == "status":
            if c.get("execution_state") == "idle":
                idle = True
        elif mt == "stream":
            nb_outputs.append({"output_type": "stream",
                               "name": c.get("name", "stdout"),
                               "text": c.get("text", "")})
            text_chunks.append(c.get("text", ""))
        elif mt == "execute_result":
            data = c.get("data", {})
            exec_count = c.get("execution_count", exec_count)
            nb_outputs.append({"output_type": "execute_result",
                               "data": data, "metadata": c.get("metadata", {}),
                               "execution_count": exec_count})
            if "text/plain" in data:
                text_chunks.append(_source_to_str(data["text/plain"]))
        elif mt == "display_data":
            data = c.get("data", {})
            nb_outputs.append({"output_type": "display_data",
                               "data": data, "metadata": c.get("metadata", {})})
            if "text/plain" in data:
                text_chunks.append(_source_to_str(data["text/plain"]))
            else:
                text_chunks.append(f"[display_data: {', '.join(data.keys())}]")
        elif mt == "error":
            tb = c.get("traceback", [])
            nb_outputs.append({"output_type": "error",
                               "ename": c.get("ename", ""),
                               "evalue": c.get("evalue", ""),
                               "traceback": tb})
            # strip ANSI colour codes for the text summary
            import re
            clean = re.sub(r"\x1b\[[0-9;]*m", "", "\n".join(tb))
            text_chunks.append(clean or f"{c.get('ename','')}: {c.get('evalue','')}")
            status = "error"
        elif mt == "execute_reply":
            reply = True
            exec_count = c.get("execution_count", exec_count)
            if c.get("status") == "error":
                status = "error"

    if not (idle and reply):
        status = "timeout" if status == "ok" else status
        text_chunks.append(f"[cell did not finish within {timeout}s]")

    return {"status": status, "execution_count": exec_count,
            "nb_outputs": nb_outputs, "text": "".join(text_chunks)}


# --------------------------------------------------------------------------- #
# public tool
# --------------------------------------------------------------------------- #
def run_jupyter_notebook(
    project_key: str,
    notebook_name: str,
    kernel_name: Optional[str] = None,
    timeout_per_cell: int = 300,
    start_timeout: int = 120,
    stop_on_error: bool = True,
    write_outputs: bool = True,
    max_output_chars: int = 4000,
) -> Dict[str, Any]:
    """Run every code cell of a Jupyter notebook in DSS and capture outputs."""
    host = _get_normalized_host()
    session_id = None
    s = None
    ws = None
    try:
        # 1) load notebook content (cells + kernelspec)
        project = get_project(project_key)
        nb = project.get_jupyter_notebook(notebook_name)
        content_obj = nb.get_content()
        content = content_obj.get_raw()
        cells = content.get("cells", [])
        ks = (content.get("metadata", {}) or {}).get("kernelspec", {}) or {}
        kname = kernel_name or ks.get("name") or "python3"

        # 2) start a kernel session bound to the project
        s = _jupyter_session(host)
        body = {"path": f"{project_key}/{notebook_name}.ipynb", "type": "notebook",
                "name": notebook_name, "kernel": {"name": kname}}
        r = s.post(host + "/jupyter/api/sessions", json=body, timeout=start_timeout)
        # The notebook's own kernelspec is frequently a code-env kernel that is
        # not installed on this instance (e.g. 'python_env_DWAS_python'), which
        # DSS rejects with HTTP 501. Retry once with an installed kernel rather
        # than making the caller guess the name.
        kernel_fallback = None
        if r.status_code >= 300 and kernel_name is None:
            available = _list_kernel_names(s, host)
            substitute = _pick_fallback_kernel(available)
            if substitute and substitute != kname:
                body["kernel"] = {"name": substitute}
                retry = s.post(host + "/jupyter/api/sessions", json=body, timeout=start_timeout)
                if retry.status_code < 300:
                    kernel_fallback = (
                        f"kernel '{kname}' unavailable; fell back to '{substitute}'"
                    )
                    kname = substitute
                    r = retry
                else:
                    return {
                        "status": "error",
                        "message": (
                            f"Failed to start kernel session (HTTP {r.status_code}): "
                            f"{r.text[:300]} | fallback '{substitute}' also failed "
                            f"(HTTP {retry.status_code}). Installed kernels: "
                            f"{', '.join(available) or 'none reported'}"
                        ),
                    }

        if r.status_code >= 300:
            available = _list_kernel_names(s, host)
            return {
                "status": "error",
                "message": (
                    f"Failed to start kernel session (HTTP {r.status_code}): "
                    f"{r.text[:500]}"
                    + (f" | Installed kernels: {', '.join(available)}" if available else "")
                ),
            }

        sess = r.json()
        session_id = sess["id"]
        kernel_id = sess["kernel"]["id"]

        # 3) connect to the kernel and wait until it is ready
        client_session = uuid.uuid4().hex
        ws = _ws_connect(host, kernel_id, client_session)
        _wait_kernel_ready(ws, client_session, start_timeout)

        # 4) execute code cells in order
        results = []
        errored = False
        for idx, cell in enumerate(cells):
            if cell.get("cell_type") != "code":
                continue
            code = _source_to_str(cell.get("source"))
            if not code.strip():
                continue
            if errored and stop_on_error:
                results.append({"cell_index": idx, "status": "skipped",
                                "execution_count": None, "output": ""})
                if write_outputs:
                    cell["outputs"] = []
                    cell["execution_count"] = None
                continue
            res = _run_cell(ws, client_session, code, timeout_per_cell)
            if write_outputs:
                cell["outputs"] = res["nb_outputs"]
                cell["execution_count"] = res["execution_count"]
            text = res["text"]
            if len(text) > max_output_chars:
                text = text[:max_output_chars] + f"\n...[truncated {len(text)-max_output_chars} chars]"
            results.append({"cell_index": idx, "status": res["status"],
                            "execution_count": res["execution_count"], "output": text})
            if res["status"] != "ok":
                errored = True

        # 5) persist outputs back into the notebook (visible in DSS UI)
        if write_outputs:
            try:
                content_obj.content = content
                content_obj.save()
                saved = True
            except Exception as e:
                saved = False
                results.append({"cell_index": -1, "status": "warning",
                                "execution_count": None,
                                "output": f"[could not write outputs back: {e}]"})
        else:
            saved = False

        executed = [r for r in results if r["status"] not in ("skipped",)]
        n_err = sum(1 for r in results if r["status"] not in ("ok", "skipped"))
        response = {
            "status": "ok" if n_err == 0 else "error",
            "project_key": project_key,
            "notebook_name": notebook_name,
            "kernel": kname,
            "cells_executed": len(executed),
            "cells_failed": n_err,
            "outputs_written": saved,
            "results": results,
            "message": (f"Ran {len(executed)} code cell(s); {n_err} failed."
                        if n_err else f"Ran {len(executed)} code cell(s) successfully."),
        }
        if kernel_fallback:
            response["kernel_warning"] = kernel_fallback
        return response

    except Exception as e:
        return {"status": "error",
                "message": f"Failed to run Jupyter notebook '{notebook_name}': {e}"}
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
        # always release the kernel
        if s is not None and session_id is not None:
            try:
                s.delete(host + f"/jupyter/api/sessions/{session_id}", timeout=30)
            except Exception:
                pass


def get_jupyter_notebook_outputs(
    project_key: str,
    notebook_name: str,
    max_output_chars: int = 4000,
) -> Dict[str, Any]:
    """Read the stored outputs of a notebook's cells as plain text (no re-run)."""
    try:
        project = get_project(project_key)
        content = project.get_jupyter_notebook(notebook_name).get_content().get_raw()
        import re
        ansi = re.compile(r"\x1b\[[0-9;]*m")
        results = []
        for idx, cell in enumerate(content.get("cells", [])):
            if cell.get("cell_type") != "code":
                continue
            chunks = []
            status = "ok"
            for o in cell.get("outputs", []) or []:
                ot = o.get("output_type")
                if ot == "stream":
                    chunks.append(_source_to_str(o.get("text", "")))
                elif ot in ("execute_result", "display_data"):
                    data = o.get("data", {})
                    if "text/plain" in data:
                        chunks.append(_source_to_str(data["text/plain"]))
                    else:
                        chunks.append(f"[{ot}: {', '.join(data.keys())}]")
                elif ot == "error":
                    status = "error"
                    chunks.append(ansi.sub("", "\n".join(o.get("traceback", []))))
            text = "".join(chunks)
            if len(text) > max_output_chars:
                text = text[:max_output_chars] + f"\n...[truncated {len(text)-max_output_chars} chars]"
            results.append({"cell_index": idx, "status": status,
                            "execution_count": cell.get("execution_count"),
                            "output": text})
        return {"status": "ok", "project_key": project_key,
                "notebook_name": notebook_name, "results": results}
    except Exception as e:
        return {"status": "error",
                "message": f"Failed to read outputs for '{notebook_name}': {e}"}
