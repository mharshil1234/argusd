"""Argusd MCP server scaffold for the Review 1 connection proof."""

import argparse
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("argusd")


@mcp.tool()
def ping() -> str:
    """Confirm that the Argusd MCP server is reachable."""
    timestamp = datetime.now(timezone.utc).isoformat()
    return f"PONG {timestamp}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Argusd MCP scaffold.")
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse"),
        default="stdio",
        help="MCP transport (stdio for agents, sse for HTTP debugging).",
    )
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
