# Demo tooling

This folder contains the repeatable stale-claim demo: two file-backed claims
(`auth.ts`, `routes.ts`) and one config-key claim (`.env:PORT`). It uses the
real MCP stdio tools and writes all generated sources, database state, and the
non-sensitive manifest under `demo/.run/` by default.

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
`.env` — never the raw value, only the hash, is ever stored or printed.

The generated workspace is ignored by Git and can be safely recreated with
`--reset`. Each real invalidation — file, git-state, or `.env` key — is also
retained in the dashboard's event log; reloading the page does not erase
those events, and only the latest 20 are displayed.
