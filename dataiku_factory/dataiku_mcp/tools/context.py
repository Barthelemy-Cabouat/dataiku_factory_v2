"""
Serve the business glossary: which dataset answers which question.

Why this exists
---------------
"How many clients do we have?" is not answerable from a schema. BURUNDI_BIZOPS
contains 32 datasets whose names begin ``VFINERACT_CLIENTS``, and an agent
choosing among them by name alone is guessing. Worse, the guess is invisible:
``VFINERACT_CLIENTS_BI_QC_Final_1`` returns a number, just not the right one.

The glossary anchors each business concept to one dataset, one measure and one
filter, so the agent looks the answer up instead of inferring it.

Design
------
Two tools rather than one. ``list_concepts`` returns a compact index -- names
and aliases only -- so the agent can see what is covered for a few hundred
tokens. ``lookup_concept`` returns one full entry. Returning every entry on
every call would reproduce the payload problem this repo has spent a while
fixing, since an agent framework replays each tool result on every subsequent
turn.

Entries live in ``dataiku_mcp/context/*.md`` and ship inside the installed
package, so the glossary is versioned with the code that reads it.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

_CONTEXT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "context")

# "key: value" lines directly under a heading are treated as structured fields;
# everything after them is free prose.
_FIELD_RE = re.compile(r"^([a-z_]+):\s*(.*)$")


def _parse_file(path: str) -> List[Dict[str, Any]]:
    """Parse one glossary markdown file into entries."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except Exception:
        return []

    topic = os.path.splitext(os.path.basename(path))[0]
    entries: List[Dict[str, Any]] = []

    # Split on level-2 headings; anything before the first is file-level preamble.
    chunks = re.split(r"^##\s+", text, flags=re.MULTILINE)[1:]
    for chunk in chunks:
        lines = chunk.splitlines()
        if not lines:
            continue
        name = lines[0].strip()
        fields: Dict[str, str] = {}
        prose: List[str] = []
        for line in lines[1:]:
            m = _FIELD_RE.match(line.strip())
            if m and not prose:
                fields[m.group(1)] = m.group(2).strip()
            elif line.strip() or prose:
                prose.append(line)

        aliases = [a.strip() for a in fields.get("aliases", "").split(",") if a.strip()]
        entries.append({
            "concept": name,
            "topic": topic,
            "aliases": aliases,
            "fields": fields,
            "notes": "\n".join(prose).strip(),
            "raw": ("## " + chunk).strip(),
        })
    return entries


def _load_all() -> List[Dict[str, Any]]:
    if not os.path.isdir(_CONTEXT_DIR):
        return []
    out: List[Dict[str, Any]] = []
    for fn in sorted(os.listdir(_CONTEXT_DIR)):
        if fn.endswith(".md") and not fn.startswith("_"):
            out.extend(_parse_file(os.path.join(_CONTEXT_DIR, fn)))
    return out


def list_concepts(topic: Optional[str] = None) -> Dict[str, Any]:
    """
    Index of every defined business concept: name, aliases and dataset.

    Args:
        topic: Optionally restrict to one glossary file (e.g. "clients").

    Returns:
        Dict with the concept index.
    """
    try:
        entries = _load_all()
        if topic:
            t = topic.strip().lower()
            entries = [e for e in entries if e["topic"].lower() == t]

        if not entries:
            return {
                "status": "ok",
                "concept_count": 0,
                "concepts": [],
                "message": (
                    "No glossary entries found."
                    + (f" No topic named '{topic}'." if topic else "")
                ),
            }

        return {
            "status": "ok",
            "concept_count": len(entries),
            "topics": sorted({e["topic"] for e in entries}),
            "concepts": [
                {
                    "concept": e["concept"],
                    "topic": e["topic"],
                    "aliases": e["aliases"],
                    "dataset": e["fields"].get("dataset"),
                }
                for e in entries
            ],
            "message": "Call lookup_concept for the full definition of any entry.",
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to list concepts: {e}"}


def lookup_concept(query: str) -> Dict[str, Any]:
    """
    Full definition of one business concept.

    Args:
        query: Concept name or alias, e.g. "number of clients".

    Returns:
        Dict with the matching entry, or near-misses if nothing matched.
    """
    try:
        entries = _load_all()
        if not entries:
            return {"status": "error", "message": "Glossary is empty or not installed."}

        q = (query or "").strip().lower()
        if not q:
            return {"status": "error", "message": "query is required."}

        def names(e):
            return [e["concept"].lower()] + [a.lower() for a in e["aliases"]]

        exact = [e for e in entries if q in names(e)]
        partial = [e for e in entries if any(q in n or n in q for n in names(e))]
        hits = exact or partial

        if not hits:
            return {
                "status": "not_found",
                "query": query,
                "message": (
                    f"No glossary entry matches '{query}'. Do not guess a dataset; "
                    "call list_concepts to see what is defined, or ask the user "
                    "which dataset they mean."
                ),
                "available": [e["concept"] for e in entries],
            }

        return {
            "status": "ok",
            "query": query,
            "match_count": len(hits),
            "entries": [
                {
                    "concept": e["concept"],
                    "topic": e["topic"],
                    "aliases": e["aliases"],
                    **e["fields"],
                    "notes": e["notes"],
                }
                for e in hits[:5]
            ],
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to look up '{query}': {e}"}
