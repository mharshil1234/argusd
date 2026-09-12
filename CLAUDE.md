# Argusd — Project Brief

## Self-audit habit (dogfooding Argusd itself)

If the `argusd` MCP tools are available in this session, call `list_stale()`
once at the start of a task before making changes, and again before any
risky action — not on every turn, just at natural checkpoints.

For each claim `list_stale()` reports, this habit includes one further
step, automatically, without being asked: read the actual current content
of that specific claim's source (the one file, or the one `.env` key it
names — nothing else) and call `record_claim` with updated text reflecting
what's true now. Then briefly report what was found stale and what was
just re-recorded. The old stale claim is never deleted or un-staled —
recording a new one is how the belief gets updated.

**This habit is scoped to exactly that — checking and refreshing claims —
and nothing else.** Do not run scripts (`seed_claims.py`, `trigger_change.py`,
tests, etc.), reset the demo workspace, edit files other than reading the
specific stale sources named by `list_stale()`, make commits, or take any
other action as part of this habit, even on an ambiguous prompt like "let's
continue" — that phrase means "check and refresh claims," nothing broader.
Anything beyond checking/refreshing needs a separate, explicit ask in that
same turn.

## Context for the agent

You are helping build a hackathon MVP called **Argusd**. Read this whole
document before writing any code. Two people are working on this in
parallel — task ownership is marked below as **[A]** or **[B]**. There is a
**Review 1 checkpoint at the 3-hour mark**, so prioritize getting that
milestone working and demonstrable over anything later in the roadmap.

## Status (updated as phases complete)

The sections below are the original roadmap and remain the reference for
what's still pending — this block only tracks what's actually done so far.

- **Hours 0–3 (Review 1) — done.** `server/db.py` (claims/sources schema)
  and `server/hashing.py` (file hashing) proven via `server/test_hash_change.py`.
- **Hours 3–8 — done.** `record_claim`, `check_freshness`, `list_stale`
  implemented for real in `server/main.py` against a shared `argusd.db` at
  the repo root; verified end-to-end over the real MCP protocol by
  `server/test_mcp_client.py`. The dashboard reads that same file (`[B]`).
- **Hours 8–14 — done.** `server/watcher.py` watches the repo tree and
  `.git` directly and flips dependent claims stale the instant a source
  changes, with no agent call involved; `hash_git_state()` is implemented
  for real. Proven by `server/test_watcher.py` and by a live run (edit a
  file, watcher logs `[STALE] ...` and the DB flips with zero MCP calls).
  The dashboard replaced polling with a live `GET /api/events`
  Server-Sent-Events feed (`[B]`).
- **Demo tooling — done ahead of schedule.** `demo/seed_claims.py`,
  `demo/trigger_change.py`, and `demo/mcp_client.py` implement the
  repeatable file-backed stale-claim walkthrough over the real MCP stdio
  tools, proven by `demo/test_demo.py`; originally scheduled for Hours
  20–28 but landed early (`[B]`).
