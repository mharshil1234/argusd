"""Small shared MCP stdio client used by the repeatable demo scripts."""

from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import sys
from typing import AsyncIterator, Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


SERVER_DIR = Path(__file__).resolve().parent.parent / "server"


@asynccontextmanager
async def mcp_session(db_path: Path) -> AsyncIterator[ClientSession]:
    """Yield an MCP session connected to an isolated database."""
    params = StdioServerParameters(
        command=os.environ.get("PYTHON", sys.executable),
        args=["main.py"],
        cwd=str(SERVER_DIR),
        env={**os.environ, "ARGUSD_DB_PATH": str(db_path)},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def call_tool(session: ClientSession, name: str, arguments: dict[str, Any]) -> Any:
    """Call a tool and unwrap FastMCP's structured result."""
    result = await session.call_tool(name, arguments)
    if result.isError:
        message = "; ".join(getattr(block, "text", str(block)) for block in result.content)
        raise RuntimeError(f"MCP tool {name} failed: {message}")
    if result.structuredContent is not None:
        content = result.structuredContent
        if list(content.keys()) == ["result"]:
            return content["result"]
        return content
    if not result.content:
        raise RuntimeError(f"MCP tool {name} returned no content")
    text = getattr(result.content[0], "text", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text
