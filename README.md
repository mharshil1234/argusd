# Argusd

Argusd timestamps claims an AI coding agent makes about a codebase and marks
them stale when their source changes. The repository currently combines the
Python SQLite/hash foundation with a read-only Next.js claims dashboard.

## Current checkpoint: Hours 3–8

- `server/db.py` owns the shared SQLite schema and writes runtime data to
  `argusd.db` at the repository root.
- `server/hashing.py` contains Person A's source-hashing proof.
- `server/main.py` exposes `record_claim`, `check_freshness`, and `list_stale`
  over stdio or SSE/HTTP.
- `dashboard/` reads that same database without creating or migrating it,
  exposes `GET /api/claims`, and polls the endpoint every second.
- `demo/` remains placeholder tooling until the integration phase.

WebSockets, watcher events, and the invalidation timeline belong to Hours
8–14 and are intentionally not part of this checkpoint.

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

## 3. Run the dashboard

In a second terminal:

```powershell
cd dashboard
npm.cmd install
npm.cmd run dev
```

Open `http://localhost:3000`. The dashboard reports an actionable waiting
state until the root database and schema exist, then displays claims newest
first with fresh/stale counts. It only exposes claim ID, text, source key,
timestamps, and freshness status; source hashes never enter the API response.

The database path can be overridden for both testing and alternate checkouts:

```powershell
$env:ARGUSD_DB_PATH = "C:\absolute\path\to\argusd.db"
npm.cmd run dev
```

Without the variable, starting Next.js from `dashboard/` resolves
`../argusd.db`, matching `server/db.py`.

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

On the current development host, Node.js 25.6.1 and npm 11.9.0 are available.
Python and the Windows `py` launcher are not installed, so the Python hash
test, schema initialization, and MCP runtime checks must be run on a host with
Python 3.10+ before the combined demo is signed off.
