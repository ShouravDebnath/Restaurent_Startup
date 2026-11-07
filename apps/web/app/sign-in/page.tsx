"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export default function SignIn() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/v1/auth/session", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }), cache: "no-store",
      });
      const body = await response.json();
      setPassword("");
      if (!response.ok) throw new Error(body.error?.message || "Unable to sign in.");
      router.replace("/settings");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to reach the service.");
    } finally { setBusy(false); }
  }

  return <main className="auth-shell">
    <Link className="brand" href="/">Restaurant AI Monitoring</Link>
    <section className="auth-card">
      <p className="eyebrow">Your restaurant workspace</p>
      <h1>Welcome back.</h1>
      <p className="muted">Sign in with the account provided by your administrator.</p>
      <form onSubmit={submit} className="stack">
        <label>Email<input name="email" type="email" autoComplete="username" required maxLength={254}
          value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label>Password<input name="password" type="password" autoComplete="current-password" required
          maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {error && <p className="error" role="alert">{error}</p>}
        <button disabled={busy} type="submit">{busy ? "Signing in…" : "Sign in"}</button>
      </form>
      <p className="hint">Local development environment. Live camera monitoring is not connected.</p>
    </section>
  </main>;
}