- **Hours 14–20 — done.** `[A]` `server/parsers/env.py` hashes each `.env`
  key's value individually; `hash_source(".env:KEY")` is implemented for
  real (was a stub); `server/watcher.py` diffs old vs. new key-hash maps
  on every `.env` save so only the changed key's claims go stale, proven
  by `server/test_env_parser.py` and a live run (edit one key, only that
  key's claim flips), and each invalidation is persisted via
  `db.insert_invalidation_event`. `[B]` added the `invalidation_events`
  table, a durable event-log UI on the dashboard (survives reloads), and a
  watcher robustness fix (`Debouncer.close()` / `observer.unschedule_all()`
  so no debounced callback fires after teardown).
- **Hours 20–28 — done.** Root `.mcp.json` registers `server/main.py` as a
  stdio MCP server for Claude Code (`command` must point to the platform's
  virtual-environment interpreter — `.venv\\Scripts\\python.exe` on
  Windows, `.venv/bin/python` on Unix — not bare `python`, because the
  system interpreter may lack the `mcp` package,
  which caused an immediate `CONNECTION_CLOSED` the first time this was
  tried against a real session). `demo/` now seeds and triggers a third
  claim, `.env:PORT`, alongside `auth`/`routes` (`demo/mcp_client.py`'s
  `mcp_session` gained an `env_path` param for `ARGUSD_ENV_PATH`), and
  `--claim auth` now also writes a narrative-only `login.ts` that imports
  `auth.ts` (not tracked — no import-graph/dependency tracking, out of
  scope by design), matching CLAUDE.md's own demo script. `demo/README.md`
  documents starting `server/watcher.py` before `trigger_change.py` so
  invalidations are watcher-driven and live on the dashboard, not just
  `trigger_change.py`'s own `check_freshness` call. The full pitch was
  verified end-to-end with real, separate `claude -p` sessions (not the
  scripted `mcp_client.py` test double): one session called `record_claim`
  on a scratch file; the file was then changed outside any agent turn;
  `server/watcher.py` flipped the claim stale with zero agent tokens
  spent; the same session was resumed and its `list_stale()` call
  surfaced the drift immediately. Hours 28–33 are complete after repeated
  isolated demo runs; Hours 33–36 is rehearsal-ready with the documented
  90-second runbook and deterministic scripted fallback. Human timed practice
  remains a presentation activity.
- **Correction (post-merge):** the teammate's fix for the Hours 20–28
  `CONNECTION_CLOSED` bug swapped `.mcp.json`'s `command` to the Windows
  venv path, which broke it outright on Linux (verified: `ENOENT`). A
  single committed path can't serve both platforms. Fixed properly via
  Claude Code's local-scope override (`claude mcp add --scope local argusd
  -- <path-to-venv-python> server/main.py`, once per developer, written to
  `~/.claude.json`, never committed) — see root `README.md`. Re-verified
  live on Linux after the fix. The "Hours 28–33 complete"/"Hours 33–36
  rehearsal-ready" claims above are the teammate's own report from their
  (Windows/Codex) side; not independently re-verified from this session.
- **Independent re-verification (this session, Linux):** ran the full
  `demo/seed_claims.py` → watcher → dashboard → `trigger_change.py` loop
  end to end using the pre-existing `.venv` and a live `server/watcher.py`
  already running against `demo/.run/argusd.db`. Confirmed, via direct file
  edits with zero MCP calls, that the watcher independently flips all three
  source types — `auth.ts`, `routes.ts`, and `.env:PORT` (only the changed
  key, `routes.ts`/other keys left untouched) — and that `dashboard`'s
  `/api/claims` and the `invalidation_events` table reflect each transition
  live. This confirms the core mechanic and the 90-second rehearsal script
  work on Linux from this session, not just the teammate's Windows/Codex
  report above. Workspace was reset back to a clean fresh state afterward
  via `--reset`.

See `README.md` and `server/README.md` for exact run/verify commands.

## The problem

AI coding agents build a mental model of a codebase as they work — "this
file has no tests," "the server runs on port 3000," "this branch is clean."
That model is frozen at the moment it was observed. Nothing tells the agent
when it stops being true. If a file changes, a config value changes, or git
state shifts (from the user, another process, or another agent), the agent
keeps acting on the old belief until it happens to re-check — which it
usually doesn't, because nothing prompts it to.

Existing tools solve adjacent problems (blocking dangerous commands, giving
agents long-term memory) but nothing tracks the **freshness** of what an
agent already believes.

## The pitch

"Every AI agent remembers what it saw. None of them know when what they saw
stopped being true. Argusd timestamps every claim an agent makes about code
or config, and the instant the underlying source changes, it invalidates
that claim before the agent acts on stale information."

## How this differs from existing tools

- **Memory / RAG tools** store what an agent has seen, but never check if
  it's still true.
- **Command blockers / firewalls** (Claude Code hooks, MCP firewalls) judge
  whether an action is dangerous, but ignore whether the reasoning behind
  that action is outdated.
- **Argusd** does neither of those — it puts an expiration date on facts the
  agent already has, and cancels that fact the moment its source changes.
  It's not more memory, and it's not a bouncer at the door.

## Core mechanic

1. The agent records a claim via an MCP tool, tied to a specific source (a
   file, a git ref, or a config key).
2. A passive watcher hashes that source continuously, independent of the
   agent — this costs zero agent tokens.
3. The moment a source's hash changes, every claim depending on it flips to
   `stale`, with no agent action required.
4. Before acting on a prior claim, the agent calls a freshness-check tool and
   gets back `FRESH` or `STALE: changed at <timestamp>`.
5. A live dashboard shows the claim timeline and invalidation events, for
   the demo.

## Data model (SQLite)

```sql
CREATE TABLE claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    source_key TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'fresh', -- 'fresh' | 'stale'
    stale_at TEXT
);

