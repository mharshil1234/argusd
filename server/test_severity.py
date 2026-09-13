#!/usr/bin/env python3
"""Coverage for claim severity and advisory recommended actions.

Run: python server/test_severity.py
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
        source = root / "risk.ts"
        source.write_text("export const risk = 'known';\n")
        db_path = root / "argusd.db"

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
        check("existing databases gain risk columns", {"severity", "recommended_action"}.issubset(columns))

        default_id = db.insert_claim(conn, "default risk", str(source), hash_file(source))
        default_claim = db.get_claim(conn, default_id)
        check("legacy-compatible default is medium", default_claim["severity"] == "medium" and default_claim["recommended_action"] == "reverify_before_continue")

        critical_id = db.insert_claim(conn, "critical risk", str(source), hash_file(source), severity="critical")
        critical_claim = db.get_claim(conn, critical_id)
        check("critical claims receive stop-and-escalate", critical_claim["recommended_action"] == "stop_and_escalate")
        invalid = False
        try:
            db.insert_claim(conn, "bad risk", str(source), hash_file(source), severity="urgent")
        except ValueError as error:
            invalid = "low, medium, high, critical" in str(error)
        check("invalid severity returns a clear error", invalid)
        conn.close()

        old_db = os.environ.get("ARGUSD_DB_PATH")
        os.environ["ARGUSD_DB_PATH"] = str(db_path)
        try:
            source.write_text("export const risk = 'changed';\n")
            result = main.validate_claims([critical_id])
            stale = result["stale_claims"][0]
            check("validation returns severity and recommended action", result["status"] == "stale" and stale["severity"] == "critical" and stale["recommended_action"] == "stop_and_escalate")
            check("risk response has no hashes", "hash" not in str(result).lower())
        finally:
            if old_db is None:
                os.environ.pop("ARGUSD_DB_PATH", None)
            else:
                os.environ["ARGUSD_DB_PATH"] = old_db

    print("\nAll checks passed.")


if __name__ == "__main__":
    run()
