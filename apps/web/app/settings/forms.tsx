"use client";

import { FormEvent, useState } from "react";
import type { Camera, Location, Member, Role, Save, Table, Zone } from "./types";

export function TableForm({ initial, path, save, disabled }: {
  initial?: Table; path: string; save: Save; disabled: boolean;
}) {
  const [label, setLabel] = useState(initial?.label || "");
  const [seats, setSeats] = useState(initial?.seats?.toString() || "");
  async function submit(e: FormEvent) {
    e.preventDefault();
    const result = await save(path, initial ? "PATCH" : "POST", { label, seats: seats ? Number(seats) : null });
    if (!initial && result) { setLabel(""); setSeats(""); }
  }
  return <form onSubmit={submit} className="inline-form">
    <label>Table label<input aria-label={initial ? `Label for ${initial.label}` : "New table label"}
      required maxLength={80} value={label} onChange={(e) => setLabel(e.target.value)} /></label>
    <label>Seats<input type="number" min={1} max={100} value={seats}
      onChange={(e) => setSeats(e.target.value)} /></label>
    {initial && <span className="badge">{initial.current_state}</span>}
    <button disabled={disabled}>{initial ? "Save table" : "Add table"}</button>
  </form>;
}

export function CameraForm({ initial, path, save, disabled }: {
  initial?: Camera; path: string; save: Save; disabled: boolean;
}) {
  const [label, setLabel] = useState(initial?.label || "");
  const [reference, setReference] = useState(initial?.source_reference || "");
  async function submit(e: FormEvent) {
    e.preventDefault();
    const result = await save(path, initial ? "PATCH" : "POST", { label, source_reference: reference || null });
    if (!initial && result) { setLabel(""); setReference(""); }
  }
  return <form onSubmit={submit} className="inline-form">
    <label>Camera label<input required maxLength={80} value={label} onChange={(e) => setLabel(e.target.value)} /></label>
    <label>Local reference<input maxLength={80} pattern="[A-Za-z0-9_-]+" placeholder="dining_room_camera"
      value={reference} onChange={(e) => setReference(e.target.value)} /></label>
    <button disabled={disabled}>{initial ? "Save camera" : "Add camera"}</button>
  </form>;
}

export function ZoneForm({ initial, path, save, disabled, tables, cameras }: {
  initial?: Zone; path: string; save: Save; disabled: boolean; tables: Table[]; cameras: Camera[];
}) {
  const [table, setTable] = useState(initial?.table_id || tables[0]?.id || "");
  const [camera, setCamera] = useState(initial?.camera_id || cameras[0]?.id || "");
  const [polygon, setPolygon] = useState(JSON.stringify(initial?.polygon || [[0.1, 0.1], [0.8, 0.1], [0.8, 0.8], [0.1, 0.8]]));
  const [width, setWidth] = useState(initial?.source_width || 1920);
  const [height, setHeight] = useState(initial?.source_height || 1080);
  const [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const points = JSON.parse(polygon);
      await save(path, initial ? "PUT" : "POST", {
        table_id: table, camera_id: camera, polygon: points, source_width: width, source_height: height,
        ...(initial ? { expected_revision: initial.revision } : {}),
      });
    } catch { setError("Check the polygon and the message above before trying again."); }
  }
  return <form onSubmit={submit} className="zone-form">
    {initial && <p className="hint">Calibration revision {initial.revision}</p>}
    <div className="inline-form">
      <label>Table<select required value={table} onChange={(e) => setTable(e.target.value)}>
        <option value="" disabled>Select a table</option>{tables.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
      </select></label>
      <label>Camera<select required value={camera} onChange={(e) => setCamera(e.target.value)}>
        <option value="" disabled>Select a camera</option>{cameras.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
      </select></label>
      <label>Source width<input type="number" min={1} max={32768} required value={width}
        onChange={(e) => setWidth(Number(e.target.value))} /></label>
      <label>Source height<input type="number" min={1} max={32768} required value={height}
        onChange={(e) => setHeight(Number(e.target.value))} /></label>
    </div>
    <label>Normalized polygon points<textarea required value={polygon} onChange={(e) => setPolygon(e.target.value)} /></label>
    <p className="hint">Enter at least three [x, y] points between 0 and 1, in boundary order. The polygon must not cross itself.</p>
    {error && <p role="alert" className="error">{error}</p>}
    <button disabled={disabled || !table || !camera}>{initial ? "Save zone" : "Add zone"}</button>
  </form>;
}

export function MemberForm({ member, locations, owner, save, path, disabled }: {
  member: Member; locations: Location[]; owner: boolean; save: Save; path: string; disabled: boolean;
}) {
  const [role, setRole] = useState<Role>(member.role);
  const [enabled, setEnabled] = useState(member.enabled);
  const [grants, setGrants] = useState(member.location_ids);
  const roles: Role[] = owner ? ["owner", "org_admin", "manager", "staff", "installer"] : ["org_admin", "manager", "staff", "installer"];
  const locked = disabled || (!owner && member.role === "owner");
  async function submit(e: FormEvent) {
    e.preventDefault();
    await save(path, "PATCH", { role, enabled, location_ids: grants });
  }
  return <form onSubmit={submit} className="member-form">
    <div><strong>{member.display_name}</strong><p className="hint">{member.email}</p></div>
    <label>Role<select disabled={locked} value={role} onChange={(e) => setRole(e.target.value as Role)}>
      {member.role === "owner" && !owner && <option value="owner">owner</option>}
      {roles.map((r) => <option key={r} value={r}>{r.replaceAll("_", " ")}</option>)}
    </select></label>
    <label className="check"><input type="checkbox" disabled={locked} checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />Access enabled</label>
    <fieldset disabled={locked}><legend>Location access</legend>
      {locations.map((l) => <label className="check" key={l.id}>
        <input type="checkbox" checked={grants.includes(l.id)} onChange={(e) => setGrants(
          e.target.checked ? [...grants, l.id] : grants.filter((id) => id !== l.id),
        )} />{l.name}</label>)}
      {member.location_ids.some((id) => !locations.some((l) => l.id === id)) &&
        <p className="hint">Other assigned locations are preserved.</p>}
    </fieldset>
    <button disabled={locked}>Save access</button>
  </form>;
}
