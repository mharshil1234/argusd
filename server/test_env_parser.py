#!/usr/bin/env python3
"""Standalone proof of per-key .env hashing and watcher diffing.

Run: python server/test_env_parser.py

Three parts, each using disposable scratch files:

1. Parser: parse_env_hashes hashes each key's value individually and never
   returns a raw value.
2. hash_source dispatch: ".env:KEY" resolves through ARGUSD_ENV_PATH, and
   an unknown key raises KeyError (so check_freshness treats it as changed).
3. Watcher diffing: editing one .env key only flips that key's claims
   stale -- an untouched key's claim stays fresh. Deleting a key also
   invalidates it.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

from watchdog.observers import Observer

from db import connect, init_db, insert_claim, get_claim, list_invalidation_events
from hashing import hash_env_value, hash_source
from parsers.env import parse_env_hashes
from watcher import Debouncer, RepoChangeHandler

POLL_TIMEOUT = 5.0
POLL_INTERVAL = 0.05


def check(label: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        sys.exit(1)


def wait_until(predicate, timeout: float = POLL_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(POLL_INTERVAL)
    return False


def test_parser(tmp_path: Path) -> None:
    env_file = tmp_path / "parser.env"
    env_file.write_text(
        "# a comment\n"
        "\n"
        "PORT=3000\n"
        "DATABASE_URL=postgres://user:pass@host/db?opt=a=b\n"
    )

    hashes = parse_env_hashes(env_file)
    check("only real keys parsed", set(hashes) == {"PORT", "DATABASE_URL"})
    check("PORT hash matches direct hash", hashes["PORT"] == hash_env_value("3000"))
    check(
        "value with embedded '=' hashed past the first '=' only",
        hashes["DATABASE_URL"] == hash_env_value("postgres://user:pass@host/db?opt=a=b"),
    )
    check("no raw value leaks into the hash map", "3000" not in hashes.values())


def test_hash_source_dispatch(tmp_path: Path) -> None:
    env_file = tmp_path / "dispatch.env"
    env_file.write_text("PORT=3000\n")
    os.environ["ARGUSD_ENV_PATH"] = str(env_file)

    check(
        "hash_source(.env:PORT) matches parser",
        hash_source(".env:PORT") == hash_env_value("3000"),
    )
    try:
        hash_source(".env:MISSING")
        check("unknown .env key raises KeyError", False)
    except KeyError:
        check("unknown .env key raises KeyError", True)


def test_watcher_diffing(tmp_path: Path) -> None:
    repo_root = tmp_path / "envrepo"
    repo_root.mkdir()
    env_file = repo_root / ".env"
    env_file.write_text("PORT=3000\nDATABASE_URL=postgres://a\nEXTRA=keep\n")

    db_path = tmp_path / "env_test.db"
    conn = connect(db_path)
    init_db(conn)
    os.environ["ARGUSD_DB_PATH"] = str(db_path)

    port_claim = insert_claim(
        conn, text="server listens on PORT", source_key=".env:PORT",
        source_hash=hash_env_value("3000"),
    )
    db_claim = insert_claim(
        conn, text="db is postgres", source_key=".env:DATABASE_URL",
        source_hash=hash_env_value("postgres://a"),
    )
    extra_claim = insert_claim(
        conn, text="extra key is set", source_key=".env:EXTRA",
        source_hash=hash_env_value("keep"),
    )

    debouncer = Debouncer(0.05)
    observer = Observer()
    observer.schedule(
        RepoChangeHandler(debouncer, repo_root, env_path=env_file),
        str(repo_root),
        recursive=True,
    )
    observer.start()
    try:
        # Change only PORT; DATABASE_URL and EXTRA keep their values.
        env_file.write_text("PORT=4000\nDATABASE_URL=postgres://a\nEXTRA=keep\n")

        stale = wait_until(lambda: get_claim(conn, port_claim)["status"] == "stale")
        check("changed key's claim flips to stale via watcher alone", stale)

        time.sleep(0.2)  # let any (incorrect) cross-invalidation settle
        check(
            "unrelated unchanged keys' claims stay fresh",
            get_claim(conn, db_claim)["status"] == "fresh"
            and get_claim(conn, extra_claim)["status"] == "fresh",
        )

        # Remove EXTRA entirely; PORT/DATABASE_URL lines untouched.
        env_file.write_text("PORT=4000\nDATABASE_URL=postgres://a\n")

        deleted = wait_until(lambda: get_claim(conn, extra_claim)["status"] == "stale")
        check("deleting a key's line invalidates that key's claim too", deleted)

        time.sleep(0.2)
        check(
            "a key untouched by the deletion stays fresh",
            get_claim(conn, db_claim)["status"] == "fresh",
        )

        events = list_invalidation_events(conn)
        event_keys = [event["source_key"] for event in events]
        check(
            "each changed key recorded its own invalidation event, not the whole file",
            event_keys.count(".env:PORT") == 1
            and event_keys.count(".env:EXTRA") == 1
            and ".env:DATABASE_URL" not in event_keys,
        )
    finally:
        observer.unschedule_all()
        observer.stop()
        observer.join()
        debouncer.close()
        conn.close()


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        test_parser(tmp_path)
        test_hash_source_dispatch(tmp_path)
        test_watcher_diffing(tmp_path)

    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
