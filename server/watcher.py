#!/usr/bin/env python3
"""Passive filesystem + git watcher.

Runs independently of the MCP server and any agent call. Watches the repo
tree for file edits and the .git directory for commit/branch/index
changes, rehashes affected sources, and flips dependent claims stale the
instant a source's hash changes -- zero agent tokens spent.

Run: python server/watcher.py   (Ctrl+C to stop)
"""

import fnmatch
import logging
import os
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import db
from hashing import hash_file, hash_git_state

REPO_ROOT = Path(__file__).resolve().parent.parent
GIT_DIR = REPO_ROOT / ".git"
GIT_SOURCE_KEY = "git:HEAD"
DEBOUNCE_SECONDS = 0.3
GIT_POLL_INTERVAL_SECONDS = float(os.environ.get("ARGUSD_GIT_POLL_INTERVAL", "3"))

IGNORE_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".next",
    "out",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
IGNORE_FILE_GLOBS = (
    "argusd.db",
    "argusd.db-journal",
    "argusd.db-wal",
    "argusd.db-shm",
    "*.sqlite",
    "*.sqlite3",
    "*.sqlite-journal",
    "*.swp",
    "*.swx",
    "*~",
    "*.tmp",
    "*.tsbuildinfo",
)

log = logging.getLogger("argusd.watcher")


def is_ignored(path: Path) -> bool:
    if any(part in IGNORE_DIR_NAMES for part in path.parts):
        return True
    return any(fnmatch.fnmatch(path.name, pattern) for pattern in IGNORE_FILE_GLOBS)


def candidate_source_keys(abs_path: Path, repo_root: Path) -> list[str]:
    """Neither record_claim nor hash_source normalizes source_key spelling,
    so try both plausible forms a claim might have been recorded under."""
    keys = []
    try:
        keys.append(abs_path.resolve().relative_to(repo_root).as_posix())
    except ValueError:
        pass
    keys.append(str(abs_path.resolve()))
    return keys


def _get_conn():
    db_path = Path(os.environ.get("ARGUSD_DB_PATH", db.DEFAULT_DB_PATH))
    conn = db.connect(db_path)
    db.init_db(conn)
    return conn


def invalidate_file_source(source_key: str, repo_root: Path) -> None:
    conn = _get_conn()
    try:
        source = db.get_source(conn, source_key)
        if source is None:
            return
        candidate_path = Path(source_key)
        if not candidate_path.is_absolute():
            candidate_path = repo_root / candidate_path
        try:
            new_hash = hash_file(candidate_path)
        except FileNotFoundError:
            new_hash = None
        if new_hash == source["last_hash"]:
            return
        ids = db.mark_source_claims_stale(conn, source_key)
        if new_hash is not None:
            db.upsert_source(conn, source_key, new_hash)
        if ids:
            log.info(
                "[STALE] %s changed at %s -> invalidated claim ids %s",
                source_key,
                db.now_iso(),
                ids,
            )
    finally:
        conn.close()


def invalidate_git_source(repo_root: Path) -> None:
    conn = _get_conn()
    try:
        source = db.get_source(conn, GIT_SOURCE_KEY)
        if source is None:
            return
        try:
            new_hash = hash_git_state(repo_root)
        except Exception:
            log.exception("failed to hash git state for %s", repo_root)
            return
        if new_hash == source["last_hash"]:
            return
        ids = db.mark_source_claims_stale(conn, GIT_SOURCE_KEY)
        db.upsert_source(conn, GIT_SOURCE_KEY, new_hash)
        if ids:
            log.info(
                "[STALE] %s changed at %s -> invalidated claim ids %s",
                GIT_SOURCE_KEY,
                db.now_iso(),
                ids,
            )
    finally:
        conn.close()


class Debouncer:
    """Coalesces bursty events for the same key into one delayed call."""

    def __init__(self, delay: float):
        self.delay = delay
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def trigger(self, key: str, fn) -> None:
        with self._lock:
            existing = self._timers.pop(key, None)
            if existing is not None:
                existing.cancel()
            timer = threading.Timer(self.delay, self._fire, args=(key, fn))
            timer.daemon = True
            self._timers[key] = timer
            timer.start()

    def _fire(self, key: str, fn) -> None:
        with self._lock:
            self._timers.pop(key, None)
        fn()


class RepoChangeHandler(FileSystemEventHandler):
    """Watches ordinary repo files for content changes."""

    def __init__(self, debouncer: Debouncer, repo_root: Path):
        self.debouncer = debouncer
        self.repo_root = repo_root

    def _handle(self, raw_path: str) -> None:
        path = Path(raw_path)
        if is_ignored(path):
            return
        self.debouncer.trigger(str(path), lambda: self._process(path))
        # Editing a tracked file can dirty the working tree without
        # touching any .git/* file, so recheck git state on every edit too.
        self.debouncer.trigger(
            GIT_SOURCE_KEY, lambda: invalidate_git_source(self.repo_root)
        )

    def _process(self, path: Path) -> None:
        for key in candidate_source_keys(path, self.repo_root):
            invalidate_file_source(key, self.repo_root)

    def on_modified(self, event):
        if not event.is_directory:
            self._handle(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self._handle(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._handle(event.dest_path)


class GitFileHandler(FileSystemEventHandler):
    """Watches specific .git files (HEAD, index, logs/HEAD) for git-state changes."""

    def __init__(self, debouncer: Debouncer, repo_root: Path, watch_names: set[str]):
        self.debouncer = debouncer
        self.repo_root = repo_root
        self.watch_names = watch_names

    def _maybe_trigger(self, raw_path: str) -> None:
        if Path(raw_path).name in self.watch_names:
            self.debouncer.trigger(
                GIT_SOURCE_KEY, lambda: invalidate_git_source(self.repo_root)
            )

    def on_modified(self, event):
        if not event.is_directory:
            self._maybe_trigger(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self._maybe_trigger(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._maybe_trigger(event.dest_path)


def build_observer(repo_root: Path, git_dir: Path, debouncer: Debouncer) -> Observer:
    observer = Observer()
    observer.schedule(
        RepoChangeHandler(debouncer, repo_root), str(repo_root), recursive=True
    )
    if git_dir.exists():
        observer.schedule(
            GitFileHandler(debouncer, repo_root, {"HEAD", "index"}),
            str(git_dir),
            recursive=False,
        )
        logs_dir = git_dir / "logs"
        if logs_dir.exists():
            observer.schedule(
                GitFileHandler(debouncer, repo_root, {"HEAD"}),
                str(logs_dir),
                recursive=False,
            )
    return observer


def git_poll_loop(repo_root: Path, stop_event: threading.Event) -> None:
    while not stop_event.wait(GIT_POLL_INTERVAL_SECONDS):
        invalidate_git_source(repo_root)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    db_path = os.environ.get("ARGUSD_DB_PATH", str(db.DEFAULT_DB_PATH))
    log.info("Argusd watcher starting: repo_root=%s db=%s", REPO_ROOT, db_path)

    debouncer = Debouncer(DEBOUNCE_SECONDS)
    observer = build_observer(REPO_ROOT, GIT_DIR, debouncer)
    observer.start()

    stop_event = threading.Event()
    poll_thread = threading.Thread(
        target=git_poll_loop, args=(REPO_ROOT, stop_event), daemon=True
    )
    poll_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Argusd watcher stopping...")
    finally:
        stop_event.set()
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
