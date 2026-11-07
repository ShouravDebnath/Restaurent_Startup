"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Activity, Dashboard, Me, State, Table, elapsed, labels, symbols } from "./types";

type Pending = { path: string; body: object; generation: number };

export default function DashboardPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [orgId, setOrgId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [view, setView] = useState<Dashboard | null>(null);
  const [history, setHistory] = useState<Activity[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [connection, setConnection] = useState("connecting");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(false);
  const [now, setNow] = useState(0);
  const [reason, setReason] = useState("maintenance");
  const csrf = useRef("");
  const generation = useRef(0);
  const pending = useRef<Pending | null>(null);
  const working = useRef(false);
  const clockOffset = useRef(0);
  const lastContact = useRef(0);
  const refresh = useRef<() => Promise<void>>(async () => undefined);
  const connected = connection === "connected";
  const manager = !!view && ["owner", "org_admin", "manager"].includes(view.role);
  const staff = !!view && ["owner", "org_admin", "manager", "staff"].includes(view.role);
  const selected = view?.tables.find((t) => t.id === selectedId) || view?.tables[0];
  const access = me?.access.find((a) => a.organization.id === orgId);

  useEffect(() => {
    const controller = new AbortController();
    async function initialize() {
      try {
        const [identity, session] = await Promise.all([
          fetch("/api/v1/me", { cache: "no-store", signal: controller.signal }),
          fetch("/api/v1/auth/csrf", { cache: "no-store", signal: controller.signal }),
        ]);
        if (identity.status === 401 || session.status === 401) { router.replace("/sign-in"); return; }
        if (!identity.ok || !session.ok) throw new Error("Unable to open your workspace.");
        const user: Me = await identity.json();
        csrf.current = (await session.json()).csrf_token;
        if (controller.signal.aborted) return;
        setMe(user);
        const preferred = new URLSearchParams(window.location.search).get("location");
        const group = user.access.find((a) => a.locations.some((l) => l.id === preferred)) || user.access[0];
        const location = group?.locations.find((l) => l.id === preferred)
          || group?.locations.find((l) => l.name.startsWith("DEMO ")) || group?.locations[0];
        setOrgId(group?.organization.id || ""); setLocationId(location?.id || "");
      } catch { if (!controller.signal.aborted) setError("Unable to connect. Reload to try again."); }
    }
    void initialize();
    return () => controller.abort();
  }, [router]);

  useEffect(() => {
    const timer = setInterval(() => {
      setNow(Date.now() + clockOffset.current);
      if (lastContact.current && performance.now() - lastContact.current > 15000) setConnection("stale");
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const current = ++generation.current;
    const controller = new AbortController();
    let source: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let changeTimer: ReturnType<typeof setTimeout> | undefined;
    let reconnectDelay = 1000;
    let newestRevision = -1;
    const active = () => current === generation.current && !controller.signal.aborted;
    setView(null); setHistory([]); setSelectedId(""); setNotice(""); setError("");
    setConnection("connecting"); pending.current = null; setRetry(false); lastContact.current = 0;
    working.current = false; setBusy(false);
    if (!locationId) return () => controller.abort();
    window.history.replaceState(null, "", "/dashboard?location=" + encodeURIComponent(locationId));

    function loseAccess(message: string, signIn = false) {
      if (!active()) return;
      source?.close(); controller.abort();
      setView(null); setHistory([]); setMe(null); csrf.current = "";
      pending.current = null; setRetry(false); setConnection("expired"); setError(message);
      if (signIn) router.replace("/sign-in");
    }

    async function load(): Promise<Dashboard | null> {
      const prefix = `/api/v1/locations/${locationId}`;
      const [response, activities] = await Promise.all([
        fetch(prefix + "/dashboard", { cache: "no-store", signal: controller.signal }),
        fetch(prefix + "/activity?limit=30", { cache: "no-store", signal: controller.signal }),
      ]);
      if (!active()) return null;
      if (response.status === 401) { loseAccess("Your session expired. Sign in again.", true); return null; }
      if ([403, 404].includes(response.status)) { loseAccess("Location access changed. Open settings to select another location."); return null; }
      if (!response.ok || !activities.ok) throw new Error("Updates unavailable.");
      const snapshot: Dashboard = await response.json();
      const events: Activity[] = await activities.json();
      if (!active()) return null;
      const revision = Number(snapshot.cursor.split(":")[1]);
      if (revision >= newestRevision) {
        newestRevision = revision; setView(snapshot); setHistory(events);
        clockOffset.current = Date.parse(snapshot.server_time) - Date.now();
        setNow(Date.parse(snapshot.server_time));
      }
      return snapshot;
    }
    refresh.current = async () => { try { await load(); } catch { if (active()) setError("Unable to refresh. Your last information may be stale."); } };

    async function connect() {
      try {
        const snapshot = await load();
        if (!snapshot || !active()) return;
        source = new EventSource(`/api/v1/locations/${locationId}/stream?after=${encodeURIComponent(snapshot.cursor)}`);
        const opened = source;
        function contact() {
          if (!active() || source !== opened) return;
          lastContact.current = performance.now(); setConnection("connected"); reconnectDelay = 1000;
        }
        opened.addEventListener("heartbeat", (event) => {
          contact();
          const data = JSON.parse((event as MessageEvent).data);
          clockOffset.current = Date.parse(data.server_time) - Date.now();
        });
        opened.addEventListener("change", () => {
          contact(); clearTimeout(changeTimer);
          changeTimer = setTimeout(() => { if (active()) void refresh.current(); }, 100);
        });
        opened.addEventListener("session_expired", () => loseAccess("Your session expired. Sign in again.", true));
        opened.addEventListener("access_lost", () => loseAccess("Your location access changed. Return to settings."));
        opened.addEventListener("unavailable", () => reconnect());
        opened.onerror = () => reconnect();
      } catch { if (active()) reconnect(); }
    }
    function reconnect() {
      if (!active()) return;
      source?.close(); source = null; clearTimeout(reconnectTimer);
      if (!navigator.onLine) { setConnection("stale"); return; }
      setConnection("reconnecting");
      reconnectTimer = setTimeout(() => { void connect(); }, reconnectDelay);
      reconnectDelay = Math.min(10000, reconnectDelay * 2);
    }
    const offline = () => reconnect();
    const online = () => reconnect();
    window.addEventListener("offline", offline);
    window.addEventListener("online", online);
    void connect();
    return () => {
      controller.abort(); source?.close(); clearTimeout(reconnectTimer); clearTimeout(changeTimer);
      window.removeEventListener("offline", offline);
      window.removeEventListener("online", online);
    };
  }, [locationId, router]);

  async function send(request: Pending) {
    if (working.current || request.generation !== generation.current) return;
    working.current = true; setBusy(true); setError(""); setNotice(""); setRetry(false);
    try {
      const response = await fetch(request.path, {
        method: "POST", cache: "no-store", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf.current },
        body: JSON.stringify(request.body), signal: AbortSignal.timeout(10000),
      });
      if (request.generation !== generation.current) return;
      if (response.status === 401) { setView(null); setHistory([]); router.replace("/sign-in"); return; }
      if (!response.ok) {
        if (response.status >= 500) throw new Error("The result is uncertain. Retry the same request safely.");
        pending.current = null;
        const body = await response.json();
        setError(body.error?.message || "This action could not be completed.");
      } else { pending.current = null; setNotice("Saved. Your team will see the update."); }
      await refresh.current();
    } catch {
      if (request.generation === generation.current) {
        setError("The result is uncertain. Retry the same request to avoid a duplicate action."); setRetry(true);
      }
    } finally {
      if (request.generation === generation.current) { working.current = false; setBusy(false); }
    }
  }

  function act(table: Table, action: string, demo = false) {
    if (!connected || working.current || pending.current) return;
    const task = view?.tasks.find((t) => t.table_id === table.id);
    const body = demo
      ? { table_id: table.id, action, expected_revision: table.operational_revision, request_key: crypto.randomUUID() }
      : { action, expected_revision: table.operational_revision, request_key: crypto.randomUUID(),
          task_id: task?.id || null, confirmed: action === "mark_ready", reason: action === "out_of_service" ? reason : "" };
    const request = { path: demo ? `/api/v1/locations/${locationId}/demo/events` : `/api/v1/tables/${table.id}/actions`,
      body, generation: generation.current };
    pending.current = request; void send(request);
  }

  async function logout() {
    try { await fetch("/api/v1/auth/session", { method: "DELETE", headers: { "X-CSRF-Token": csrf.current } }); }
    finally { setView(null); setHistory([]); setMe(null); generation.current++; router.replace("/sign-in"); }
  }

  const disabled = busy || !connected || retry;
  const counts = (state: State) => view?.tables.filter((t) => t.current_state === state
    && (state !== "AVAILABLE" || (connected && t.source_status === "ONLINE" && t.observation === "VACANT"))).length || 0;

  if (!me) return <main className="workspace"><h1>Restaurant dashboard</h1>
    <p role="status">{error || "Opening your workspace…"}</p><Link href="/settings">Open settings</Link></main>;

  return <main className="dashboard-shell">
    <header className="dashboard-header"><div><Link className="brand" href="/">Restaurant AI Monitoring</Link>
      <h1>The dining room, at a glance.</h1></div><nav aria-label="Workspace navigation">
        <Link href="/settings">Settings</Link><button className="secondary" onClick={() => void logout()}>Sign out</button></nav></header>
    <section className="dashboard-toolbar" aria-label="Workspace selection">
      <label>Restaurant<select value={orgId} onChange={(e) => {
        setView(null); setHistory([]); setOrgId(e.target.value);
        const places = me.access.find((a) => a.organization.id === e.target.value)?.locations;
        setLocationId(places?.find((l) => l.name.startsWith("DEMO "))?.id || places?.[0]?.id || "");
      }}>{me.access.map((a) => <option key={a.organization.id} value={a.organization.id}>{a.organization.name}</option>)}</select></label>
      <label>Location<select value={locationId} onChange={(e) => { setView(null); setHistory([]); setLocationId(e.target.value); }}>
        {!access?.locations.length && <option value="">No assigned locations</option>}
        {access?.locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}</select></label>
      <span className="badge">{view?.role.replaceAll("_", " ") || "Loading"}</span>
      <button className="secondary" disabled={!view || busy} onClick={() => void refresh.current()}>Refresh</button>
    </section>
    {view?.demo ? <p className="demo-notice"><strong>DEMO — simulated information.</strong> No CCTV or AI is connected. Scenario observations stay effective until the next explicit demo input.</p>
      : <p className="demo-notice">Configuration workspace. No video source is connected.</p>}
    <div className="dashboard-connection" role="status"><strong>{connected ? "Updates connected" : connection === "connecting" ? "Connecting updates…" : "STALE — updates interrupted"}</strong>
      {view && <span>{view.location.name} · {now ? new Date(now).toLocaleTimeString([], { timeZone: view.location.time_zone }) : "—"} · {view.location.time_zone}</span>}</div>
    {!connected && view && <p className="offline-banner">Last-known information only. Current availability and actions are paused until updates reconnect.</p>}
    <div aria-live="polite">{error && <p role="alert" className="error">{error}</p>}{notice && <p className="notice">{notice}</p>}</div>
    {retry && <button disabled={busy} onClick={() => { if (pending.current) void send(pending.current); }}>Retry the same request</button>}
    {!locationId && <p>No location is assigned. Ask an administrator to grant access.</p>}
    {locationId && !view && <p role="status">Loading your dining room…</p>}
    {view && <>
      {(view.tables_truncated || view.tasks_truncated) && <p role="alert" className="offline-banner">This overview has reached its display limit. Some tables or tasks are not shown. Ask an administrator to review the full location records.</p>}
      <section className="floor-summary" aria-label="Table summary">
        <div><strong>{view.tables.length}</strong><span>Tables shown</span></div>
        {(["AVAILABLE", "OCCUPIED", "RESET_PENDING", "CLEANING", "UNKNOWN", "OUT_OF_SERVICE"] as State[]).map((state) =>
          <div key={state}><strong>{counts(state)}</strong><span>{labels[state]}</span></div>)}
      </section>
      <div className="floor-workspace"><section aria-label="Floor view" className="floor-panel">
        <div className="panel-heading"><h2>Floor view</h2><span className="hint">Select a table for details</span></div>
        <div className="floor-grid">{view.tables.map((table) => <button key={table.id} type="button"
          className={`floor-table state-${table.current_state.toLowerCase()} ${selected?.id === table.id ? "selected" : ""}`}
          aria-pressed={selected?.id === table.id} data-table-id={table.id} data-state={table.current_state}
          onClick={() => setSelectedId(table.id)}>
          <span className="table-name">{table.label}<span>{table.seats ? `${table.seats} seats` : "Seats not set"}</span></span>
          <span className="table-status"><span aria-hidden="true">{symbols[table.current_state]}</span> {connected ? "" : "Last known: "}{labels[table.current_state]}</span>
          <span className="table-timer" aria-live="off">{elapsed(table.state_since, now)} <small>in this state</small></span>
          {table.source_status !== "ONLINE" && <span className="source-warning">{view.demo ? "Demo source" : "Source"}: {table.source_status === "OFFLINE" ? "offline" : "not connected"}</span>}
          {table.state_source === "manual" && <span className="manual-label">Staff-confirmed state</span>}
        </button>)}</div>
        {!view.tables.length && <p>No tables configured. Add tables in settings.</p>}
        <div className="floor-legend" aria-label="Status legend">{(Object.keys(labels) as State[]).map((state) =>
          <span key={state}><span aria-hidden="true">{symbols[state]}</span> {labels[state]}</span>)}</div>
        <p className="hint">Available counts require a current vacant demo observation and connected updates. A manual state is retained during source failure; its readiness is not rechecked.</p>
      </section>
      <aside className="staff-panel" aria-label="Staff workspace">
        {selected && <section className="table-details" aria-label="Selected table">
          <h2>{selected.label}</h2><p><strong>{labels[selected.current_state]}</strong> · {elapsed(selected.state_since, now)}</p>
          {selected.current_state === "OCCUPIED" && selected.occupied_since && <p>Occupancy timer: {elapsed(selected.occupied_since, now)}</p>}
          <p className="hint">{selected.source_status === "ONLINE" ? `Demo observation: ${selected.observation.toLowerCase()}` : "Source information is unavailable."}
            {selected.observed_at && ` Last input ${new Date(selected.observed_at).toLocaleTimeString([], { timeZone: view.location.time_zone })}.`}</p>
          <p className="hint">Timers show recorded state duration, not order or service time. AI confidence is not measured.</p>
          {staff && <div className="staff-actions">
            {selected.current_state === "RESET_PENDING" && <button disabled={disabled} onClick={() => act(selected, "start_cleaning")}>Start cleaning</button>}
            {["CLEANING", "UNKNOWN"].includes(selected.current_state) && <button disabled={disabled || selected.source_status !== "ONLINE" || selected.observation !== "VACANT"}
              onClick={() => act(selected, "mark_ready")}>I checked this table — mark ready</button>}
          </div>}
          {manager && (selected.current_state === "OUT_OF_SERVICE"
            ? <button className="secondary" disabled={disabled} onClick={() => act(selected, "reopen")}>Reopen to unknown</button>
            : <div className="manager-actions"><label>Reason<select value={reason} onChange={(e) => setReason(e.target.value)}>
              <option value="maintenance">Maintenance</option><option value="reserved">Reserved</option><option value="safety">Safety</option><option value="other">Other operational reason</option>
            </select></label><button className="secondary" disabled={disabled} onClick={() => act(selected, "out_of_service")}>Out of service</button></div>)}
          {view.simulation_controls && <details className="simulation-controls"><summary>DEMO scenario controls</summary>
            <p className="hint">Change synthetic observations for this table. Cleaning and manager blocks take priority.</p>
            <div>{[["arrive", "Guests arrive"], ["depart", "Guests leave"], ["vacant", "Show vacant"], ["source_offline", "Source offline"], ["source_resume", "Resume source"]].map(([action, label]) =>
              <button key={action} className="secondary" disabled={disabled} onClick={() => act(selected, action, true)}>{label}</button>)}</div>
          </details>}
        </section>}
        <section className="task-panel" aria-label="Cleaning tasks"><h2>Needs attention <span className="badge">{view.tasks.length}</span></h2>
          <p className="hint">Oldest tasks first. “May need cleaning” requires a staff check.</p>
          {!view.tasks.length && <p>No active reset tasks.</p>}
          {view.tasks.map((task) => {
            const table = view.tables.find((t) => t.id === task.table_id);
            return <article className="cleaning-task" key={task.id}><h3>{table?.label || "Table"} may need cleaning</h3>
              <p>{task.status.replaceAll("_", " ")} · {elapsed(task.created_at, now)} since task creation</p>
              {table && <div><button className="secondary" onClick={() => setSelectedId(table.id)}>View table</button>
                {staff && task.status === "OPEN" && <button disabled={disabled} onClick={() => act(table, "acknowledge")}>Acknowledge</button>}
                {staff && table.current_state === "RESET_PENDING" && <button disabled={disabled} onClick={() => act(table, "start_cleaning")}>Start cleaning</button>}</div>}
            </article>;
          })}</section>
      </aside></div>
      <section className="activity-panel" aria-label="Recent table activity"><h2>Recent activity</h2>
        <p className="hint">Last 30 location events · times in {view.location.time_zone}. Operational history excludes private administration records.</p>
        <ol>{history.map((event) => <li key={event.id}><time dateTime={event.occurred_at}>{new Date(event.occurred_at).toLocaleString([], { timeZone: view.location.time_zone })}</time>
          <span>{view.tables.find((t) => t.id === event.table_id)?.label || "Table"}: {event.event_type.replace("table.", "").replaceAll("_", " ")} → {labels[event.new_state]}</span>
          <span className="badge">{event.source === "demo" ? "DEMO" : event.source}</span></li>)}</ol>
      </section>
    </>}
  </main>;
}
