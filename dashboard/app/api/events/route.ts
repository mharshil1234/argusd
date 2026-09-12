import fs from "node:fs";
import path from "node:path";

import { readClaims, readEvents, resolveDatabasePath } from "../../../lib/claims";
import type { DashboardSnapshot } from "../../../lib/claims";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const HEARTBEAT_MS = 20_000;
const DEBOUNCE_MS = 150;

export function GET() {
  const encoder = new TextEncoder();
  const dbPath = resolveDatabasePath();
  const dbDir = path.dirname(dbPath);
  const dbName = path.basename(dbPath);

  let debounceTimer: ReturnType<typeof setTimeout> | null = null;
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  let dirWatcher: fs.FSWatcher | null = null;
  let closed = false;

  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const snapshot = (): DashboardSnapshot => {
        const claims = readClaims(dbPath);
        try {
          return { ...claims, events: claims.state === "ready" ? readEvents(dbPath) : [] };
        } catch (error) {
          const message = error instanceof Error ? error.message : "Unknown SQLite error";
          return { state: "error", claims: [], events: [], summary: { total: 0, fresh: 0, stale: 0 }, generatedAt: new Date().toISOString(), message: `Unable to read invalidation events: ${message}` };
        }
      };
      const send = (payload: DashboardSnapshot) => {
        if (closed) return;
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`));
      };

      const scheduleRefresh = () => {
        if (debounceTimer) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => send(snapshot()), DEBOUNCE_MS);
      };

      send(snapshot()); // initial snapshot on connect

      try {
        dirWatcher = fs.watch(dbDir, { persistent: false }, (_event, filename) => {
          if (!filename || filename.startsWith(dbName)) scheduleRefresh();
        });
      } catch {
        // dbDir doesn't exist yet; client already has the initial "waiting" snapshot above.
        dirWatcher = null;
      }

      heartbeatTimer = setInterval(() => {
        if (!closed) controller.enqueue(encoder.encode(": heartbeat\n\n"));
      }, HEARTBEAT_MS);
    },
    cancel() {
      closed = true;
      if (debounceTimer) clearTimeout(debounceTimer);
      if (heartbeatTimer) clearInterval(heartbeatTimer);
      dirWatcher?.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-store, max-age=0",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
