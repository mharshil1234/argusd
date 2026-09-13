# Argusd

Argusd timestamps claims an AI coding agent makes about a codebase and marks
them stale when their source changes. The repository currently combines the
Python SQLite/hash foundation with a read-only Next.js claims dashboard.

## Current checkpoint: Hours 33–36 readiness

- `server/db.py` owns the shared SQLite schema and writes runtime data to
  `argusd.db` at the repository root.
- `server/hashing.py` hashes file content, git state (`git:HEAD`), and
  individual `.env` keys (`.env:KEY`) via `server/parsers/env.py`.
- `server/main.py` exposes `record_claim`, `check_freshness`, `list_stale`,
  and the multi-claim `validate_claims` preflight over stdio or SSE/HTTP.
  Claims can also carry a display-safe agent/session owner, severity, and an
  advisory recommended action when stale.
- `server/watcher.py` is a standalone, always-on process that watches the
  repo tree, `.git`, and `.env` directly, flips dependent claims stale the
  instant their source changes — diffing old vs. new key hashes so an
  `.env` edit only invalidates the changed key's claims — and logs every
  invalidation. No agent call involved. See `server/README.md` for how to
  run it.
- `dashboard/` reads that same database without creating or migrating it,
  and exposes both `GET /api/claims` (manual/debug) and a live
  `GET /api/events` Server-Sent Events feed the UI subscribes to.
- The live dashboard includes a durable invalidation timeline backed by the
  `invalidation_events` table; recent events survive page reloads and feed
  reconnects. It displays the owner of each claim without exposing source
  hashes or raw configuration values, plus severity and stale-claim guidance.
- `demo/` contains a repeatable file-backed stale-claim walkthrough.

Hours 20–28 integration and the Hours 28–33 full run-throughs are complete.
The remaining Hours 33–36 work is human rehearsal using the documented
90-second run and deterministic scripted fallback.

Both halves of Hours 14–20 are done: config-key (`.env`) claims and the
dashboard's invalidation-timeline/event-log UI.

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

**Claude Code:** the repo-root `.mcp.json` registers this server as a
project-scoped default, but its `command` is a single hardcoded interpreter
path — whichever OS committed it last, the other OS gets an immediate
`ENOENT`/`CONNECTION_CLOSED` (verified: a Windows path there breaks Linux
outright, and vice versa). Don't fight over which path is committed — each
developer instead registers a **local-scope** override once, which lives in
their own `~/.claude.json` and is never committed, and takes precedence over
the project entry with the same name:

```bash
# Linux/Mac
claude mcp add --scope local argusd -- "$(pwd)/.venv/bin/python" "$(pwd)/server/main.py"
```

```powershell
# Windows
claude mcp add --scope local argusd -- "$PWD\.venv\Scripts\python.exe" "$PWD\server\main.py"
```

After that, opening Claude Code in this directory (approving the one-time
"project requires approval to run MCP servers" prompt) gives the session
`record_claim`/`check_freshness`/`list_stale` regardless of what's committed
in `.mcp.json`. Verified end-to-end with real `claude -p` sessions on Linux.

**Codex CLI:** Codex keeps MCP registrations in user configuration. From the
repository root, register Argusd once in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File demo\register_codex.ps1
codex mcp get argusd
```

The helper is idempotent; pass `-Force` only to replace an existing entry.
Start a fresh Codex session after registration so it discovers the tools.

Before a risky action, an agent can call `validate_claims([claim_id, ...])`.
It returns `safe` when all claims still match their sources, or `stale` with
the affected claim IDs and source keys. It is advisory and does not block
shell commands automatically.

### Attribute claims to an agent session

`record_claim` accepts optional `agent_id` and `session_id` strings. Use
short, non-secret display identifiers so a shared dashboard can distinguish
which agent session recorded a belief:

```text
record_claim(
  text="The auth module uses the current session contract.",
  source_key="src/auth.ts",
  agent_id="codex",
  session_id="review-42"
)
```

The MCP server also reads `ARGUSD_AGENT_ID` and `ARGUSD_SESSION_ID` when
those arguments are omitted. `list_stale(session_id="review-42")` limits a
stale audit to that session; `list_stale()` remains the cross-session view.
Do not put API keys, `.env` values, tokens, emails, or other sensitive data
in either identifier. Older database rows remain readable and appear as
`unattributed` with no session.

### Set claim severity and act on stale results

`record_claim` also accepts a `severity`: `low`, `medium` (the default),
`high`, or `critical`. Severity is advisory; Argusd never blocks shell or
Git commands automatically. When a claim is stale, `check_freshness`,
`list_stale`, and `validate_claims` return its server-assigned action:

| Severity | Recommended action |
| --- | --- |
| Low | `review_before_next_change` |
| Medium | `reverify_before_continue` |
| High | `pause_and_reverify` |
| Critical | `stop_and_escalate` |

For example, use `severity="critical"` for a production deployment or
security assumption. The dashboard makes the severity and action visible on
each stale claim. Existing database rows migrate to medium severity.

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

For the repeatable demo and final rehearsal, see `demo/README.md`. It uses
`demo/.run/argusd.db`, records file, git-state, and `.env` claims through MCP,
changes one controlled source at a time, and leaves the dashboard showing the
fresh/stale split plus the durable event timeline.

## Verification

Dashboard checks run from `dashboard/`:

```powershell
npm.cmd test
npm.cmd run lint
npm.cmd run build
```

The MCP freshness-gate proof runs from `server/`:

```powershell
python server\test_validate_claims.py
python server\test_ownership.py
python server\test_severity.py
```

The test fixture verifies waiting and error states, fresh/stale counts,
newest-first ordering, nullable `stale_at`, and that hashes are absent from
the response. The reader opens SQLite read-only and never initializes or
migrates the database.

The verified development host used Node.js 25.6.1, npm 11.9.0, and Python
3.12.14. The hash-change proof, stdio MCP integration client, watcher
proof (`server/test_watcher.py`), and `.env` per-key proof
(`server/test_env_parser.py`) all pass; the SSE transport also starts
successfully and serves its event-stream handshake on `/sse`. End-to-end
was also verified manually: with the watcher and dashboard both running,
editing a file with a tracked claim produced a `[STALE]` log line and the
same-second `stale` flip on the live dashboard, with no client polling;
editing one `.env` key while another was left untouched flipped only the
changed key's claim.
