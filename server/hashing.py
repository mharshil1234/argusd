"""Hash functions for the sources Argusd watches.

Build priority per CLAUDE.md: file content and git state are implemented
here; per-key config hashing is stubbed until the Hours 14-20 phase.
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
    ".env:KEY" -> env value (not yet implemented, hour 14-20).
    anything else -> treated as a file path.
    """
    if source_key.startswith("git:"):
        return hash_git_state(REPO_ROOT)
    if source_key.startswith(".env:"):
        raise NotImplementedError("env-key hashing lands in the config-parsing phase")
    path = Path(source_key)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return hash_file(path)
