# Argusd MCP server scaffold

This is the Hour 0–3 connection proof. It exposes one tool, `ping`, and does
not yet read SQLite or implement claims.

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
Use an MCP client inspector or the agent’s MCP configuration to connect and
call `ping`. The expected result starts with `PONG` and includes an ISO-8601
UTC timestamp.

The real `record_claim`, `check_freshness`, and `list_stale` tools are deferred
until after the Review 1 checkpoint.
