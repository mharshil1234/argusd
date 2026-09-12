# Argusd MCP server

Exposes the three real tools from `CLAUDE.md`, wired to SQLite:

- `record_claim(text, source_key) -> claim_id` hashes the source and stores a
  fresh claim.
- `check_freshness(claim_id) -> {status, changed_at?}` rehashes its source and
  marks the claim stale when it changed.
- `list_stale() -> [{claim_id, text, source_key, stale_at}]` returns all stale
  claims.

File, `git:`, and `.env:KEY` source keys are all supported now. `.env:KEY`
hashes only that key's value (see `parsers/env.py`) — never the whole
file, and never the raw value.

## Setup

Use Python 3.10+ in a virtual environment from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r server\requirements.txt
```

## Run

Stdio is the primary agent transport:

```powershell
python server\main.py
```

For HTTP/SSE debugging:

```powershell
python server\main.py --transport sse
```

The MCP framework prints its local SSE endpoint at startup. Connect an MCP
inspector or compatible client there.

## Watcher

The watcher is a separate, always-on process independent of the MCP
server's lifecycle — it invalidates claims the instant a source changes,
with no agent call involved. Run it in a second terminal, from the
repository root, and leave it running for the duration of a session:

```powershell
python server\watcher.py
```

Ctrl+C stops it. It watches the whole repo tree for file edits, `.git`
for commit/branch/index changes, and `.env` for per-key value changes —
diffing old vs. new key hashes so only the changed key's claims go stale,
never the whole file's. It flips dependent claims stale and logs every
invalidation to stdout as `[STALE] <source_key> changed at <ts> ->
invalidated claim ids [...]`. Set `ARGUSD_DB_PATH` the same way as for
`main.py` if you're pointing at a non-default database, and
`ARGUSD_ENV_PATH` to point at a non-default `.env` file.

Each real fresh-to-stale transition is also recorded in the additive
`invalidation_events` table. The dashboard reads the latest 20 events
read-only through its SSE feed, so the timeline survives browser reloads.

## Verify

The integration client starts the server over stdio and calls all three tools:

```powershell
python server\test_mcp_client.py
```

The hash-change proof can also be run independently:

```powershell
python server\test_hash_change.py
```

The watcher's file-content and git-state invalidation paths are proven the
same way, against disposable scratch trees:

```powershell
python server\test_watcher.py
```

The `.env` per-key parsing, hashing, and diff-only-the-changed-key
invalidation are proven independently:

```powershell
python server\test_env_parser.py
```

## Shared database

The authoritative `server/db.py` default is `argusd.db` at the repository
root. The MCP server initializes that schema; the dashboard opens the same
file read-only and never initializes or migrates it. Set `ARGUSD_DB_PATH` to
an absolute path to override the location for both processes. The database is
generated runtime state and ignored by Git.
