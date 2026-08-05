#!/usr/bin/env python3
"""Command-line entrypoint for the Dataiku MCP server.

This module deliberately lives *inside* the ``dataiku_mcp`` package.

The console script previously pointed at ``scripts.mcp_server:main``, but
setuptools' flat-layout auto-discovery excludes a top-level ``scripts``
directory by default (along with ``tests``, ``docs`` and friends). The
package therefore installed without it, and the installed
``dataiku-mcp-server`` launcher died at import with
``ModuleNotFoundError: No module named 'scripts'``.

Keeping the entrypoint in the package means whatever pip installs is
exactly what runs.
"""

import argparse
import logging
import sys
from typing import List, Optional

from dataiku_mcp.server import create_server

logger = logging.getLogger(__name__)


def configure_logging(verbose: bool = False) -> None:
    """Route all log output to stderr.

    The stdio transport uses **stdout** for JSON-RPC frames. Anything else
    written there corrupts the stream and the client drops the connection
    with an unhelpful "Connection closed". ``force=True`` overrides any
    handler installed at import time by other modules.
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dataiku-mcp-server",
        description="Dataiku DSS MCP server",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport mechanism (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host for SSE transport (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for SSE transport (default: 8000)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging (written to stderr)",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Start the MCP server. Returns a process exit code."""
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose)

    try:
        server = create_server()

        if args.transport == "sse":
            # FastMCP reads host/port from its settings object rather than
            # from run() keyword arguments.
            settings = getattr(server, "settings", None)
            if settings is not None:
                settings.host = args.host
                settings.port = args.port
            logger.info(
                "Starting Dataiku MCP server (sse) on %s:%s",
                args.host,
                args.port,
            )
            server.run(transport="sse")
        else:
            logger.info("Starting Dataiku MCP server (stdio)")
            server.run()

        return 0

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        return 0
    except Exception:
        logger.exception("Server error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
