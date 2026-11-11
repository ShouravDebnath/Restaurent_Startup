"use client";

import { FormEvent, useEffect, useState } from "react";
import type { Camera, Save } from "./types";

type Grant = {id:string;viewer_id:string;expires_at:string;revoked_at:string|null};
export function PreviewPermissions({locationId,cameras,userId,canGrant,save,disabled}:{
  locationId:string;cameras:Camera[];userId:string;canGrant:boolean;save:Save;disabled:boolean;
}) {
  const [camera,setCamera]=useState(cameras[0]?.id||"");
  const [grants,setGrants]=useState<Grant[]>([]);
  const [message,setMessage]=useState("");
  const [revision,setRevision]=useState(0);
  useEffect(()=>{setCamera(cameras[0]?.id||"");setGrants([]);},[cameras,locationId]);
  useEffect(()=>{
    let active=true;setGrants([]);
    if(!camera||!canGrant)return;
    fetch(`/api/v1/locations/${locationId}/cameras/${camera}/preview-grants?limit=50`,{cache:"no-store"})
      .then(async r=>{if(!r.ok)throw new Error("Unable to load preview permissions.");return r.json();})
      .then(rows=>{if(active)setGrants(rows);}).catch(e=>{if(active)setMessage(e.message);});
    return()=>{active=false;};
  },[camera,locationId,canGrant,revision]);
  async function grant(e:FormEvent<HTMLFormElement>){
    e.preventDefault();const fields=new FormData(e.currentTarget);
    const result=await save(`/v1/locations/${locationId}/cameras/${camera}/preview-grants`,"POST",{
      viewer_id:fields.get("viewer"),duration_seconds:Number(fields.get("duration"))*60,
      request_key:crypto.randomUUID(),consent:fields.get("consent")==="on",
    });if(result){setMessage("Explicit preview permission saved. Video stays on the edge computer.");setRevision(v=>v+1);}
  }
  return <section className="config-card" aria-labelledby="preview-title"><h2 id="preview-title">Local preview permissions</h2>
    <p>Use the authenticated local calibration tool on the edge computer. Frames and camera passwords stay local. Background device health appears separately on the dashboard; pairing a device never grants human preview permission.</p>
    <p>Start the local tool with the documented Windows command, then open <a href="http://127.0.0.1:8765" target="_blank" rel="noopener noreferrer">local camera setup on this PC</a>. This link makes no automatic connection.</p>
    {canGrant&&!!cameras.length&&<><label>Preview camera<select value={camera} onChange={e=>setCamera(e.target.value)}>{cameras.map(c=><option key={c.id} value={c.id}>{c.label}</option>)}</select></label>
      <form className="stack" onSubmit={grant}><label>Authorized viewer user ID<input name="viewer" required defaultValue={userId} pattern="[0-9a-fA-F-]{36}"/></label>
      <p className="hint">Your ID is filled in for explicit self-authorization. An installer needs an eligible account and an explicit grant for this location.</p>
      <label>Duration<select name="duration" defaultValue="15"><option value="15">15 minutes</option><option value="30">30 minutes</option><option value="60">60 minutes</option></select></label>
      <label><input type="checkbox" name="consent" required/> I authorize this person to preview this camera locally.</label>
      <button disabled={disabled||!camera}>Grant local preview</button></form>
      {grants.map(g=><p key={g.id}>{g.viewer_id} · {g.revoked_at?"Revoked":`Expires ${new Date(g.expires_at).toLocaleString()}`} {!g.revoked_at&&<button className="secondary" disabled={disabled} onClick={async()=>{if(await save(`/v1/locations/${locationId}/cameras/${camera}/preview-grants/${g.id}/revoke`,"POST"))setRevision(v=>v+1);}}>Revoke preview</button>}</p>)}</>}
    {!canGrant&&<p>A manager or administrator must grant preview permission before the local tool will display video.</p>}
    {message&&<p role="status">{message}</p>}
  </section>;
}
