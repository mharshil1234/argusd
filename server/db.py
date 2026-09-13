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
    agent_id TEXT NOT NULL DEFAULT 'unattributed',
    session_id TEXT,
    status TEXT NOT NULL DEFAULT 'fresh', -- 'fresh' | 'stale'
    stale_at TEXT
);

CREATE TABLE IF NOT EXISTS sources (
    key TEXT PRIMARY KEY,           -- e.g. "auth.ts", ".env:PORT", "git:HEAD"
    last_hash TEXT NOT NULL,
    last_checked TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invalidation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    invalidated_count INTEGER NOT NULL CHECK (invalidated_count > 0)
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
    # Claims databases created before ownership support must remain readable.
    # SQLite only supports additive ALTER TABLE migrations, which is exactly
    # what this feature needs.
    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(claims)").fetchall()
    }
    if "agent_id" not in columns:
        conn.execute(
            "ALTER TABLE claims ADD COLUMN agent_id TEXT NOT NULL DEFAULT 'unattributed'"
        )
    if "session_id" not in columns:
        conn.execute("ALTER TABLE claims ADD COLUMN session_id TEXT")
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


def list_sources_by_prefix(conn: sqlite3.Connection, prefix: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM sources WHERE key LIKE ?", (prefix + "%",)
    ).fetchall()


# --- claims --------------------------------------------------------------

def insert_claim(
    conn: sqlite3.Connection,
    text: str,
    source_key: str,
    source_hash: str,
    agent_id: str = "unattributed",
    session_id: str | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO claims (
            text, source_key, source_hash, created_at, agent_id, session_id, status
        )
        VALUES (?, ?, ?, ?, ?, ?, 'fresh')
        """,
        (text, source_key, source_hash, now_iso(), agent_id, session_id),
    )
    conn.commit()
    new_id = cur.lastrowid
    upsert_source(conn, source_key, source_hash)
    supersede_stale_claims(conn, source_key, keep_id=new_id)
    return new_id


def supersede_stale_claims(conn: sqlite3.Connection, source_key: str, keep_id: int) -> list[int]:
    """A fresh claim replaces any stale claims about the same source -- the
    stale belief is moot once a current one exists (invalidation_events
    keeps the permanent history; this only trims the live claims list).
    Returns the removed claim ids."""
    rows = conn.execute(
        "SELECT id FROM claims WHERE source_key = ? AND status = 'stale' AND id != ?",
        (source_key, keep_id),
    ).fetchall()
    ids = [row["id"] for row in rows]
    if ids:
        conn.executemany("DELETE FROM claims WHERE id = ?", [(i,) for i in ids])
        conn.commit()
    return ids


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


def list_stale_claims(
    conn: sqlite3.Connection, session_id: str | None = None
) -> list[sqlite3.Row]:
    query = """
        SELECT id AS claim_id, text, source_key, stale_at, agent_id, session_id
        FROM claims
        WHERE status = 'stale'
    """
    params: tuple[str, ...] = ()
    if session_id is not None:
        query += " AND session_id = ?"
        params = (session_id,)
    return conn.execute(query + " ORDER BY stale_at DESC, id DESC", params).fetchall()


def insert_invalidation_event(
    conn: sqlite3.Connection, source_key: str, invalidated_count: int
) -> int:
    """Record one real fresh-to-stale transition for dashboard history."""
    if invalidated_count <= 0:
        raise ValueError("invalidated_count must be positive")
    cur = conn.execute(
        """
        INSERT INTO invalidation_events (source_key, occurred_at, invalidated_count)
        VALUES (?, ?, ?)
        """,
        (source_key, now_iso(), invalidated_count),
    )
    conn.commit()
    return cur.lastrowid


def list_invalidation_events(
    conn: sqlite3.Connection, limit: int = 20
) -> list[sqlite3.Row]:
    """Return recent invalidations newest-first, capped to a safe positive limit."""
    bounded_limit = max(1, min(limit, 100))
    return conn.execute(
        """
        SELECT id, source_key, occurred_at, invalidated_count
        FROM invalidation_events
        ORDER BY occurred_at DESC, id DESC
        LIMIT ?
        """,
        (bounded_limit,),
    ).fetchall()
