# Argusd MCP server

Exposes the three real tools from CLAUDE.md, wired to SQLite:

- `record_claim(text, source_key) -> claim_id` — hashes the source now,
  stores the claim as fresh.
- `check_freshness(claim_id) -> {status, changed_at?}` — rehashes the
  source, flips the claim stale if it changed, returns the verdict.
- `list_stale() -> [{claim_id, text, source_key, stale_at}]` — every
  currently-stale claim.

Claims persist in `server/argusd.db` (gitignored) so they survive across
tool calls within a session. `source_key` is a file path for now; `git:`
and `.env:KEY` prefixes are recognized but raise `NotImplementedError`
until the watcher and env-parser phases land.

## Setup

Use Python 3.10+ in a virtual environment, then install:

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

For HTTP/SSE debugging, run:

```powershell
python server\main.py --transport sse
```

The MCP framework serves its SSE endpoint using its default local host/port.
Use an MCP client inspector or the agent's MCP configuration to connect.

## Test client

`test_mcp_client.py` spawns the server over stdio and calls all three
tools directly (no agent required) to verify behavior in isolation:

```
python server/test_mcp_client.py
```
