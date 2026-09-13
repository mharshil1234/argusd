import { existsSync } from "node:fs";
import path from "node:path";

import Database from "better-sqlite3";

export type ClaimStatus = "fresh" | "stale";
export type ClaimSeverity = "low" | "medium" | "high" | "critical";
export type DashboardClaim = { id: number; text: string; sourceKey: string; createdAt: string; agentId: string; sessionId: string | null; severity: ClaimSeverity; recommendedAction: string; status: ClaimStatus; staleAt: string | null };
export type ClaimsResponse = { state: "ready" | "waiting" | "error"; claims: DashboardClaim[]; summary: { total: number; fresh: number; stale: number }; generatedAt: string; message?: string };
export type InvalidationEvent = { id: number; sourceKey: string; occurredAt: string; invalidatedCount: number };
export type DashboardSnapshot = ClaimsResponse & { events: InvalidationEvent[] };
type ClaimRow = { id: number; text: string; source_key: string; created_at: string; agent_id: string; session_id: string | null; severity: string; recommended_action: string; status: string; stale_at: string | null };
type EventRow = { id: number; source_key: string; occurred_at: string; invalidated_count: number };

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

    const columns = new Set((database.prepare("PRAGMA table_info(claims)").all() as { name: string }[]).map((column) => column.name));
    const ownershipColumns = columns.has("agent_id") && columns.has("session_id")
      ? "agent_id, session_id"
      : "'unattributed' AS agent_id, NULL AS session_id";
    const riskColumns = columns.has("severity") && columns.has("recommended_action")
      ? "severity, recommended_action"
      : "'medium' AS severity, 'reverify_before_continue' AS recommended_action";
    const rows = database.prepare(`SELECT id, text, source_key, created_at, ${ownershipColumns}, ${riskColumns}, status, stale_at FROM claims ORDER BY created_at DESC, id DESC`).all() as ClaimRow[];
    const claims = rows.map((row): DashboardClaim => {
      if (row.status !== "fresh" && row.status !== "stale") throw new Error(`Unsupported claim status: ${row.status}`);
      if (!["low", "medium", "high", "critical"].includes(row.severity)) throw new Error(`Unsupported claim severity: ${row.severity}`);
      return { id: row.id, text: row.text, sourceKey: row.source_key, createdAt: row.created_at, agentId: row.agent_id, sessionId: row.session_id, severity: row.severity as ClaimSeverity, recommendedAction: row.recommended_action, status: row.status, staleAt: row.stale_at };
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

export function readEvents(dbPath = resolveDatabasePath()): InvalidationEvent[] {
  if (!existsSync(dbPath)) return [];
  let database: Database.Database | undefined;
  try {
    database = new Database(dbPath, { readonly: true, fileMustExist: true });
    const hasEventsTable = database.prepare("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'invalidation_events'").get();
    if (!hasEventsTable) return [];
    const rows = database.prepare(`SELECT id, source_key, occurred_at, invalidated_count FROM invalidation_events ORDER BY occurred_at DESC, id DESC LIMIT 20`).all() as EventRow[];
    return rows.map((row) => ({ id: row.id, sourceKey: row.source_key, occurredAt: row.occurred_at, invalidatedCount: row.invalidated_count }));
  } finally {
    database?.close();
  }
}
