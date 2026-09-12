import fs from "node:fs";
import path from "node:path";

import { readClaims, resolveDatabasePath } from "../../../lib/claims";
import type { ClaimsResponse } from "../../../lib/claims";

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
      const send = (payload: ClaimsResponse) => {
        if (closed) return;
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`));
      };

      const scheduleRefresh = () => {
        if (debounceTimer) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => send(readClaims()), DEBOUNCE_MS);
      };

      send(readClaims()); // initial snapshot on connect

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
