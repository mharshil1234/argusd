#!/usr/bin/env python3
"""Integration tests for the isolated seed/change demo workflow."""

import json
import os
import sqlite3
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SEED = REPO_ROOT / "demo" / "seed_claims.py"
TRIGGER = REPO_ROOT / "demo" / "trigger_change.py"


class DemoWorkflowTests(unittest.TestCase):
    def run_script(self, script: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *args],
            cwd=REPO_ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_seed_isolated_change_and_repeat_behavior(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="argusd-demo-test-"))
        try:
            workspace = tmp / "run"
            seed = self.run_script(SEED, "--workspace", str(workspace))
            self.assertEqual(seed.returncode, 0, seed.stderr)

            manifest = json.loads((workspace / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(set(manifest["claims"]), {"auth", "routes", "env"})
            self.assertEqual(manifest["claims"]["env"]["source"], ".env:PORT")
            self.assertNotIn("source_hash", json.dumps(manifest))

            database = sqlite3.connect(workspace / "argusd.db")
            try:
                rows = database.execute("SELECT status FROM claims ORDER BY id").fetchall()
            finally:
                database.close()
            self.assertEqual(rows, [("fresh",), ("fresh",), ("fresh",)])

            duplicate = self.run_script(SEED, "--workspace", str(workspace))
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn("--reset", duplicate.stderr)

            auth_before = (workspace / "auth.ts").read_bytes()
            routes_before = (workspace / "routes.ts").read_bytes()
            trigger = self.run_script(TRIGGER, "--workspace", str(workspace), "--claim", "auth")
            self.assertEqual(trigger.returncode, 0, trigger.stderr)
            self.assertIn("check_freshness -> stale", trigger.stdout)
            self.assertEqual((workspace / "routes.ts").read_bytes(), routes_before)
            self.assertNotEqual((workspace / "auth.ts").read_bytes(), auth_before)
            self.assertIn(
                'import { source } from "./auth.ts";',
                (workspace / "login.ts").read_text(encoding="utf-8"),
            )

            database = sqlite3.connect(workspace / "argusd.db")
            try:
                rows = database.execute("SELECT status, stale_at FROM claims ORDER BY id").fetchall()
            finally:
                database.close()
            self.assertEqual(rows[0][0], "stale")
            self.assertIsNotNone(rows[0][1])
            self.assertEqual(rows[1], ("fresh", None))
            self.assertEqual(rows[2], ("fresh", None))

            env_before = (workspace / ".env").read_text(encoding="utf-8")
            trigger = self.run_script(TRIGGER, "--workspace", str(workspace), "--claim", "env")
            self.assertEqual(trigger.returncode, 0, trigger.stderr)
            self.assertIn("check_freshness -> stale", trigger.stdout)
            env_after = (workspace / ".env").read_text(encoding="utf-8")
            self.assertNotEqual(env_after, env_before)
            self.assertIn("PORT=4000", env_after)
            self.assertNotIn("4000", trigger.stdout)  # raw value never printed

            # The script only flips the claim stale -- it deliberately does
            # not re-record an updated belief. That's the live agent's
            # self-audit habit's job (CLAUDE.md), kept consistent with how
            # --claim auth/routes already behave (stale and stopped there).
            database = sqlite3.connect(workspace / "argusd.db")
            try:
                rows = database.execute(
                    "SELECT id, source_key, status, stale_at FROM claims ORDER BY id"
                ).fetchall()
            finally:
                database.close()
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0][2], "stale")  # auth: unchanged from before
            self.assertEqual(rows[1][2:], ("fresh", None))  # routes: still untouched
            self.assertEqual(rows[2][2], "stale")  # env: just flipped, not re-recorded
            self.assertIsNotNone(rows[2][3])
        finally:
            for _ in range(30):
                try:
                    shutil.rmtree(tmp)
                    break
                except PermissionError:
                    time.sleep(0.1)
            else:
                self.fail(f"demo workspace remained locked: {tmp}")


if __name__ == "__main__":
    unittest.main()
