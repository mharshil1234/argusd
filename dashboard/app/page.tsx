"use client";

import { useEffect, useState } from "react";
import type { ClaimsResponse, DashboardClaim } from "../lib/claims-reader";

const initialResponse: ClaimsResponse = { state: "waiting", claims: [], summary: { total: 0, fresh: 0, stale: 0 }, generatedAt: "", message: "Connecting to Argusd…" };

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(date);
}

function ClaimRow({ claim }: { claim: DashboardClaim }) {
  return (
    <article className="claim-row">
      <div className="claim-copy"><p>{claim.text}</p><div className="claim-source"><span>Source</span><code>{claim.sourceKey}</code></div></div>
      <div className="claim-meta">
        <span className={`status status-${claim.status}`} aria-label={`Claim status: ${claim.status}`}><span className="status-dot" aria-hidden="true" />{claim.status}</span>
        <time dateTime={claim.staleAt ?? claim.createdAt}>{claim.status === "stale" ? "Changed" : "Recorded"} {formatTimestamp(claim.staleAt ?? claim.createdAt)}</time>
      </div>
    </article>
  );
}

export default function Home() {
  const [data, setData] = useState<ClaimsResponse>(initialResponse);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    let inFlight = false;
    let controller: AbortController | undefined;
    async function refresh() {
      if (inFlight) return;
      inFlight = true;
      controller = new AbortController();
      try {
        const response = await fetch("/api/claims", { cache: "no-store", signal: controller.signal });
        if (!response.ok) throw new Error(`Dashboard API returned ${response.status}`);
        const nextData = (await response.json()) as ClaimsResponse;
        if (active) setData(nextData);
      } catch (error) {
        if (active && !(error instanceof DOMException && error.name === "AbortError")) {
          setData({ state: "error", claims: [], summary: { total: 0, fresh: 0, stale: 0 }, generatedAt: new Date().toISOString(), message: error instanceof Error ? error.message : "Unable to refresh claims." });
        }
      } finally {
        inFlight = false;
        if (active) setLoading(false);
      }
    }
    void refresh();
    const timer = window.setInterval(() => void refresh(), 1_000);
    return () => { active = false; window.clearInterval(timer); controller?.abort(); };
  }, []);

  const connectionLabel = loading ? "Connecting" : data.state === "error" ? "Read error" : data.state === "waiting" ? "Waiting for DB" : "SQLite connected";

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <div><p className="eyebrow">ARGUSD / LIVE FRESHNESS MONITOR</p><h1>Claims dashboard</h1><p className="lede">See which agent beliefs still match their underlying source.</p></div>
        <div className={`connection connection-${data.state}`} aria-live="polite"><span className="connection-dot" aria-hidden="true" /><div><strong>{connectionLabel}</strong><span>{data.generatedAt ? `Last checked ${formatTimestamp(data.generatedAt)}` : "Starting poller"}</span></div></div>
      </header>

      <section className="summary-grid" aria-label="Claim freshness summary">
        <article className="summary-card"><span>Tracked claims</span><strong>{data.summary.total}</strong><p>Across monitored source keys</p></article>
        <article className="summary-card summary-fresh"><span>Fresh</span><strong>{data.summary.fresh}</strong><p>Current against their source</p></article>
        <article className="summary-card summary-stale"><span>Stale</span><strong>{data.summary.stale}</strong><p>Changed since they were recorded</p></article>
      </section>

      <section className="claims-panel" aria-labelledby="claims-heading" aria-busy={loading}>
        <div className="panel-header"><div><p className="section-kicker">READ-ONLY SQLITE VIEW</p><h2 id="claims-heading">Tracked claims</h2></div><div className="panel-meta"><span>{data.summary.total} total</span><span className="poll-rate">POLLING · 1s</span></div></div>
        {loading ? <div className="state-card" role="status"><span className="spinner" />Reading claims…</div>
          : data.state !== "ready" ? <div className={`state-card state-${data.state}`} role="status" aria-live="polite"><strong>{data.state === "waiting" ? "Argusd is ready for data" : "Claims are temporarily unavailable"}</strong><p>{data.message}</p>{data.state === "waiting" && <code>python -c &quot;from server.db import connect, init_db; c=connect(); init_db(c)&quot;</code>}</div>
          : data.claims.length === 0 ? <div className="state-card" role="status"><strong>No claims recorded yet</strong><p>Call the MCP record_claim tool to populate this view.</p></div>
          : <div className="claims-list">{data.claims.map((claim) => <ClaimRow key={claim.id} claim={claim} />)}</div>}
      </section>

      <footer><span>Hashes and raw config values never leave the server.</span><span>WebSocket events arrive in Hours 8–14.</span></footer>
    </main>
  );
}
