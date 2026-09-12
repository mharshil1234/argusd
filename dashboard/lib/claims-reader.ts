import { existsSync } from "node:fs";
import path from "node:path";

import Database from "better-sqlite3";

export type ClaimStatus = "fresh" | "stale";
export type DashboardClaim = { id: number; text: string; sourceKey: string; createdAt: string; status: ClaimStatus; staleAt: string | null };
export type ClaimsResponse = { state: "ready" | "waiting" | "error"; claims: DashboardClaim[]; summary: { total: number; fresh: number; stale: number }; generatedAt: string; message?: string };
type ClaimRow = { id: number; text: string; source_key: string; created_at: string; status: string; stale_at: string | null };

const emptySummary = { total: 0, fresh: 0, stale: 0 };

export function resolveDatabasePath(): string {
  return process.env.ARGUSD_DB_PATH ? path.resolve(process.env.ARGUSD_DB_PATH) : path.resolve(process.cwd(), "..", "argusd.db");
}

export function readClaims(dbPath = resolveDatabasePath()): ClaimsResponse {
  const generatedAt = new Date().toISOString();
  if (!existsSync(dbPath)) return { state: "waiting", claims: [], summary: emptySummary, generatedAt, message: "Waiting for the Argusd database to be created." };

  let database: Database.Database | undefined;
  try {
    database = new Database(dbPath, { readonly: true, fileMustExist: true });
    const hasClaimsTable = database.prepare("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'claims'").get();
    if (!hasClaimsTable) return { state: "waiting", claims: [], summary: emptySummary, generatedAt, message: "Waiting for the claims table to be initialized." };

    const rows = database.prepare(`SELECT id, text, source_key, created_at, status, stale_at FROM claims ORDER BY created_at DESC, id DESC`).all() as ClaimRow[];
    const claims = rows.map((row): DashboardClaim => {
      if (row.status !== "fresh" && row.status !== "stale") throw new Error(`Unsupported claim status: ${row.status}`);
      return { id: row.id, text: row.text, sourceKey: row.source_key, createdAt: row.created_at, status: row.status, staleAt: row.stale_at };
    });
    const fresh = claims.filter((claim) => claim.status === "fresh").length;
    return { state: "ready", claims, summary: { total: claims.length, fresh, stale: claims.length - fresh }, generatedAt };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown SQLite error";
    return { state: "error", claims: [], summary: emptySummary, generatedAt, message: `Unable to read claims: ${message}` };
  } finally {
    database?.close();
  }
}
