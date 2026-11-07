"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { CameraForm, MemberForm, TableForm, ZoneForm } from "./forms";
import type { Audit, Camera, Me, Member, Role, Table, Zone } from "./types";

export default function SettingsPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [csrf, setCsrf] = useState("");
  const [organizationId, setOrganizationId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [tables, setTables] = useState<Table[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [audits, setAudits] = useState<Audit[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [revision, setRevision] = useState(0);
  const access = me?.access.find((a) => a.organization.id === organizationId);
  const location = access?.locations.find((l) => l.id === locationId);
  const admin = access?.role === "owner" || access?.role === "org_admin";
  const manager = admin || access?.role === "manager";
  const installer = manager || access?.role === "installer";
  const disabled = busy || !csrf || loading;

  const request = useCallback(async <T,>(path: string, options?: RequestInit): Promise<T> => {
    const response = await fetch("/api" + path, { ...options, cache: "no-store" });
    if (response.status === 401) {
      setMe(null);
      router.replace("/sign-in");
      throw new Error("Please sign in again.");
    }
    if (response.status === 204) return null as T;
    const result = await response.json();
    if (!response.ok) throw new Error(result.error?.message || "The request could not be completed.");
    return result as T;
  }, [router]);

  const refreshIdentity = useCallback(async () => {
    const value = await request<Me>("/v1/me");
    setMe(value);
    return value;
  }, [request]);

  useEffect(() => {
    let active = true;
    Promise.all([request<Me>("/v1/me"), request<{ csrf_token: string }>("/v1/auth/csrf")])
      .then(([value, session]) => {
        if (!active) return;
        setMe(value); setCsrf(session.csrf_token);
        setOrganizationId(value.access[0]?.organization.id || "");
        setLocationId(value.access[0]?.locations[0]?.id || "");
      }).catch((reason) => { if (active) setError(reason.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [request]);

  useEffect(() => {
    let active = true;
    setTables([]); setCameras([]); setZones([]); setMembers([]); setAudits([]);
    if (!organizationId) return;
    setLoading(true);
    const prefix = `/v1/locations/${locationId}`;
    Promise.all([
      locationId ? request<Table[]>(prefix + "/tables") : Promise.resolve([]),
      locationId ? request<Camera[]>(prefix + "/cameras") : Promise.resolve([]),
      locationId ? request<Zone[]>(prefix + "/table-zones") : Promise.resolve([]),
      admin ? request<Member[]>(`/v1/organizations/${organizationId}/memberships`) : Promise.resolve([]),
      admin ? request<Audit[]>(`/v1/organizations/${organizationId}/audit-logs?limit=20`) :
        manager && locationId ? request<Audit[]>(prefix + "/audit-logs?limit=20") : Promise.resolve([]),
    ]).then(([t, c, z, m, a]) => {
      if (!active) return;
      setTables(t); setCameras(c); setZones(z); setMembers(m); setAudits(a);
    }).catch((reason) => { if (active) setError(reason.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [organizationId, locationId, admin, manager, request, revision]);

  async function save(path: string, method: string, body?: object) {
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await request<{ id?: string }>(path, {
        method, headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        ...(body ? { body: JSON.stringify(body) } : {}),
      });
      if (path === "/v1/auth/session" && method === "DELETE") {
        setMe(null); router.replace("/sign-in"); return true;
      }
      const identity = await refreshIdentity();
      const selectedOrg = path === "/v1/organizations" && method === "POST" ? result.id : organizationId;
      const current = identity.access.find((a) => a.organization.id === selectedOrg);
      setOrganizationId(current?.organization.id || identity.access[0]?.organization.id || "");
      const selectedLoc = path.endsWith("/locations") && method === "POST" ? result.id : locationId;
      setLocationId(current?.locations.some((l) => l.id === selectedLoc) ? selectedLoc || "" : current?.locations[0]?.id || "");
      setNotice("Changes saved."); setRevision((v) => v + 1);
      return result;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save changes.");
      return null;
    } finally { setBusy(false); }
  }

  async function addOrganization(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (await save("/v1/organizations", "POST", { name: new FormData(form).get("name") })) form.reset();
  }

  async function addLocation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    if (await save(`/v1/organizations/${organizationId}/locations`, "POST", {
      name: fields.get("name"), time_zone: fields.get("time_zone"), address: fields.get("address") || null,
    })) form.reset();
  }

  async function addMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    if (await save(`/v1/organizations/${organizationId}/memberships`, "POST", {
      email: fields.get("email"), role: fields.get("role"), location_ids: fields.getAll("location"),
    })) form.reset();
  }

  if (!me) return <main className="workspace"><p role="status">Opening your workspace…</p>
    {error && <p role="alert" className="error">{error}</p>}<Link href="/sign-in">Go to sign in</Link></main>;

  return <main className="workspace">
    <header className="workspace-header">
      <Link className="brand" href="/">Restaurant AI Monitoring</Link>
      <div><span className="hint">{me.display_name}</span> <button className="secondary" disabled={busy || !csrf}
        onClick={() => void save("/v1/auth/session", "DELETE")}>Sign out</button></div>
    </header>
    <p className="eyebrow">Restaurant settings</p><h1>A place for every detail.</h1>
    <p className="muted">Manage your locations, table configuration, and team access.</p>
    <section className="switcher" aria-label="Workspace selection">
      <label>Restaurant<select value={organizationId} onChange={(e) => {
        setOrganizationId(e.target.value);
        setLocationId(me.access.find((a) => a.organization.id === e.target.value)?.locations[0]?.id || "");
        setError(""); setNotice("");
      }}>{me.access.map((a) => <option key={a.organization.id} value={a.organization.id}>{a.organization.name}</option>)}</select></label>
      <label>Location<select value={locationId} onChange={(e) => { setLocationId(e.target.value); setError(""); setNotice(""); }}>
        {!access?.locations.length && <option value="">No assigned locations</option>}
        {access?.locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
      </select></label><span className="badge">{access?.role.replaceAll("_", " ") || "No membership"}</span>
    </section>
    <div aria-live="polite">{notice && <p className="notice">{notice}</p>}{error && <p className="error" role="alert">{error}</p>}</div>
    {loading && <p role="status">Loading settings…</p>}

    {location && <>
      <section className="config-card"><h2>{location.name}</h2>
        <p className="muted">Time zone: {location.time_zone}{location.address ? ` · ${location.address}` : ""}</p>
        {admin && <form key={location.id + revision} className="inline-form" onSubmit={(event) => {
          event.preventDefault(); const fields = new FormData(event.currentTarget);
          void save(`/v1/locations/${locationId}`, "PATCH", {
            name: fields.get("name"), time_zone: fields.get("time_zone"), address: fields.get("address") || null,
          });
        }}>
          <label>Location name<input name="name" required maxLength={120} defaultValue={location.name} /></label>
          <label>IANA time zone<input name="time_zone" required maxLength={100} defaultValue={location.time_zone} /></label>
          <label>Address<input name="address" maxLength={500} defaultValue={location.address || ""} /></label>
          <button disabled={disabled}>Save location</button>
        </form>}
      </section>
      <section className="config-card" aria-labelledby="tables-title"><h2 id="tables-title">Tables</h2>
        <p className="hint">New tables start as UNKNOWN. Live monitoring and readiness actions are not connected.</p>
        {!tables.length && <p className="muted">No tables registered at this location.</p>}
        {tables.map((t) => manager ? <TableForm key={`${t.id}-${t.label}-${t.seats}`} initial={t} path={`/v1/locations/${locationId}/tables/${t.id}`} save={save} disabled={disabled} /> :
          <p key={t.id}>{t.label} · {t.seats || "—"} seats <span className="badge">{t.current_state}</span></p>)}
        {manager && <details><summary>Add a table</summary><TableForm key={locationId} path={`/v1/locations/${locationId}/tables`} save={save} disabled={disabled} /></details>}
      </section>
      <section className="config-card" aria-labelledby="cameras-title"><h2 id="cameras-title">Cameras</h2>
        <p className="hint">Metadata only · not connected. Use a local reference without a URL or password.</p>
        {!cameras.length && <p className="muted">No cameras registered at this location.</p>}
        {cameras.map((c) => installer ? <CameraForm key={`${c.id}-${c.label}-${c.source_reference}`} initial={c} path={`/v1/locations/${locationId}/cameras/${c.id}`} save={save} disabled={disabled} /> : <p key={c.id}>{c.label} · Not configured</p>)}
        {installer && <details><summary>Add camera metadata</summary><CameraForm key={locationId} path={`/v1/locations/${locationId}/cameras`} save={save} disabled={disabled} /></details>}
      </section>
      <section className="config-card"><h2>Table zones</h2>
        <p className="hint">Saved calibration data. Camera preview and the drawing tool arrive in a later phase.</p>
        {!zones.length && <p className="muted">No table zones saved.</p>}
        {zones.map((z) => installer ? <details key={z.id}><summary>{tables.find((t) => t.id === z.table_id)?.label || "Table"} · {cameras.find((c) => c.id === z.camera_id)?.label || "Camera"} · revision {z.revision}</summary>
          <ZoneForm key={`${z.id}-${z.revision}`} initial={z} path={`/v1/locations/${locationId}/table-zones/${z.id}`} save={save} disabled={disabled} tables={tables} cameras={cameras} />
        </details> : <p key={z.id}>Table zone · revision {z.revision}</p>)}
        {installer && !!tables.length && !!cameras.length && <details><summary>Add a table zone</summary>
          <ZoneForm key={locationId + tables.length + cameras.length} path={`/v1/locations/${locationId}/table-zones`} save={save} disabled={disabled} tables={tables} cameras={cameras} />
        </details>}
      </section>
    </>}

    {admin && <>
      <section className="config-card"><h2>Restaurant and locations</h2>
        <form key={organizationId + revision} className="inline-form" onSubmit={(event) => {
          event.preventDefault(); void save(`/v1/organizations/${organizationId}`, "PATCH", { name: new FormData(event.currentTarget).get("name") });
        }}><label>Restaurant name<input name="name" required maxLength={120} defaultValue={access?.organization.name} /></label><button disabled={disabled}>Save restaurant</button></form>
        <details><summary>Add a location</summary><form className="inline-form" onSubmit={addLocation}>
          <label>Location name<input name="name" required maxLength={120} /></label>
          <label>IANA time zone<input name="time_zone" required maxLength={100} placeholder="America/New_York" /></label>
          <label>Address<input name="address" maxLength={500} /></label>
          <button disabled={disabled}>Add location</button>
        </form></details>
      </section>
      <section className="config-card"><h2>Team access</h2><p className="hint">Each person needs explicit location access. Only an owner can change owner permissions.</p>
        {members.map((m) => <MemberForm key={`${m.id}-${revision}`} member={m} locations={access?.locations || []} owner={access?.role === "owner"} save={save}
          path={`/v1/organizations/${organizationId}/memberships/${m.id}`} disabled={disabled} />)}
        <details><summary>Add an existing account</summary><form className="stack" onSubmit={addMember}>
          <label>Email<input name="email" type="email" required maxLength={254} /></label>
          <label>Role<select name="role" defaultValue="staff">{(["staff", "installer", "manager", "org_admin", ...(access?.role === "owner" ? ["owner"] : [])] as Role[]).map((r) => <option key={r} value={r}>{r.replaceAll("_", " ")}</option>)}</select></label>
          <fieldset><legend>Location access</legend>{access?.locations.map((l) => <label className="check" key={l.id}><input type="checkbox" name="location" value={l.id} />{l.name}</label>)}</fieldset>
          <button disabled={disabled}>Add account to restaurant</button>
        </form></details>
      </section>
    </>}
    {manager && <section className="config-card"><h2>Recent activity</h2><p className="hint">Latest 20 permitted records. Times use each record’s location time zone; restaurant-wide changes use UTC.</p>
      {!audits.length && <p className="muted">No activity to show.</p>}
      <div className="audit-list">{audits.map((a) => {
        const zone = access?.locations.find((l) => l.id === a.location_id)?.time_zone || "UTC";
        return <p key={a.id}><span>{a.action.replaceAll(".", " · ")}</span><time dateTime={a.created_at}>{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: zone }).format(new Date(a.created_at))} · {zone}</time></p>;
      })}</div>
    </section>}
    <section className="config-card"><details><summary>Create another restaurant workspace</summary>
      <form className="inline-form" onSubmit={addOrganization}><label>Restaurant name<input name="name" required maxLength={120} /></label><button disabled={disabled}>Create restaurant</button></form>
    </details></section>
  </main>;
}
