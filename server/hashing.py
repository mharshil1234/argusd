"""Hash functions for the sources Argusd watches.

Build priority per CLAUDE.md: file content first (this module), then
git state, then per-key config hashing — both stubbed here for now.
"""

import hashlib
from pathlib import Path


def hash_file(path: Path | str) -> str:
    """SHA256 of a file's full bytes."""
    data = Path(path).read_bytes()
    return hashlib.sha256(data).hexdigest()


def hash_git_state(repo_path: Path | str = ".") -> str:
    """Stub: hash of HEAD commit + branch name + working-tree-clean flag.

    TODO(hour 8-14): shell out to `git rev-parse HEAD`, `git branch
    --show-current`, and `git status --porcelain`, then hash the
    concatenation.
    """
    raise NotImplementedError("git state hashing lands in the watcher phase")


def hash_env_value(value: str) -> str:
    """SHA256 of a single .env value (never the raw value itself)."""
    return hashlib.sha256(value.strip().encode()).hexdigest()
