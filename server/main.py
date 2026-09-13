"""Argusd MCP server: claim recording, freshness checks, and stale audits.

Wired to db.py against the repository-root SQLite file (argusd.db) so
claims survive across tool calls within a session. Tool descriptions
and return values are kept terse by design (a status word and a
timestamp, never file contents) to minimize per-turn token overhead.
"""

import argparse
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

import db
from hashing import hash_source

mcp = FastMCP("argusd")


def _get_conn():
    db_path = Path(os.environ.get("ARGUSD_DB_PATH", db.DEFAULT_DB_PATH))
    conn = db.connect(db_path)
    db.init_db(conn)
    return conn


@mcp.tool()
def record_claim(text: str, source_key: str) -> int:
    """Record a claim tied to a source (file path). Hashes it now, stores it fresh. Returns claim_id."""
    conn = _get_conn()
    try:
        source_hash = hash_source(source_key)
        return db.insert_claim(conn, text, source_key, source_hash)
    finally:
        conn.close()


def _refresh_claim(conn, claim_id: int) -> dict:
    claim = db.get_claim(conn, claim_id)
    if claim is None:
        raise ValueError(f"no claim with id {claim_id}")
    if claim["status"] == "fresh":
        try:
            current_hash = hash_source(claim["source_key"])
        except (FileNotFoundError, KeyError):
            current_hash = None  # a deleted source counts as changed
        if current_hash != claim["source_hash"]:
            db.mark_stale(conn, claim_id)
            claim = db.get_claim(conn, claim_id)
    result = {"status": claim["status"]}
    if claim["status"] == "stale":
        result["changed_at"] = claim["stale_at"]
        result["source_key"] = claim["source_key"]
    return result


@mcp.tool()
def check_freshness(claim_id: int) -> dict:
    """Rehash a claim's source; flips it stale if changed. Returns status and changed_at if stale."""
    conn = _get_conn()
    try:
        result = _refresh_claim(conn, claim_id)
        result.pop("source_key", None)
        return result
    finally:
        conn.close()


@mcp.tool()
def list_stale() -> list[dict]:
    """List every claim currently marked stale (id, text, source_key, stale_at)."""
    conn = _get_conn()
    try:
        return [dict(row) for row in db.list_stale_claims(conn)]
    finally:
        conn.close()


@mcp.tool()
def validate_claims(claim_ids: list[int]) -> dict:
    """Validate several claims before a risky action. Returns safe or stale."""
    if not isinstance(claim_ids, list) or any(not isinstance(claim_id, int) for claim_id in claim_ids):
        raise ValueError("claim_ids must be a list of integer claim IDs")
    checked_at = db.now_iso()
    conn = _get_conn()
    try:
        unique_ids = list(dict.fromkeys(claim_ids))
        missing = [claim_id for claim_id in unique_ids if db.get_claim(conn, claim_id) is None]
        if missing:
            raise ValueError(f"no claims with id(s) {missing}")
        stale_claims = []
        for claim_id in unique_ids:
            result = _refresh_claim(conn, claim_id)
            if result["status"] == "stale":
                stale_claims.append({"claim_id": claim_id, "source_key": result["source_key"], "changed_at": result["changed_at"]})
        if not stale_claims:
            return {"status": "safe", "checked_at": checked_at}
        return {"status": "stale", "checked_at": checked_at, "stale_claims": stale_claims}
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Argusd MCP server.")
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
