"use client";

import { FormEvent, useEffect, useState } from "react";
import type { Camera, Save, Table, Zone } from "./types";

type Device={id:string;label:string;revision:number;status:string;purpose:string;processing_enabled:boolean};
type Key={id:string;device_id:string;fingerprint:string;expires_at:string;revoked:boolean};

export function DevicePermissions({locationId,canManage,save,disabled,cameras,tables,zones}:{
  locationId:string;canManage:boolean;save:Save;disabled:boolean;cameras:Camera[];tables:Table[];zones:Zone[];
}) {
  const [devices,setDevices]=useState<Device[]>([]);
  const [keys,setKeys]=useState<Key[]>([]);
  const [selected,setSelected]=useState("");
  const [revision,setRevision]=useState(0);
  const [message,setMessage]=useState("");
  const device=devices.find(row=>row.id===selected)||devices[0];
  useEffect(()=>{
    const controller=new AbortController();
    setDevices([]);setKeys([]);
    fetch(`/api/v1/locations/${locationId}/devices`,{cache:"no-store",signal:controller.signal})
      .then(async response=>{if(!response.ok)throw new Error("Device synchronization is unavailable or not enabled.");return response.json();})
      .then(value=>{setDevices(value.devices);setKeys(value.keys||[]);setMessage("");})
      .catch(reason=>{if(!controller.signal.aborted)setMessage(reason.message);});
    return()=>controller.abort();
  },[locationId,revision]);
  async function command(body:object){
    if(await save(`/v1/locations/${locationId}/devices/commands`,"POST",body))setRevision(value=>value+1);
  }
  async function approve(event:FormEvent<HTMLFormElement>){
    event.preventDefault();const fields=new FormData(event.currentTarget);
    const rotating=fields.get("action")==="rotate";
    if(rotating&&!device)return;
    await command({action:rotating?"rotate":"approve",request_id:fields.get("request_id"),fingerprint:fields.get("fingerprint"),
      ...(rotating?{device_id:device!.id,expected_revision:device!.revision}:{label:fields.get("label"),purpose:"AI_SHADOW"})});
  }
  async function assign(event:FormEvent<HTMLFormElement>){
    event.preventDefault();if(!device)return;
    const fields=new FormData(event.currentTarget);const zone=zones.find(row=>row.id===fields.get("zone"));if(!zone)return;
    await command({action:"assign",device_id:device.id,expected_revision:device.revision,camera_id:zone.camera_id,table_id:zone.table_id,
      zone_revision:zone.revision,profile_revision:Number(fields.get("profile_revision")),profile_sha256:fields.get("profile_sha256"),
      model_sha256:fields.get("model_sha256")});
  }
  return <section className="config-card" aria-labelledby="devices-title"><h2 id="devices-title">Background AI devices</h2>
    <p>Pair the restaurant computer by comparing its complete public fingerprint. Pairing does not allow anyone to view video. Background processing needs separate approval below.</p>
    {message&&<p role="status">{message}</p>}
    {!canManage&&<p>A manager or administrator must approve devices and camera bindings.</p>}
    {canManage&&<>
      <form className="stack" onSubmit={approve}>
        <label>Action<select name="action"><option value="approve">Approve a new shadow device</option><option value="rotate">Rotate selected device key</option></select></label>
        <label>Pairing request ID<input name="request_id" required pattern="[0-9a-fA-F-]{36}"/></label>
        <label>Full SHA-256 public fingerprint<input name="fingerprint" required pattern="[0-9a-f]{64}" maxLength={64}/></label>
        <label>Device label<input name="label" required maxLength={80} defaultValue="Local synthetic processor"/></label>
        <label><input type="checkbox" required/> I compared all 64 fingerprint characters with the restaurant computer.</label>
        <button disabled={disabled}>Approve fingerprint</button>
      </form>
      {!!devices.length&&<><label>Selected device<select value={device?.id||""} onChange={event=>setSelected(event.target.value)}>
        {devices.map(row=><option key={row.id} value={row.id}>{row.label} ({row.status})</option>)}
      </select></label>
      {device&&<><p>Device ID: <code>{device.id}</code> · {device.purpose} · Revision {device.revision}</p>
        {keys.filter(row=>row.device_id===device.id).map(row=><p key={row.id}>Public fingerprint: <code className="device-fingerprint">{row.fingerprint}</code> · {row.revoked?"Revoked":`Expires ${new Date(row.expires_at).toLocaleDateString()}`}</p>)}
        <form className="stack" onSubmit={assign}>
          <h3>Approve a synthetic camera and seating profile</h3>
          <label>Calibrated table / camera<select name="zone" required>{zones.map(zone=><option key={zone.id} value={zone.id}>
            {tables.find(row=>row.id===zone.table_id)?.label||zone.table_id} / {cameras.find(row=>row.id===zone.camera_id)?.label||zone.camera_id} / Zone revision {zone.revision}
          </option>)}</select></label>
          <label>Local seating profile revision<input name="profile_revision" required type="number" min={1} defaultValue={1}/></label>
          <label>Reviewed profile SHA-256<input name="profile_sha256" required pattern="[0-9a-f]{64}" maxLength={64}/></label>
          <label>Approved local model SHA-256<input name="model_sha256" required pattern="[0-9a-f]{64}" maxLength={64}/></label>
          <label><input type="checkbox" required/> I reviewed this synthetic source, profile and model for local shadow processing.</label>
          <button disabled={disabled||device.status!=="ACTIVE"||!zones.length}>Save camera binding</button>
        </form>
        <p>Enabling processing grants a renewable one-hour development lease. An offline computer may continue until that lease expires. Restarting always requires online authorization.</p>
        <div className="staff-actions"><button disabled={disabled||device.status!=="ACTIVE"} onClick={()=>void command({action:"processing",device_id:device.id,expected_revision:device.revision,enabled:!device.processing_enabled})}>
          {device.processing_enabled?"Disable background processing":"Enable synthetic background processing"}</button>
        <button className="secondary" disabled={disabled||device.status!=="ACTIVE"} onClick={()=>void command({action:"revoke",device_id:device.id,expected_revision:device.revision})}>Revoke selected device</button></div>
      </>}
      </>}
    </>}
  </section>;
}
