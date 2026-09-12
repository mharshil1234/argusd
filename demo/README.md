# Demo tooling

This folder contains the repeatable file-backed stale-claim demo. It uses the
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

In terminal two, point the dashboard at the generated database and start it:

```powershell
$env:ARGUSD_DB_PATH = (Resolve-Path demo\.run\argusd.db).Path
cd dashboard
npm.cmd run dev
```

Open `http://localhost:3000`. Two fresh claims should appear after the first
poll. In terminal one, trigger a controlled source edit:

```powershell
python demo\trigger_change.py --claim auth
```

Within one second, the dashboard should show one stale claim and one fresh
claim. The command also calls `check_freshness` and `list_stale` and prints
their results. Use `--claim routes` to run the same flow for the other claim.

The scripts support file-backed claims only. `.env` key claims remain later
roadmap work; git-state claims and the passive filesystem/git watcher
(`server/watcher.py`) are implemented as of Hours 8–14 but not yet wired
into this scripted walkthrough. The generated workspace is ignored by Git
and can be safely recreated with `--reset`.

When the watcher is used with the dashboard, each actual invalidation is
also retained in the dashboard's event log. Reloading the page does not
erase those events; only the latest 20 are displayed.
