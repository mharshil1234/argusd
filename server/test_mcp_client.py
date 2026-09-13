#!/usr/bin/env python3
"""Standalone MCP client for the three real tools.

Spawns server/main.py as a subprocess over stdio and calls
record_claim, check_freshness, and list_stale directly over the MCP
protocol -- no agent required. Verifies each tool's behavior in
isolation before wiring up a real Claude Code session.

Run: python server/test_mcp_client.py
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

SERVER_DIR = Path(__file__).resolve().parent


def check(label: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        sys.exit(1)


def unwrap(result) -> object:
    """Turn a CallToolResult into the plain value a tool returned."""
    if result.isError:
        text = "; ".join(getattr(block, "text", str(block)) for block in result.content)
        raise RuntimeError(f"tool call failed: {text}")
    if result.structuredContent is not None:
        content = result.structuredContent
        # FastMCP wraps a bare int/list return under {"result": ...}.
        if list(content.keys()) == ["result"]:
            return content["result"]
        return content
    text = result.content[0].text
    try:
        return json.loads(text)
    except (json.JSONDecodeError, IndexError):
        return text


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        scratch_file = tmp_path / "auth.ts"
        scratch_file.write_text("export function login() { return true; }\n")

        params = StdioServerParameters(
            command=sys.executable,
            args=["main.py"],
            cwd=str(SERVER_DIR),
            env={**os.environ, "ARGUSD_DB_PATH": str(tmp_path / "argusd.db")},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                tool_names = {tool.name for tool in tools.tools}
                check("validate_claims is discoverable over stdio", "validate_claims" in tool_names)

                # 1. record_claim
                result = await session.call_tool(
                    "record_claim",
                    {"text": "no other files import this", "source_key": str(scratch_file)},
                )
                claim_id = unwrap(result)
                print(f"record_claim -> claim_id={claim_id}")
                check("record_claim returned an int id", isinstance(claim_id, int))

                # 2. check_freshness before any edit
                result = await session.call_tool("check_freshness", {"claim_id": claim_id})
                verdict = unwrap(result)
                print(f"check_freshness (unchanged) -> {verdict}")
                check("claim is fresh before any edit", verdict["status"] == "fresh")
                check("no changed_at while fresh", "changed_at" not in verdict)

                # 3. edit the source file out from under the claim
                scratch_file.write_text("export function login() { return false; }\n")

                # 4. check_freshness after the edit
                result = await session.call_tool("check_freshness", {"claim_id": claim_id})
                verdict = unwrap(result)
                print(f"check_freshness (after edit) -> {verdict}")
                check("claim flips stale after edit", verdict["status"] == "stale")
                check("changed_at is present once stale", "changed_at" in verdict)

                # 5. list_stale should surface the same claim
                result = await session.call_tool("list_stale", {})
                stale = unwrap(result)
                print(f"list_stale -> {stale}")
                stale_ids = [row["claim_id"] for row in stale]
                check("claim_id appears in list_stale", claim_id in stale_ids)

                result = await session.call_tool("validate_claims", {"claim_ids": [claim_id]})
                gate = unwrap(result)
                print(f"validate_claims -> {gate}")
                check("validate_claims reports the changed claim", gate["status"] == "stale" and gate["stale_claims"][0]["claim_id"] == claim_id)
                check("validate_claims response contains no hash", "hash" not in json.dumps(gate).lower())

    print("\nAll checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
