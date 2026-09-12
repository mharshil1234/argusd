"""SQLite schema + claim/source CRUD for Argusd.

Flat two-table model: a claim points at exactly one source_key; a
source_key can invalidate many claims when its hash changes.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "argusd.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    source_key TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'fresh', -- 'fresh' | 'stale'
    stale_at TEXT
);

CREATE TABLE IF NOT EXISTS sources (
    key TEXT PRIMARY KEY,           -- e.g. "auth.ts", ".env:PORT", "git:HEAD"
    last_hash TEXT NOT NULL,
    last_checked TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


# --- sources -----------------------------------------------------------

def upsert_source(conn: sqlite3.Connection, key: str, source_hash: str) -> None:
    conn.execute(
        """
        INSERT INTO sources (key, last_hash, last_checked)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            last_hash = excluded.last_hash,
            last_checked = excluded.last_checked
        """,
        (key, source_hash, now_iso()),
    )
    conn.commit()


def get_source(conn: sqlite3.Connection, key: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM sources WHERE key = ?", (key,)
    ).fetchone()


# --- claims --------------------------------------------------------------

def insert_claim(
    conn: sqlite3.Connection, text: str, source_key: str, source_hash: str
) -> int:
    cur = conn.execute(
        """
        INSERT INTO claims (text, source_key, source_hash, created_at, status)
        VALUES (?, ?, ?, ?, 'fresh')
        """,
        (text, source_key, source_hash, now_iso()),
    )
    conn.commit()
    upsert_source(conn, source_key, source_hash)
    return cur.lastrowid


def get_claim(conn: sqlite3.Connection, claim_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM claims WHERE id = ?", (claim_id,)
    ).fetchone()


def mark_stale(conn: sqlite3.Connection, claim_id: int) -> None:
    conn.execute(
        "UPDATE claims SET status = 'stale', stale_at = ? WHERE id = ? AND status = 'fresh'",
        (now_iso(), claim_id),
    )
    conn.commit()


def mark_source_claims_stale(conn: sqlite3.Connection, source_key: str) -> list[int]:
    """Flip every fresh claim on source_key to stale. Returns affected claim ids."""
    rows = conn.execute(
        "SELECT id FROM claims WHERE source_key = ? AND status = 'fresh'",
        (source_key,),
    ).fetchall()
    ids = [row["id"] for row in rows]
    if ids:
        stale_at = now_iso()
        conn.executemany(
            "UPDATE claims SET status = 'stale', stale_at = ? WHERE id = ?",
            [(stale_at, claim_id) for claim_id in ids],
        )
        conn.commit()
    return ids


def list_stale_claims(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id AS claim_id, text, source_key, stale_at FROM claims WHERE status = 'stale'"
    ).fetchall()
