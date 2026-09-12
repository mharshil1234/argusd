"""Change one generated source and verify its claim becomes stale through MCP."""

import argparse
import asyncio
import json
from pathlib import Path

from mcp_client import call_tool, mcp_session


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKSPACE = REPO_ROOT / "demo" / ".run"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trigger one controlled stale-claim change.")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--claim", choices=("auth", "routes", "env"), default="auth")
    return parser.parse_args()


def load_manifest(workspace: Path) -> dict[str, object]:
    manifest_path = workspace / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"No demo manifest found at {manifest_path}. Run seed_claims.py first.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("workspace") != str(workspace) or manifest.get("database") != str(workspace / "argusd.db"):
        raise ValueError("Manifest does not match the selected workspace.")
    claims = manifest.get("claims")
    if not isinstance(claims, dict) or set(claims) != {"auth", "routes", "env"}:
        raise ValueError("Manifest must contain auth, routes, and env claims.")
    return manifest


async def trigger_file_claim(
    workspace: Path, claim_key: str, claim: dict[str, object]
) -> tuple[dict[str, object], list[dict[str, object]]]:
    source = Path(claim["source"])
    expected_source = workspace / ("auth.ts" if claim_key == "auth" else "routes.ts")
    if source != expected_source or not source.is_file():
        raise ValueError("Manifest points outside the controlled demo source set.")
    source.write_text(source.read_text(encoding="utf-8") + "// Argusd demo change.\n", encoding="utf-8")
    if claim_key == "auth":
        # Narrative flavor only: Argusd hashes auth.ts itself, not an import
        # graph (dependency/impact graphs are explicitly out of scope), so
        # this file isn't tracked -- the edit to auth.ts above is what
        # actually invalidates the claim.
        (workspace / "login.ts").write_text(
            'import { source } from "./auth.ts";\nexport const login = source;\n',
            encoding="utf-8",
        )
    async with mcp_session(workspace / "argusd.db") as session:
        verdict = await call_tool(session, "check_freshness", {"claim_id": claim["id"]})
        stale = await call_tool(session, "list_stale", {})
    return verdict, stale


async def trigger_env_claim(
    workspace: Path, claim: dict[str, object]
) -> tuple[dict[str, object], list[dict[str, object]]]:
    if claim["source"] != ".env:PORT":
        raise ValueError("Manifest's env claim must be .env:PORT.")
    env_path = workspace / ".env"
    if not env_path.is_file():
        raise ValueError(f"No .env file found at {env_path}. Run seed_claims.py first.")
    env_path.write_text(env_path.read_text(encoding="utf-8").replace("PORT=3000", "PORT=4000"), encoding="utf-8")
    async with mcp_session(workspace / "argusd.db", env_path=env_path) as session:
        verdict = await call_tool(session, "check_freshness", {"claim_id": claim["id"]})
        stale = await call_tool(session, "list_stale", {})
    # Deliberately stops here, same as trigger_file_claim: this only flips
    # the claim stale. Re-verifying and recording an updated belief is the
    # live agent's self-audit habit's job (see CLAUDE.md), not this script's
    # -- keeping both claim types stale until asked, consistently.
    return verdict, stale


async def trigger(
    workspace: Path, claim_key: str, manifest: dict[str, object]
) -> tuple[dict[str, object], list[dict[str, object]]]:
    claim = manifest["claims"][claim_key]
    if claim_key == "env":
        verdict, stale = await trigger_env_claim(workspace, claim)
    else:
        verdict, stale = await trigger_file_claim(workspace, claim_key, claim)
    if not isinstance(verdict, dict) or verdict.get("status") != "stale":
        raise RuntimeError(f"Expected a stale verdict, received {verdict!r}")
    if not isinstance(stale, list):
        raise RuntimeError(f"Expected a stale claim list, received {stale!r}")
    return verdict, stale


def main() -> None:
    args = parse_args()
    workspace = args.workspace.resolve()
    try:
        manifest = load_manifest(workspace)
        verdict, stale = asyncio.run(trigger(workspace, args.claim, manifest))
    except (FileNotFoundError, ValueError, RuntimeError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise SystemExit(f"Trigger failed: {error}") from error
    changed = ".env:PORT" if args.claim == "env" else f"{args.claim}.ts"
    print(f"Changed {changed}")  # never the raw before/after value, even here
    print(f"  check_freshness -> {verdict['status']} at {verdict['changed_at']}")
    print(f"  list_stale -> {len(stale)} claim(s)")
    for row in stale:
        print(f"    claim_id={row['claim_id']} source={row['source_key']} stale_at={row['stale_at']}")


if __name__ == "__main__":
    main()
