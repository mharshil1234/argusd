"use client";

import { useEffect, useState } from "react";
import type { DashboardClaim, DashboardSnapshot, InvalidationEvent } from "../lib/claims-reader";

const initialResponse: DashboardSnapshot = { state: "waiting", claims: [], events: [], summary: { total: 0, fresh: 0, stale: 0 }, generatedAt: "", message: "Connecting to Argusd…" };

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(date);
}

function formatAction(action: string): string {
  return action.split("_").join(" ");
}

function ClaimRow({ claim }: { claim: DashboardClaim }) {
  const owner = claim.sessionId ? `${claim.agentId} / ${claim.sessionId}` : claim.agentId;
  return (
    <article className="claim-row">
      <div className="claim-copy"><p>{claim.text}</p><div className="claim-context"><div className="claim-source"><span>Source</span><code>{claim.sourceKey}</code></div><div className="claim-owner"><span>Owner</span><code title={owner}>{owner}</code></div></div>{claim.status === "stale" && <p className="claim-action"><span>Recommended</span>{formatAction(claim.recommendedAction)}</p>}</div>
      <div className="claim-meta">
        <span className={`status status-${claim.status}`} aria-label={`Claim status: ${claim.status}`}><span className="status-dot" aria-hidden="true" />{claim.status}</span>
        <span className={`severity severity-${claim.severity}`} aria-label={`Claim severity: ${claim.severity}`}>{claim.severity}</span>
        <time dateTime={claim.staleAt ?? claim.createdAt}>{claim.status === "stale" ? "Changed" : "Recorded"} {formatTimestamp(claim.staleAt ?? claim.createdAt)}</time>
      </div>
    </article>
  );
}

function EventRow({ event }: { event: InvalidationEvent }) {
  const countLabel = `${event.invalidatedCount} claim${event.invalidatedCount === 1 ? "" : "s"}`;
  return <li className="event-row"><span className="event-mark" aria-hidden="true" /><div><p><code>{event.sourceKey}</code> changed <span aria-hidden="true">→</span> invalidated {countLabel}</p><time dateTime={event.occurredAt}>{formatTimestamp(event.occurredAt)}</time></div></li>;
}

type FeedState = "connecting" | "open" | "error";

export default function Home() {
  const [data, setData] = useState<DashboardSnapshot>(initialResponse);
  const [loading, setLoading] = useState(true);
  const [feedState, setFeedState] = useState<FeedState>("connecting");

  useEffect(() => {
    let active = true;
    const source = new EventSource("/api/events");

    source.onopen = () => {
      if (active) setFeedState("open");
    };
    source.onmessage = (event) => {
      if (!active) return;
      try {
        setData(JSON.parse(event.data) as DashboardSnapshot);
        setLoading(false);
        setFeedState("open");
      } catch {
        // malformed frame; ignore, the next message will recover
      }
    };
    source.onerror = () => {
      // EventSource retries on its own; onopen fires again once it reconnects.
      if (active) setFeedState("error");
    };

    return () => {
      active = false;
      source.close();
    };
  }, []);

  const connectionLabel = loading ? "Connecting" : feedState === "error" ? "Reconnecting…" : data.state === "error" ? "Read error" : data.state === "waiting" ? "Waiting for DB" : "Live";

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <div><p className="eyebrow">ARGUSD / LIVE FRESHNESS MONITOR</p><h1>Claims dashboard</h1><p className="lede">See which agent beliefs still match their underlying source.</p></div>
        <div className={`connection connection-${data.state}`} aria-live="polite"><span className="connection-dot" aria-hidden="true" /><div><strong>{connectionLabel}</strong><span>{data.generatedAt ? `Updated ${formatTimestamp(data.generatedAt)}` : "Connecting to live feed"}</span></div></div>
      </header>

      <section className="summary-grid" aria-label="Claim freshness summary">
        <article className="summary-card"><span>Tracked claims</span><strong>{data.summary.total}</strong><p>Across monitored source keys</p></article>
        <article className="summary-card summary-fresh"><span>Fresh</span><strong>{data.summary.fresh}</strong><p>Current against their source</p></article>
        <article className="summary-card summary-stale"><span>Stale</span><strong>{data.summary.stale}</strong><p>Changed since they were recorded</p></article>
      </section>

      <section className="claims-panel" aria-labelledby="claims-heading" aria-busy={loading}>
        <div className="panel-header"><div><p className="section-kicker">READ-ONLY SQLITE VIEW</p><h2 id="claims-heading">Tracked claims</h2></div><div className="panel-meta"><span>{data.summary.total} total</span><span className="poll-rate">{feedState === "open" ? "LIVE" : feedState === "error" ? "RECONNECTING" : "CONNECTING"}</span></div></div>
        {loading ? <div className="state-card" role="status"><span className="spinner" />Reading claims…</div>
          : data.state !== "ready" ? <div className={`state-card state-${data.state}`} role="status" aria-live="polite"><strong>{data.state === "waiting" ? "Argusd is ready for data" : "Claims are temporarily unavailable"}</strong><p>{data.message}</p>{data.state === "waiting" && <code>python -c &quot;from server.db import connect, init_db; c=connect(); init_db(c)&quot;</code>}</div>
          : data.claims.length === 0 ? <div className="state-card" role="status"><strong>No claims recorded yet</strong><p>Call the MCP record_claim tool to populate this view.</p></div>
           : <div className="claims-list">{data.claims.map((claim) => <ClaimRow key={claim.id} claim={claim} />)}</div>}
      </section>

      <section className="events-panel" aria-labelledby="events-heading">
        <div className="panel-header"><div><p className="section-kicker">PERSISTED INVALIDATIONS</p><h2 id="events-heading">Event log</h2></div><span className="panel-meta">{data.events.length} recent</span></div>
        {data.events.length === 0 ? <div className="event-empty" role="status">No invalidations recorded yet.</div> : <ol className="events-list">{data.events.map((event) => <EventRow key={event.id} event={event} />)}</ol>}
      </section>

      <footer><span>Hashes and raw config values never leave the server.</span><span>Live updates via Server-Sent Events.</span></footer>
    </main>
  );
}
