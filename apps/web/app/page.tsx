import Link from "next/link";

const checks = [
  "Synthetic demo tenant enabled",
  "Camera inference not configured",
  "Raw video stays local by default",
];

export default function Home() {
  return (
    <main className="shell">
      <section className="masthead">
        <p className="eyebrow">Restaurant AI Monitoring / Phase 1</p>
        <h1>Know the room before the room gets away from you.</h1>
        <p className="lede">
          A foundation for table operations built around local processing, honest states, and staff
          confirmation.
        </p>
        <div className="status"><span aria-hidden="true" /> DEMO MODE</div>
        <p><Link className="primary-link" href="/settings">Open restaurant settings →</Link></p>
      </section>
      <section className="panel" aria-labelledby="foundation-title">
        <div>
          <p className="eyebrow">System status</p>
          <h2 id="foundation-title">Foundation ready</h2>
          <p className="muted">The web shell is connected to the synthetic Phase 1 boundary.</p>
        </div>
        <ul>
          {checks.map((check) => <li key={check}>{check}</li>)}
        </ul>
      </section>
    </main>
  );
}
