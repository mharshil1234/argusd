#!/usr/bin/env python3
"""Standalone proof-of-concept for Review 1.

Run: python server/test_hash_change.py

Inserts a claim about a scratch file, edits the file, rehashes, and
confirms (a) the hash changed and (b) the claim can be flipped stale.
Uses a throwaway on-disk DB and scratch file so it's safe to re-run.
"""

import sys
import tempfile
from pathlib import Path

from db import connect, init_db, insert_claim, get_claim, get_source, mark_source_claims_stale
from hashing import hash_file


def check(label: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        sys.exit(1)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db_path = tmp_path / "test_argusd.db"
        scratch_file = tmp_path / "auth.ts"
        scratch_file.write_text("export function login() { return true; }\n")

        conn = connect(db_path)
        init_db(conn)

        # 1. Hash the file and record a claim tied to it.
        source_key = str(scratch_file)
        original_hash = hash_file(scratch_file)
        claim_id = insert_claim(
            conn,
            text="no other files import this",
            source_key=source_key,
            source_hash=original_hash,
        )
        print(f"Recorded claim {claim_id} on {source_key} (hash={original_hash[:12]}...)")

        claim = get_claim(conn, claim_id)
        check("claim stored as fresh", claim["status"] == "fresh")

        source = get_source(conn, source_key)
        check("source row hash matches file hash", source["last_hash"] == original_hash)

        # 2. Edit the file.
        scratch_file.write_text("export function login() { return false; }\n")

        # 3. Rehash and confirm the hash differs.
        new_hash = hash_file(scratch_file)
        check("hash changed after edit", new_hash != original_hash)

        # 4. Simulate what the watcher does on change: flip dependent claims.
        stale_ids = mark_source_claims_stale(conn, source_key)
        check("claim flipped to stale", claim_id in stale_ids)

        claim = get_claim(conn, claim_id)
        check("claim status is now 'stale'", claim["status"] == "stale")
        check("stale_at was set", claim["stale_at"] is not None)

        conn.close()

    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
