"""Hash functions for the sources Argusd watches.

Hashes file content, git state, and individual .env keys (see
parsers/env.py for the per-key .env parsing).
"""

import hashlib
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def hash_file(path: Path | str) -> str:
    """SHA256 of a file's full bytes."""
    data = Path(path).read_bytes()
    return hashlib.sha256(data).hexdigest()


def hash_git_state(repo_path: Path | str = ".") -> str:
    """Hash of HEAD commit + branch name + working-tree-clean flag."""

    def run(*args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    head = run("rev-parse", "HEAD")
    branch = run("branch", "--show-current")
    status = run("status", "--porcelain")
    combined = f"{head}|{branch}|{status}"
    return hashlib.sha256(combined.encode()).hexdigest()


def hash_env_value(value: str) -> str:
    """SHA256 of a single .env value (never the raw value itself)."""
    return hashlib.sha256(value.strip().encode()).hexdigest()


def hash_source(source_key: str) -> str:
    """Dispatch a source_key to the right hasher and return its current hash.

    "git:..." -> git state.
    ".env:KEY" -> env value.
    anything else -> treated as a file path.
    """
    if source_key.startswith("git:"):
        return hash_git_state(REPO_ROOT)
    if source_key.startswith(".env:"):
        from parsers.env import ENV_SOURCE_PREFIX, parse_env_hashes, resolve_env_path

        key = source_key[len(ENV_SOURCE_PREFIX):]
        hashes = parse_env_hashes(resolve_env_path())
        if key not in hashes:
            raise KeyError(f"no such .env key: {key}")
        return hashes[key]
    path = Path(source_key)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return hash_file(path)