CREATE TABLE sources (
    key TEXT PRIMARY KEY,           -- e.g. "auth.ts", ".env:PORT", "git:HEAD"
    last_hash TEXT NOT NULL,
    last_checked TEXT NOT NULL
);
```

Keep this flat. No graph database. A claim points at exactly one source key;
a source key can invalidate many claims when it changes.

## Source types, in build priority order

1. **File content** — SHA256 of full file bytes. Baseline case: "this
   function does X."
2. **Git state** — hash of HEAD commit + branch name + a boolean for
   working-tree-clean. Lets you demo: "you're on main with no uncommitted
   changes" going stale the instant that changes.
3. **Config keys** (`.env`, optionally `package.json` / `docker-compose.yml`)
   — hash each key's *value* individually, not the whole file. Editing an
   unrelated line in `.env` must NOT invalidate a claim about `PORT` unless
   `PORT` itself changed.

   ```python
   def parse_env_hashes(path):
       hashes = {}
       for line in open(path):
           line = line.strip()
           if not line or line.startswith("#") or "=" not in line:
               continue
           key, value = line.split("=", 1)
           hashes[key.strip()] = hashlib.sha256(value.strip().encode()).hexdigest()
       return hashes  # {"PORT": "a1b2...", "DATABASE_URL": "9f8e..."}
   ```

   **Never store or display raw values** — only hashes and a changed
   boolean. The dashboard shows `.env:PORT — CHANGED at 14:32`, never the
   actual old/new values.

## MCP tools to expose

Keep tool descriptions short and return values terse (a status word + a
timestamp, never full file contents). This keeps token overhead small — the
schema for these three tools sits in the agent's context every turn
regardless of use.

- `record_claim(text: str, source_key: str) -> claim_id`
  Hashes the source right now, stores the claim as fresh.
- `check_freshness(claim_id: int) -> {status, changed_at?}`
  Rehashes the source, compares to the stored hash, flips status if
  different, returns the verdict.
- `list_stale() -> [{claim_id, text, source_key, stale_at}]`
  Everything currently stale — meant to be called by the agent at the start
  of a task or before a risky action, as a self-audit.

## Architecture

```
Agent (Claude Code / Codex / OpenCode)
        │ MCP
        ▼
     Argusd MCP server (Python)             [A]
        │
   ┌────┼────────────┐
   ▼    ▼             ▼
 Files  Git          Config keys
 (watchdog)  (.git/HEAD watch)   (.env parser)      [A]
        │
        ▼
     SQLite (claims, sources)                [A]
        │
        ▼
  Next.js dashboard (WebSocket live feed)     [B]
```

No browser/CDP integration, no Tree-sitter/LSP dependency graph, no
recovery/checkpoint system — out of scope for this build.

## File structure

```
argusd/
  server/
    main.py            # MCP server entrypoint, tool definitions        [A]
    db.py               # SQLite schema + claim/source CRUD             [A]
    hashing.py           # file hash, git-state hash, env-key hash fns  [A]
    watcher.py            # watchdog-based filesystem + git watcher     [A]
    parsers/
      env.py              # .env key-level parser                      [A]
  dashboard/
    (Next.js app)                                                       [B]
      app/page.tsx        # single live-updating page                  [B]
      app/api/ws/route.ts  # WebSocket feed from SQLite / watcher       [B]
  demo/
    seed_claims.py         # scripted demo: record a couple of claims  [B]
    trigger_change.py       # scripted demo: flips a value on cue      [B]
  CLAUDE.md
  README.md
