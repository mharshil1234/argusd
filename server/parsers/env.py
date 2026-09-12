"""Per-key .env parsing and hashing.

Hashes each key's value individually (never the whole file) so editing one
key never invalidates a claim about an unrelated key. Raw values are never
returned or stored -- only their hashes.
"""

import os
from pathlib import Path

from hashing import hash_env_value

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_SOURCE_PREFIX = ".env:"


def resolve_env_path() -> Path:
    """The .env file claims are hashed against, overridable like ARGUSD_DB_PATH."""
    return Path(os.environ.get("ARGUSD_ENV_PATH", str(REPO_ROOT / ".env")))


def parse_env_hashes(path: Path | str) -> dict[str, str]:
    """Map each KEY in a .env file to a hash of its current value."""
    hashes = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            hashes[key.strip()] = hash_env_value(value.strip())
    return hashes
