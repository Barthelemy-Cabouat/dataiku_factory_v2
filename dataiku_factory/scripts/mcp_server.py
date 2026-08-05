#!/usr/bin/env python3
"""Local development entrypoint.

Thin shim kept so that ``python scripts/mcp_server.py`` keeps working from a
source checkout. The real implementation lives in ``dataiku_mcp.cli`` so that
it is packaged and installed by pip -- see the note in that module.

Prefer the installed console script in any deployed setting:

    dataiku-mcp-server [--transport stdio|sse] [--verbose]
"""

import sys
from pathlib import Path

# Allow running directly from a source checkout without installing.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dataiku_mcp.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
