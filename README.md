# Argusd

Argusd timestamps the claims an AI coding agent makes about a codebase and invalidates them when their underlying source changes.

## Hour 0–3 scaffold

This checkpoint contains the Person B dashboard and MCP connection proof:

- `dashboard/` — Next.js App Router + TypeScript placeholder page.
- `server/main.py` — MCP server with one `ping` tool.
- `demo/` — documented placeholders for later claim seeding and change triggering.

Real claims, SQLite integration, filesystem watching, and the live dashboard feed are intentionally deferred until after Review 1.

## Run the dashboard

```powershell
cd dashboard
npm.cmd install
npm.cmd run dev
```

Open `http://localhost:3000`. For a production check, use `npm.cmd run lint` and `npm.cmd run build`.

## Prove the MCP connection

The MCP dependency is declared in `server/requirements.txt`. With Python 3.10+:

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -r server\\requirements.txt
python server\\main.py
```

Configure the command as a stdio MCP server in the agent, then call `ping`. A successful result begins with `PONG` and includes an ISO-8601 UTC timestamp.

For HTTP/SSE debugging, run `python server\\main.py --transport sse` and connect an MCP inspector or compatible client to the framework’s default SSE endpoint.

## Verification status

Node.js 25.6.1 is available, but npm PowerShell script execution is restricted and Python is not installed in the current environment. Dashboard checks can be run with `npm.cmd`; MCP runtime checks require Python 3.10+.
