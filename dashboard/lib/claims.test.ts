import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import Database from "better-sqlite3";

import { readClaims } from "./claims-reader";

const schema = `
CREATE TABLE claims (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  text TEXT NOT NULL,
  source_key TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'fresh',
  stale_at TEXT
);`;

function withTempPath(run: (dbPath: string) => void) {
  const directory = mkdtempSync(path.join(tmpdir(), "argusd-dashboard-"));
  try {
    run(path.join(directory, "argusd.db"));
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}

test("returns a waiting state when the database is missing", () => {
  withTempPath((dbPath) => {
    const result = readClaims(dbPath);
    assert.equal(result.state, "waiting");
    assert.deepEqual(result.claims, []);
  });
});

test("returns a waiting state when claims have not been initialized", () => {
  withTempPath((dbPath) => {
    const database = new Database(dbPath);
    database.close();
    assert.equal(readClaims(dbPath).state, "waiting");
  });
});

test("normalizes, sorts, and summarizes claims without exposing hashes", () => {
  withTempPath((dbPath) => {
    const database = new Database(dbPath);
    database.exec(schema);
    const insert = database.prepare(
      `INSERT INTO claims (text, source_key, source_hash, created_at, status, stale_at)
       VALUES (?, ?, ?, ?, ?, ?)`,
    );
    insert.run("older fresh claim", "auth.ts", "secret-one", "2026-01-01T10:00:00Z", "fresh", null);
    insert.run("new stale claim", ".env:PORT", "secret-two", "2026-01-01T11:00:00Z", "stale", "2026-01-01T11:01:00Z");
    database.close();

    const result = readClaims(dbPath);
    assert.equal(result.state, "ready");
    assert.deepEqual(result.summary, { total: 2, fresh: 1, stale: 1 });
    assert.deepEqual(result.claims.map((claim) => claim.text), ["new stale claim", "older fresh claim"]);
    assert.equal(result.claims[1].staleAt, null);
    assert.equal(JSON.stringify(result).includes("secret-"), false);
    assert.equal("sourceHash" in result.claims[0], false);
  });
});

test("reports malformed databases without throwing", () => {
  withTempPath((dbPath) => {
    writeFileSync(dbPath, "not a sqlite database");
    const result = readClaims(dbPath);
    assert.equal(result.state, "error");
    assert.match(result.message ?? "", /Unable to read claims/);
  });
});