```

## Team workflow (2 people)

**Person A — core engine.** Owns `server/`: data model, hashing, MCP
tools, watcher, config parsing. This is the part that has to be *correct*,
since it's the whole idea — prioritize it being right over being fast.

**Person B — dashboard + demo tooling.** Owns `dashboard/` and `demo/`:
the live view, the WebSocket feed, and the scripted demo triggers. Can build
against a stub/mock of the DB schema before Person A's engine is fully wired,
since the schema is fixed up front and won't change shape.

Work in parallel from hour 0. Sync briefly before Review 1 to confirm the
DB schema hasn't drifted between what A implemented and what B is reading
from.

## Roadmap with Review 1 at hour 3

### Before Review 1 (Hours 0–3)

- **[A]** Implement `db.py` (schema above) and `hashing.py` (file hashing +
  a stub for git/env hashing). Test from a Python REPL: insert a claim,
  hash a file, change the file, rehash, confirm the hash differs. This is
  the core proof-of-concept and should be demonstrable standalone.
- **[B]** Scaffold the repo: Next.js app skeleton, MCP server skeleton with
  one dummy tool (e.g. `ping`) so the agent connection path is proven end to
  end, and a placeholder dashboard page. Also scaffold `demo/` folder
  structure.

**Review 1 deliverable:** show (1) hash-change detection working live in a
REPL or a short script, and (2) an MCP client (or Claude Code itself)
successfully calling a dummy tool on the server. This proves both halves of
the architecture are reachable before building the real logic on top.

### After Review 1 (Hours 3–36)

3. **Hours 3–8 — MCP tools, wired.** **[A]** Implement `record_claim`,
   `check_freshness`, `list_stale` for real, wired to `db.py`. **[B]** Wire
   the dashboard skeleton to read directly from the SQLite file (polling is
   fine for now) so there's a visible claims list, even if static.
4. **Hours 8–14 — Filesystem + git watcher.** **[A]** `watchdog` on the repo
   directory; on save, rehash and flip dependent claims stale immediately,
   independent of any agent call. Extend to git-state claims (branch,
   commit, clean-tree) and log every invalidation event. **[B]** Replace
   dashboard polling with a real WebSocket feed driven by watcher events.
5. **Hours 14–20 — Config-key claims + dashboard polish.** **[A]** Implement
   `parsers/env.py`; diff old vs. new key-hash maps on save so only the
   changed key's claims go stale. **[B]** Claim list UI: color-coded
   fresh/stale, event log underneath ("`.env:PORT` changed at 14:32 →
   invalidated 1 claim").
6. **Hours 20–28 — Integration.** Both: connect the MCP server to a real
   Claude Code session. Script a task where a claim goes stale mid-session
   and the agent's next `check_freshness` or `list_stale` call catches it.
   Build out `demo/seed_claims.py` and `demo/trigger_change.py` together.
7. **Hours 28–33 — Full run-throughs.** Both: run the complete demo end to
   end multiple times, fix whatever breaks under real conditions.
8. **Hours 33–36 — Rehearse and de-risk.** Time-box a 90-second run-through
   3–4 times. If any live watcher trigger is flaky on stage, fall back to
   the scripted `trigger_change.py` instead of live-editing a file in a
   second terminal — reliability beats realism for the actual demo slot.

## Demo script (90 seconds)

1. Agent works on `auth.ts`, records a claim: "no other files import this."
2. `demo/trigger_change.py` runs: makes a second file import `auth.ts`, and
   separately flips `PORT=3000` to `PORT=4000` in `.env`.
3. Dashboard flips both claims to stale in real time, timestamped.
4. Agent calls `list_stale()` before its next action, sees both flags, and
   re-verifies instead of acting on outdated beliefs.
5. Closing line: memory tools tell an agent what it saw; this tells it when
   what it saw stopped being true.

## Token-cost design constraints (keep these in mind while coding)

- Fixed cost: the 3 tool schemas sit in the agent's context every turn
  regardless of use — keep descriptions and parameter lists minimal.
- Variable cost: each tool call adds a tool_use/tool_result pair to
  context — keep `check_freshness` and `list_stale` responses to a status
  word and a timestamp, never full file contents or claim history dumps.
- The filesystem/git watcher must do all its work outside the model — zero
  agent tokens spent on passive invalidation.
- Do not build any mechanism that force-injects a "check freshness" reminder
  into every turn — that's the anti-pattern that would make this expensive.
  Rely on the agent calling `list_stale()` at natural checkpoints instead.

## What is explicitly out of scope for this build

- Blocking dangerous shell/git commands (solved elsewhere, not this
  project's differentiator).
- Tree-sitter/LSP-based dependency/impact graphs.
- Browser/DOM/console state tracking.
- Task recovery / checkpoint / "resume" style features.
- Multi-repo or multi-agent support.

Start now: **[A]** scaffold `server/db.py` and `server/hashing.py` and
confirm hash-change detection from a REPL. **[B]** scaffold the Next.js
dashboard and a dummy-tool MCP server so the connection path to Claude Code
is proven. Both should be ready to demo by hour 3 for Review 1.
