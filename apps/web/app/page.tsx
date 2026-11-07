import Link from "next/link";

const checks = [
  "Two separate synthetic restaurant workspaces",
  "Camera inference not configured",
  "Raw video stays local by default",
];

export default function Home() {
  return (
    <main className="shell">
      <section className="masthead">
        <p className="eyebrow">Restaurant AI Monitoring / Phase 3</p>
        <h1>Know the room before the room gets away from you.</h1>
        <p className="lede">
          Explore simulated table states, saved timers, and staff reset tasks in your private
          restaurant workspace.
        </p>
        <div className="status"><span aria-hidden="true" /> DEMO MODE</div>
        <p><Link className="primary-link" href="/dashboard">Open restaurant dashboard →</Link></p>
        <p><Link className="primary-link" href="/settings">Open restaurant settings →</Link></p>
      </section>
      <section className="panel" aria-labelledby="foundation-title">
        <div>
          <p className="eyebrow">System status</p>
          <h2 id="foundation-title">Your demo dining room is ready</h2>
          <p className="muted">Sign in to operate synthetic scenarios. Real CCTV and AI are not connected.</p>
        </div>
        <ul>
          {checks.map((check) => <li key={check}>{check}</li>)}
        </ul>
      </section>
    </main>
  );
}
