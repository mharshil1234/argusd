# Argusd

Argusd timestamps claims an AI coding agent makes about a codebase and marks
them stale when their source changes. The repository currently combines the
Python SQLite/hash foundation with a read-only Next.js claims dashboard.

## Current checkpoint: Hours 8–14

- `server/db.py` owns the shared SQLite schema and writes runtime data to
  `argusd.db` at the repository root.
- `server/hashing.py` hashes file content and git state (`git:HEAD`).
- `server/main.py` exposes `record_claim`, `check_freshness`, and `list_stale`
  over stdio or SSE/HTTP.
- `server/watcher.py` is a standalone, always-on process that watches the
  repo tree and `.git` directly, flips dependent claims stale the instant
  their source changes, and logs every invalidation — no agent call
  involved. See `server/README.md` for how to run it.
- `dashboard/` reads that same database without creating or migrating it,
  and exposes both `GET /api/claims` (manual/debug) and a live
  `GET /api/events` Server-Sent Events feed the UI subscribes to.
- The live dashboard includes a durable invalidation timeline backed by the
  `invalidation_events` table; recent events survive page reloads and feed
  reconnects.
- `demo/` contains a repeatable file-backed stale-claim walkthrough.

`.env` config-key claims and the dashboard's invalidation-timeline UI
belong to Hours 14–20 and are intentionally not part of this checkpoint.

## 1. Set up Python and initialize SQLite

Use Python 3.10 or newer from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r server\requirements.txt
python -c "from server.db import connect, init_db; connection = connect(); init_db(connection); connection.close()"
```

The final command creates the root `argusd.db` and its `claims` and `sources`
tables. The database is generated runtime state and is ignored by Git.

To repeat Person A's hash-change proof:

```powershell
python server\test_hash_change.py
```

## 2. Run and verify the MCP connection

Stdio is the primary agent transport:

```powershell
python server\main.py
```

Configure that command as a stdio MCP server. Call `record_claim` for a file,
edit the file, then call `check_freshness`; the second call should report the
claim as stale. `list_stale` returns the stale claim summary.

For an HTTP/SSE client or MCP inspector:

```powershell
python server\main.py --transport sse
```

Connect the client to the FastMCP SSE endpoint printed at startup. See
`server/README.md` for the server-only setup and integration client.

## 3. Run the watcher

In a second terminal, from the repository root, leave this running for the
rest of the session — it's independent of the MCP server's lifecycle:

```powershell
python server\watcher.py
```

See `server/README.md` for what it watches and how it logs invalidations.

## 4. Run the dashboard

Use Node.js 20.9 or newer. In a third terminal:

```powershell
cd dashboard
npm.cmd ci
npm.cmd run dev
```

Open `http://localhost:3000`. The dashboard reports an actionable waiting
state until the root database and schema exist, then displays claims newest
first with fresh/stale counts, updating live over Server-Sent Events as the
watcher invalidates claims — no manual refresh or client-side polling. It
only exposes claim ID, text, source key, timestamps, and freshness status;
source hashes never enter the API response. The event log shows the source,
time, and number of claims invalidated, and remains available after reload.

The database path can be overridden for both the MCP server and dashboard,
which is useful for testing and alternate checkouts:

```powershell
$env:ARGUSD_DB_PATH = "C:\absolute\path\to\argusd.db"
npm.cmd run dev
```

Without the variable, both processes resolve the repository-root `argusd.db`.

For the repeatable demo, see `demo/README.md`. It uses
`demo/.run/argusd.db`, records two file-backed claims through MCP, changes one
generated source, and leaves the dashboard showing the fresh/stale split.

## Verification

Dashboard checks run from `dashboard/`:

```powershell
npm.cmd test
npm.cmd run lint
npm.cmd run build
```

The test fixture verifies waiting and error states, fresh/stale counts,
newest-first ordering, nullable `stale_at`, and that hashes are absent from
the response. The reader opens SQLite read-only and never initializes or
migrates the database.

The verified development host used Node.js 25.6.1, npm 11.9.0, and Python
3.12.14. The hash-change proof, stdio MCP integration client, and watcher
proof (`server/test_watcher.py`) all pass; the SSE transport also starts
successfully and serves its event-stream handshake on `/sse`. End-to-end
was also verified manually: with the watcher and dashboard both running,
editing a file with a tracked claim produced a `[STALE]` log line and the
same-second `stale` flip on the live dashboard, with no client polling.
