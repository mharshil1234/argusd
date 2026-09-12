# Demo tooling

This folder contains the repeatable stale-claim demo: two file-backed claims
(`auth.ts`, `routes.ts`) and one config-key claim (`.env:PORT`). It uses the
real MCP stdio tools and writes all generated sources, database state, and the
non-sensitive manifest under `demo/.run/` by default.

## Codex registration

Codex stores MCP servers in user configuration rather than reading the
repository's `.mcp.json`. From the repository root, run once in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File demo\register_codex.ps1
codex mcp get argusd
```

The helper will not create a duplicate registration. Use `-Force` to replace
an existing `argusd` entry, then start a fresh Codex session.

## Run the demo

From the repository root, install Python dependencies first:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r server\requirements.txt
```

In terminal one, seed the isolated workspace:

```powershell
python demo\seed_claims.py --reset
```

It prints the generated database and `.env` paths — keep them handy for the
next two terminals.

In terminal two, start the watcher against that same workspace so
invalidations happen live, independent of `trigger_change.py`:

```powershell
$env:ARGUSD_DB_PATH = (Resolve-Path demo\.run\argusd.db).Path
$env:ARGUSD_ENV_PATH = (Resolve-Path demo\.run\.env).Path
python server\watcher.py
```

In terminal three, point the dashboard at the generated database and start it:

```powershell
$env:ARGUSD_DB_PATH = (Resolve-Path demo\.run\argusd.db).Path
cd dashboard
npm.cmd run dev
```

Open `http://localhost:3000`. Three fresh claims should appear. Back in
terminal one, trigger a controlled source edit:

```powershell
python demo\trigger_change.py --claim auth
```

The watcher (terminal two) flips the claim stale within its debounce window
and the dashboard updates live over its SSE feed — `trigger_change.py`'s own
`check_freshness`/`list_stale` calls just confirm what already happened.
`--claim auth` also writes a second file, `login.ts`, that imports `auth.ts`
— purely narrative (Argusd hashes `auth.ts` itself; it has no import-graph
tracking, which is explicitly out of scope). Use `--claim routes` for the
other file claim, or `--claim env` to flip the seeded `PORT` value in
`.env`. Argusd's own storage/API never touches or exposes the raw value —
only hashes — but `--claim env` also re-records an updated belief after
the flip (agent-authored narrative text, same as the seed claim's own
"port 3000" text), which shows up as a second, fresh `.env:PORT` claim
right next to the now-stale original: drift caught, then re-verified.

The generated workspace is ignored by Git and can be safely recreated with
`--reset`. Each real invalidation — file, git-state, or `.env` key — is also
retained in the dashboard's event log; reloading the page does not erase
those events, and only the latest 20 are displayed.

## 90-second rehearsal

1. Seed the workspace and verify that a fresh Codex session can discover and
   call the Argusd tools.
2. Start `server\watcher.py` with the generated database and `.env` paths.
3. Start the dashboard and show the three fresh claims.
4. Trigger `auth`, then `env`, and point out the live stale badges and durable
   event entries. Note `env` also re-records an updated belief, which
   appears fresh right next to the stale original — the full loop, not
   just the drift. Ask Codex to call `list_stale` before continuing.
5. Reload the dashboard to prove event history persists.

If live editing or startup is unreliable during review, use
`trigger_change.py --claim auth` or `--claim env` as the deterministic
fallback. The narrative `login.ts` does not imply import-graph tracking.
