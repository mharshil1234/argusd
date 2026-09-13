#!/usr/bin/env python3
"""Coverage for backward-compatible agent and session claim ownership.

Run: python server/test_ownership.py
"""

import os
import tempfile
from pathlib import Path

import db
import main
from hashing import hash_file


def check(label: str, condition: bool) -> None:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}")
    if not condition:
        raise SystemExit(1)


def run() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "owned.ts"
        source.write_text("export const owner = 'initial';\n")
        db_path = root / "argusd.db"

        # Simulate the schema written by pre-ownership Argusd releases.
        conn = db.connect(db_path)
        conn.execute(
            """
            CREATE TABLE claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                source_key TEXT NOT NULL,
                source_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'fresh',
                stale_at TEXT
            )
            """
        )
        conn.commit()
        db.init_db(conn)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(claims)")}
        check("existing databases gain ownership columns", {"agent_id", "session_id"}.issubset(columns))

        legacy_id = db.insert_claim(conn, "legacy claim", str(source), hash_file(source))
        owned_id = db.insert_claim(
            conn,
            "owned claim",
            str(source),
            hash_file(source),
            agent_id="codex",
            session_id="review-a",
        )
        check("legacy claims retain a safe owner default", db.get_claim(conn, legacy_id)["agent_id"] == "unattributed")
        check("explicit agent and session are stored", db.get_claim(conn, owned_id)["session_id"] == "review-a")

        db.mark_source_claims_stale(conn, str(source))
        scoped = [dict(row) for row in db.list_stale_claims(conn, "review-a")]
        check("session scope returns only its own stale claim", [claim["claim_id"] for claim in scoped] == [owned_id])
        check("ownership output contains no source hash", "hash" not in str(scoped).lower())
        conn.close()

        old_db = os.environ.get("ARGUSD_DB_PATH")
        old_agent = os.environ.get("ARGUSD_AGENT_ID")
        old_session = os.environ.get("ARGUSD_SESSION_ID")
        os.environ["ARGUSD_DB_PATH"] = str(db_path)
        os.environ["ARGUSD_AGENT_ID"] = "claude"
        os.environ["ARGUSD_SESSION_ID"] = "review-b"
        try:
            source.write_text("export const owner = 'new';\n")
            env_owned_id = main.record_claim("environment owned", str(source))
            verification_conn = db.connect(db_path)
            env_owned = db.get_claim(verification_conn, env_owned_id)
            verification_conn.close()
            check("environment defaults identify a session", env_owned["agent_id"] == "claude" and env_owned["session_id"] == "review-b")
            invalid = False
            try:
                main.record_claim("invalid owner", str(source), agent_id=" ")
            except ValueError:
                invalid = True
            check("blank identifiers are rejected", invalid)
        finally:
            for name, value in (("ARGUSD_DB_PATH", old_db), ("ARGUSD_AGENT_ID", old_agent), ("ARGUSD_SESSION_ID", old_session)):
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    print("\nAll checks passed.")


if __name__ == "__main__":
    run()
