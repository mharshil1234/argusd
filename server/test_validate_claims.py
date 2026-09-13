#!/usr/bin/env python3
"""Edge-case coverage for the multi-claim freshness gate.

Run: python server/test_validate_claims.py
"""

import os
import tempfile
from pathlib import Path

import db
import main
from hashing import hash_env_value, hash_file


def check(label: str, condition: bool) -> None:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}")
    if not condition:
        raise SystemExit(1)


def run() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = root / "first.ts"
        second = root / "second.ts"
        env_file = root / ".env"
        first.write_text("one\n")
        second.write_text("two\n")
        env_file.write_text("PORT=3000\n")
        db_path = root / "argusd.db"
        old_db = os.environ.get("ARGUSD_DB_PATH")
        old_env = os.environ.get("ARGUSD_ENV_PATH")
        os.environ["ARGUSD_DB_PATH"] = str(db_path)
        os.environ["ARGUSD_ENV_PATH"] = str(env_file)
        try:
            conn = db.connect(db_path)
            db.init_db(conn)
            ids = [
                db.insert_claim(conn, "first source is one", str(first), hash_file(first)),
                db.insert_claim(conn, "second source is two", str(second), hash_file(second)),
                db.insert_claim(conn, "port is 3000", ".env:PORT", hash_env_value("3000")),
            ]
            conn.close()

            check("empty list is safe", main.validate_claims([])["status"] == "safe")
            safe = main.validate_claims(ids)
            check("multiple unchanged claims are safe", safe["status"] == "safe")

            first.write_text("changed\n")
            second.write_text("also changed\n")
            env_file.write_text("PORT=4000\n")
            stale = main.validate_claims(ids)
            stale_ids = {row["claim_id"] for row in stale["stale_claims"]}
            check("multiple changed claims are reported", stale["status"] == "stale" and stale_ids == set(ids))
            check("stale response has no hashes or raw values", all(secret not in str(stale) for secret in ("source_hash", "3000", "4000")))

            again = main.validate_claims(ids)
            check("already-stale claims remain stale", again["status"] == "stale" and {row["claim_id"] for row in again["stale_claims"]} == set(ids))
            conn = db.connect(db_path)
            check("validation does not duplicate watcher events", len(db.list_invalidation_events(conn)) == 0)
            conn.close()

            missing_error = False
            try:
                main.validate_claims([9999])
            except ValueError as error:
                missing_error = "9999" in str(error)
            check("missing claim IDs return a clear error", missing_error)

            mixed_error = False
            try:
                main.validate_claims([ids[0], 9999])
            except ValueError as error:
                mixed_error = "9999" in str(error)
            check("mixed valid and missing IDs fail before partial validation", mixed_error)
        finally:
            if old_db is None:
                os.environ.pop("ARGUSD_DB_PATH", None)
            else:
                os.environ["ARGUSD_DB_PATH"] = old_db
            if old_env is None:
                os.environ.pop("ARGUSD_ENV_PATH", None)
            else:
                os.environ["ARGUSD_ENV_PATH"] = old_env

    print("\nAll checks passed.")


if __name__ == "__main__":
    run()
