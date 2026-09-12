export default function Home() {
  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">ARGUSD / REVIEW 1</p>
        <h1>Freshness for the agent’s memory.</h1>
        <p className="lede">
          The dashboard shell is live. Claims, invalidation events, and the live feed
          will be wired after the MCP connection proof.
        </p>
      </section>

      <section className="grid" aria-label="System status">
        <article className="card">
          <span className="label">Dashboard</span>
          <strong><span className="dot" /> Rendering</strong>
          <p>Next.js App Router is serving this placeholder page.</p>
        </article>
        <article className="card">
          <span className="label">MCP connection</span>
          <strong><span className="dot pending" /> Ping scaffold</strong>
          <p>Call the server’s <code>ping</code> tool to prove the agent path.</p>
        </article>
      </section>

      <footer>Real claims UI and live invalidation feed: deferred until after Review 1.</footer>
    </main>
  );
}
