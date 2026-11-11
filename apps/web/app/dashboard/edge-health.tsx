"use client";

import { useEffect, useRef, useState } from "react";

type Device = {id:string;label:string;purpose:string;status:string;last_contact_at:string|null;
  metrics:{camera:string;inference:string;queue_pending:number}|null};
type Shadow = {binding_id:string;state:string;occurred_at:string;reason:string;stale:boolean};
type Health = {devices:Device[];shadows:Shadow[];server_time:string};

export function EdgeHealthPanel({locationId,cursor,timeZone}:{locationId:string;cursor:string;timeZone:string}) {
  const [data,setData] = useState<Health|null>(null);
  const [error,setError] = useState("");
  const [now,setNow] = useState(0);
  const clock=useRef({server:0,received:0});
  useEffect(()=>{
    const controller=new AbortController();
    fetch(`/api/v1/locations/${locationId}/devices`,{cache:"no-store",signal:controller.signal})
      .then(async response=>{if(!response.ok)throw new Error(response.status===503?"Device synchronization is not enabled.":"Device health is unavailable. Reload or sign in again.");return response.json();})
      .then(value=>{clock.current={server:Date.parse(value.server_time),received:performance.now()};setData(value);setNow(clock.current.server);setError("");})
      .catch(reason=>{if(!controller.signal.aborted){setData(null);setError(reason.message);}});
    return()=>controller.abort();
  },[locationId,cursor]);
  useEffect(()=>{const timer=setInterval(()=>setNow(clock.current.server+performance.now()-clock.current.received),1000);return()=>clearInterval(timer);},[]);
  return <section className="config-card" aria-label="Edge device health"><h2>Local AI device health</h2>
    <p>AI estimates are shadow information. Staff decisions and the operational floor map remain separate.</p>
    {error&&<p role="status">{error}</p>}
    {data&&!data.devices.length&&<p>No paired devices at this location.</p>}
    {data?.devices.map(device=>{
      const offline=device.status!=="ACTIVE"||!device.last_contact_at||now-Date.parse(device.last_contact_at)>45000;
      const degraded=!offline&&(device.metrics?.camera!=="ONLINE"||device.metrics?.inference!=="RUNNING"||device.metrics?.queue_pending!==0);
      return <div key={device.id} className={offline||degraded?"notice":"hint"} data-device-id={device.id}>
        <strong>{device.label}: {offline?"OFFLINE / not connected":degraded?"DEGRADED":"ONLINE"}</strong>
        <p>{device.purpose==="SYNTHETIC_WORKFLOW_TEST"?"DEMO transport fixture":"Shadow AI processor"} · Camera: {device.metrics?.camera||"UNKNOWN"} · Inference: {device.metrics?.inference||"UNKNOWN"} · Queued: {device.metrics?.queue_pending??"unknown"}</p>
        {device.last_contact_at&&<p>Last device contact: {new Date(device.last_contact_at).toLocaleString([], {timeZone})}</p>}
      </div>;
    })}
    {data?.shadows.map(shadow=><p key={shadow.binding_id}>Shadow: {shadow.stale||now-Date.parse(shadow.occurred_at)>30000?"UNKNOWN / stale":shadow.state.replaceAll("_"," ")} · {shadow.reason.replaceAll("_"," ")} · Not operational confirmation</p>)}
  </section>;
}
