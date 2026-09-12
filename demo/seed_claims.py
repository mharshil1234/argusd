"""Create an isolated workspace and record representative claims through MCP."""

import argparse
import asyncio
import json
from pathlib import Path

from mcp_client import call_tool, mcp_session


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKSPACE = REPO_ROOT / "demo" / ".run"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed an isolated Argusd demo workspace.")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--reset", action="store_true", help="Replace an existing demo workspace.")
    return parser.parse_args()


def prepare_workspace(workspace: Path, reset: bool) -> None:
    if workspace in (REPO_ROOT, REPO_ROOT / "demo"):
        raise ValueError("Refusing to use the repository or demo directory as a workspace.")
    if workspace.exists():
        if not reset:
            raise FileExistsError(f"Workspace already exists: {workspace}. Use --reset to replace it.")
        import shutil

        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)


async def seed(workspace: Path) -> dict[str, object]:
    sources = {
        "auth": ("auth.ts", "The auth module has no stale imports."),
        "routes": ("routes.ts", "The routes module uses the current auth contract."),
    }
    claims: dict[str, dict[str, object]] = {}
    for filename, _ in sources.values():
        (workspace / filename).write_text(f"export const source = {filename!r};\n", encoding="utf-8")

    env_path = workspace / ".env"
    env_path.write_text("PORT=3000\n", encoding="utf-8")

    async with mcp_session(workspace / "argusd.db") as session:
        for key, (filename, text) in sources.items():
            claim_id = await call_tool(session, "record_claim", {"text": text, "source_key": str(workspace / filename)})
            if not isinstance(claim_id, int):
                raise RuntimeError(f"record_claim returned an invalid id for {key}: {claim_id!r}")
            claims[key] = {"id": claim_id, "source": str(workspace / filename), "text": text}

    async with mcp_session(workspace / "argusd.db", env_path=env_path) as session:
        text = "the server runs on port 3000"
        claim_id = await call_tool(session, "record_claim", {"text": text, "source_key": ".env:PORT"})
        if not isinstance(claim_id, int):
            raise RuntimeError(f"record_claim returned an invalid id for env: {claim_id!r}")
        claims["env"] = {"id": claim_id, "source": ".env:PORT", "text": text}

    manifest = {"version": 1, "workspace": str(workspace), "database": str(workspace / "argusd.db"), "claims": claims}
    (workspace / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    args = parse_args()
    workspace = args.workspace.resolve()
    try:
        prepare_workspace(workspace, args.reset)
        manifest = asyncio.run(seed(workspace))
    except (FileExistsError, ValueError, RuntimeError) as error:
        raise SystemExit(f"Seed failed: {error}") from error
    print(f"Seeded demo workspace: {manifest['workspace']}")
    for key, claim in manifest["claims"].items():
        print(f"  {key}: claim_id={claim['id']} source={claim['source']}")
    print(
        "Next: start server/watcher.py with ARGUSD_DB_PATH and ARGUSD_ENV_PATH set to "
        f"{workspace / 'argusd.db'} and {workspace / '.env'}, start the dashboard with the "
        "same ARGUSD_DB_PATH, then run trigger_change.py."
    )


if __name__ == "__main__":
    main()
