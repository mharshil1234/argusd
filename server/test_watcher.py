#!/usr/bin/env python3
"""Standalone proof that the watcher invalidates claims on its own.

Run: python server/test_watcher.py

Two parts, each using a disposable scratch tree so it's safe to re-run and
never touches the real project's files or git state:

1. File-content: record a claim, edit the watched file, confirm the claim
   flips to stale via the watcher alone -- no check_freshness call.
2. Git-state: record a "git:HEAD" claim against a scratch git repo, make a
   commit, confirm the claim flips to stale via the watcher alone.
"""

import subprocess
import sys
import tempfile
import time
from pathlib import Path

from watchdog.observers import Observer

from db import connect, init_db, insert_claim, get_claim
from hashing import hash_file, hash_git_state
from watcher import Debouncer, RepoChangeHandler, GitFileHandler, GIT_SOURCE_KEY

POLL_TIMEOUT = 5.0
POLL_INTERVAL = 0.05


def check(label: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        sys.exit(1)


def wait_until_stale(conn, claim_id: int, timeout: float = POLL_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        claim = get_claim(conn, claim_id)
        if claim["status"] == "stale":
            return True
        time.sleep(POLL_INTERVAL)
    return False


def run_git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def test_file_content_invalidation(tmp_path: Path) -> None:
    repo_root = tmp_path / "filerepo"
    repo_root.mkdir()
    scratch_file = repo_root / "auth.ts"
    scratch_file.write_text("export function login() { return true; }\n")

    db_path = tmp_path / "file_test.db"
    conn = connect(db_path)
    init_db(conn)

    source_key = "auth.ts"  # repo-root-relative, matching the watcher's primary form
    claim_id = insert_claim(
        conn,
        text="no other files import this",
        source_key=source_key,
        source_hash=hash_file(scratch_file),
    )
    print(f"Recorded claim {claim_id} on {source_key}")

    debouncer = Debouncer(0.05)
    observer = Observer()
    observer.schedule(RepoChangeHandler(debouncer, repo_root), str(repo_root), recursive=True)
    observer.start()
    try:
        # Point the watcher's invalidation functions at this scratch DB.
        import os

        os.environ["ARGUSD_DB_PATH"] = str(db_path)

        scratch_file.write_text("export function login() { return false; }\n")

        stale = wait_until_stale(conn, claim_id)
        check("file-content claim flips to stale via watcher alone", stale)
    finally:
        observer.unschedule_all()
        observer.stop()
        observer.join()
        debouncer.close()
        conn.close()


def test_git_state_invalidation(tmp_path: Path) -> None:
    repo_root = tmp_path / "gitrepo"
    repo_root.mkdir()
    run_git("init", cwd=repo_root)
    run_git("config", "user.email", "test@example.com", cwd=repo_root)
    run_git("config", "user.name", "Argusd Test", cwd=repo_root)

    (repo_root / "README.md").write_text("initial\n")
    run_git("add", "-A", cwd=repo_root)
    run_git("commit", "-m", "initial commit", cwd=repo_root)

    db_path = tmp_path / "git_test.db"
    conn = connect(db_path)
    init_db(conn)

    baseline_hash = hash_git_state(repo_root)
    claim_id = insert_claim(
        conn,
        text="you're on main with no uncommitted changes",
        source_key=GIT_SOURCE_KEY,
        source_hash=baseline_hash,
    )
    print(f"Recorded claim {claim_id} on {GIT_SOURCE_KEY}")

    import os

    os.environ["ARGUSD_DB_PATH"] = str(db_path)

    debouncer = Debouncer(0.05)
    observer = Observer()
    git_dir = repo_root / ".git"
    observer.schedule(GitFileHandler(debouncer, repo_root, {"HEAD", "index"}), str(git_dir), recursive=False)
    logs_dir = git_dir / "logs"
    if logs_dir.exists():
        observer.schedule(GitFileHandler(debouncer, repo_root, {"HEAD"}), str(logs_dir), recursive=False)
    observer.start()
    try:
        (repo_root / "second.txt").write_text("second\n")
        run_git("add", "-A", cwd=repo_root)
        run_git("commit", "-m", "second commit", cwd=repo_root)

        stale = wait_until_stale(conn, claim_id)
        check("git-state claim flips to stale via watcher alone", stale)
    finally:
        observer.unschedule_all()
        observer.stop()
        observer.join()
        debouncer.close()
        conn.close()


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        test_file_content_invalidation(tmp_path)
        test_git_state_invalidation(tmp_path)

    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
