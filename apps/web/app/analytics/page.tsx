"use client";

import Link from "next/link";
import {useRouter} from "next/navigation";
import {useEffect,useMemo,useRef,useState} from "react";
import type {Location,Me} from "../settings/types";

type Row={table_id:string;table_label:string;bucket_start:string;bucket_end:string;local_label:string;
  occupied_seconds:number|null;state_seconds:Record<string,number>|null;usable_seconds:number;
  known_evidence_seconds:number;unknown_evidence_seconds:number;evidence_coverage:number|null;
  estimated_occupied_seconds:number;estimated_occupied_fraction:number|null};
type Report={from_date:string;to_date_exclusive:string;time_zone:string;group:string;basis:string;synthetic:boolean;as_of:string;
  rows:Row[];summary:{average_occupied_seconds:number|null;completed_occupied_sessions:number;completed_resets:number;
    average_wait_to_clean_seconds:number|null;average_cleaning_seconds:number|null;average_time_to_ready_seconds:number|null;
    open_reset_attempts:number;oldest_open_reset_seconds:number|null;cancelled_attempts:number;corrections_applied:number;
    excluded_sessions:number;excluded_attempts:number;cross_boundary_sessions:number};limitations:string[]};
const managers=["owner","org_admin","manager"];
const minutes=(value:number|null)=>value===null?"Not enough data":`${(value/60).toFixed(1)} min`;
function dateShift(value:string,days:number){const d=new Date(value+"T00:00:00Z");d.setUTCDate(d.getUTCDate()+days);return d.toISOString().slice(0,10);}
function localToday(zone:string){const parts=new Intl.DateTimeFormat("en-US",{timeZone:zone,year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date());
  return ["year","month","day"].map(type=>parts.find(p=>p.type===type)?.value).join("-");}

export default function AnalyticsPage(){
  const router=useRouter();
  const [places,setPlaces]=useState<(Location&{restaurant:string})[]>([]);
  const [locationId,setLocationId]=useState("");
  const [tables,setTables]=useState<{id:string;label:string}[]>([]);const [tableId,setTableId]=useState("");
  const [from,setFrom]=useState("");const [to,setTo]=useState("");
  const [group,setGroup]=useState("day");const [basis,setBasis]=useState("");
  const [report,setReport]=useState<Report|null>(null);const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);const [exporting,setExporting]=useState(false);
  const [refresh,setRefresh]=useState(0);const [page,setPage]=useState(0);const generation=useRef(0);
  const exportController=useRef<AbortController|null>(null);
  const location=places.find(p=>p.id===locationId);
  useEffect(()=>()=>exportController.current?.abort(),[]);
  useEffect(()=>{
    const controller=new AbortController();
    void fetch("/api/v1/me",{cache:"no-store",signal:controller.signal}).then(async response=>{
      if(response.status===401){router.replace("/sign-in");return;}
      if(!response.ok)throw new Error("Unable to load permitted locations.");
      const user:Me=await response.json();if(controller.signal.aborted)return;
      const allowed=user.access.filter(a=>managers.includes(a.role)).flatMap(a=>a.locations.map(l=>({...l,restaurant:a.organization.name})));
      setPlaces(allowed);
      const preferred=new URLSearchParams(window.location.search).get("location");
      const chosen=allowed.find(l=>l.id===preferred)||allowed[0];
      if(chosen){const today=localToday(chosen.time_zone);setFrom(dateShift(today,-6));setTo(dateShift(today,1));setLocationId(chosen.id);}
      else setError("Reports require a manager or administrator role and explicit location access.");
    }).catch(()=>{if(!controller.signal.aborted)setError("Unable to load report access. Refresh or sign in again.");});
    return()=>controller.abort();
  },[router]);
  useEffect(()=>{
    const controller=new AbortController();setTables([]);
    if(locationId)void fetch(`/api/v1/locations/${locationId}/tables`,{cache:"no-store",signal:controller.signal})
      .then(async response=>{if(!response.ok)throw new Error();return response.json();})
      .then(value=>{if(!controller.signal.aborted)setTables(value);})
      .catch(()=>{if(!controller.signal.aborted)setTables([]);});
    return()=>controller.abort();
  },[locationId]);
  const query=useMemo(()=>new URLSearchParams({from,to,group,...(basis?{basis}:{}),...(tableId?{table_id:tableId}:{})}).toString(),[from,to,group,basis,tableId]);
  useEffect(()=>{
    const current=++generation.current;const controller=new AbortController();
    exportController.current?.abort();
    setReport(null);setPage(0);setError("");
    if(!locationId||!from||!to){setBusy(false);return()=>controller.abort();}
    setBusy(true);window.history.replaceState(null,"","/analytics?location="+encodeURIComponent(locationId));
    const timer=setTimeout(()=>{void (async()=>{
      try{
        const response=await fetch(`/api/v1/locations/${locationId}/analytics?${query}`,{cache:"no-store",signal:controller.signal});
        if(current!==generation.current||controller.signal.aborted)return;
        if(response.status===401){router.replace("/sign-in");return;}
        if([403,404].includes(response.status)){setReport(null);throw new Error("Location access changed. Return to the dashboard or sign in again.");}
        if(!response.ok){const detail=await response.json();throw new Error(detail.error?.message||"Report unavailable. Choose a smaller range or refresh.");}
        const value:Report=await response.json();
        if(!controller.signal.aborted&&current===generation.current)setReport(value);
      }catch(reason){if(!controller.signal.aborted&&current===generation.current)setError(reason instanceof Error?reason.message:"Report unavailable.");}
      finally{if(!controller.signal.aborted&&current===generation.current)setBusy(false);}
    })();},200);
    return()=>{clearTimeout(timer);controller.abort();};
  },[locationId,from,to,query,refresh,router]);
  async function download(){
    if(exporting||!report)return;
    const current=generation.current;setExporting(true);setError("");
    const controller=new AbortController();exportController.current=controller;
    const timeout=setTimeout(()=>controller.abort(),60000);
    try{
      const response=await fetch(`/api/v1/locations/${locationId}/analytics.csv?${query}`,{cache:"no-store",signal:controller.signal});
      if(response.status===401){setReport(null);router.replace("/sign-in");return;}
      if([403,404].includes(response.status)){setReport(null);throw new Error("Report access changed. Return to the dashboard or sign in again.");}
      if(!response.ok){const detail=await response.json();throw new Error(detail.error?.message||"Export unavailable.");}
      const blob=await response.blob();
      if(current!==generation.current)return;
      // Next.js may use chunked transfer instead of preserving Content-Length.
      // Validate decoded bytes before offering any report as a complete file.
      const expected=Number(response.headers.get("x-report-bytes"));
      if(!Number.isSafeInteger(expected)||expected<=0||expected>16777216||blob.size!==expected){
        throw new Error("Export incomplete. Refresh and download again; no file was saved.");
      }
      const url=URL.createObjectURL(blob);const link=document.createElement("a");link.href=url;link.download=`restaurant-report-${from}.csv`;link.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
    }catch(reason){if(current===generation.current)setError(reason instanceof Error?reason.message:"Export interrupted. Refresh and sign in if necessary.");}
    finally{clearTimeout(timeout);setExporting(false);if(exportController.current===controller)exportController.current=null;}
  }
  const chart=useMemo(()=>{
    const aggregate=new Map<string,{label:string;seconds:number;usable:number}>();
    report?.rows.forEach(row=>{const value=aggregate.get(row.bucket_start)||{label:row.local_label,seconds:0,usable:0};
      value.seconds+=row.occupied_seconds??row.estimated_occupied_seconds;value.usable+=row.usable_seconds;aggregate.set(row.bucket_start,value);});
    return [...aggregate.entries()];
  },[report]);
  const usable=report?.rows.reduce((n,r)=>n+r.usable_seconds,0)||0;
  const coverage=report?.rows.reduce((n,r)=>n+r.known_evidence_seconds,0)||0;
  return <main className="workspace analytics-workspace">
    <header className="workspace-header"><div><Link className="brand" href="/">Restaurant AI Monitoring</Link><h1>Recorded workflow reports</h1></div>
      <nav aria-label="Workspace navigation"><Link href={`/dashboard?location=${encodeURIComponent(locationId)}`}>Dashboard</Link> · <Link href="/settings">Settings</Link></nav></header>
    <p>Review saved table use and reset times. These records do not establish real-world AI accuracy or prove cleanliness.</p>
    <section className="config-card" aria-label="Report filters"><div className="inline-form">
      <label>Restaurant / location<select value={locationId} onChange={e=>{setReport(null);setTableId("");setTables([]);setLocationId(e.target.value);setBasis("");}}>
        {!places.length&&<option value="">No report access</option>}{places.map(l=><option key={l.id} value={l.id}>{l.restaurant} / {l.name}</option>)}
      </select></label>
      <label>Table<select value={tableId} onChange={e=>setTableId(e.target.value)}><option value="">All configured tables</option>
        {tables.map(t=><option value={t.id} key={t.id}>{t.label}</option>)}</select></label>
      <label>Start date, included<input type="date" value={from} onChange={e=>setFrom(e.target.value)}/></label>
      <label>End date, not included<input type="date" value={to} onChange={e=>setTo(e.target.value)}/></label>
      <label>Group<select value={group} onChange={e=>setGroup(e.target.value)}><option value="day">Daily</option><option value="hour">Hourly</option></select></label>
      <label>Record basis<select value={basis} onChange={e=>setBasis(e.target.value)}><option value="">Location default</option><option value="CONFIRMED_WORKFLOW">Confirmed workflow</option>
        <option value="DEMO">DEMO records</option><option value="LEGACY">Legacy history</option><option value="ESTIMATED_EVIDENCE">AI evidence estimates</option></select></label>
      <button disabled={busy||!locationId} onClick={()=>setRefresh(v=>v+1)}>Refresh report</button>
      <button className="secondary" disabled={busy||exporting||!report} onClick={()=>void download()}>{exporting?"Preparing export…":"Download CSV"}</button>
    </div><p className="hint">Dates use {location?.time_zone||"the selected location's time zone"}. Maximum 31 local days. Changing a location clears the previous result. Reports refresh on request.</p></section>
    {busy&&<p role="status">Calculating saved history…</p>}{error&&<p role="alert" className="error">{error}</p>}
    {report&&<>
      <p className={report.synthetic?"demo-notice":"notice"}><strong>{report.synthetic?"DEMO — synthetic records. ":""}{report.basis.replaceAll("_"," ")}</strong> · Cutoff {new Date(report.as_of).toLocaleString([], {timeZone:report.time_zone})} · {report.time_zone}</p>
      <p className="notice">Qualified camera evidence covers {usable?(100*coverage/usable).toFixed(1)+"%":"an unknown share"} of usable table-time. Gaps are unknown, never empty or ready. Model scores are not accuracy percentages.</p>
      <section className="report-summary" aria-label="Report summary">
        {[['Average recorded occupancy',minutes(report.summary.average_occupied_seconds)],['Completed occupied sessions',report.summary.completed_occupied_sessions],
          ['Completed resets',report.summary.completed_resets],['Wait to start cleaning',minutes(report.summary.average_wait_to_clean_seconds)],
          ['Cleaning duration',minutes(report.summary.average_cleaning_seconds)],['Time to ready, including waiting',minutes(report.summary.average_time_to_ready_seconds)],
          ['Open resets at cutoff',report.summary.open_reset_attempts],['Cancelled attempts',report.summary.cancelled_attempts]].map(([label,value])=><article key={label}><span>{label}</span><strong>{value}</strong></article>)}
      </section>
      <section className="config-card" aria-label="Occupancy chart"><h2>{report.basis==="ESTIMATED_EVIDENCE"?"Estimated occupied evidence":"Recorded occupied time"}</h2>
        <p className="hint">Minutes summed across tables. Bar length compares recorded occupied time with usable table-time; it is not a validated restaurant occupancy rate. Hour labels include UTC offsets for repeated daylight-saving hours.</p>
        <div className="report-bars">{chart.slice(0,100).map(([id,bucket])=><div className="report-bar" key={id}>
          <span>{bucket.label.replace("T"," ")} · {minutes(bucket.seconds)}</span><div role="img" aria-label={`${bucket.label}: ${minutes(bucket.seconds)}`}>
            <span style={{width:Math.max(0,Math.min(100,bucket.usable?100*bucket.seconds/bucket.usable:0))+"%"}}/></div></div>)}</div>
        {chart.length>100&&<p>Chart shows the first 100 buckets. All permitted buckets remain in the table and CSV.</p>}
      </section>
      <section className="config-card" aria-label="Table duration report"><h2>Table durations</h2>
        <div className="report-scroll"><table className="report-table"><caption>All durations below are minutes. Unknown evidence stays separate from staff-confirmed table states.</caption>
          <thead><tr>{['Table','Local bucket','Occupied','Ready','Reset pending','Cleaning','Unknown','Out of service','Evidence coverage'].map(s=><th key={s} scope="col">{s}</th>)}</tr></thead>
          <tbody>{report.rows.slice(page*100,page*100+100).map(row=><tr key={row.table_id+":"+row.bucket_start}><th scope="row">{row.table_label}</th><td>{row.local_label.replace("T"," ")}</td>
            {['OCCUPIED','AVAILABLE','RESET_PENDING','CLEANING','UNKNOWN','OUT_OF_SERVICE'].map(state=><td key={state}>{row.state_seconds?(row.state_seconds[state]/60).toFixed(1):"Not applicable"}</td>)}
            <td>{row.evidence_coverage===null?"Not enough data":(100*row.evidence_coverage).toFixed(1)+"%"}</td></tr>)}</tbody></table></div>
        {!report.rows.length&&<p>No configured table-time in this selection.</p>}
        <div className="report-pagination"><button className="secondary" disabled={page===0} onClick={()=>setPage(p=>p-1)}>Previous rows</button>
          <span>Showing {report.rows.length?page*100+1:0}–{Math.min((page+1)*100,report.rows.length)} of {report.rows.length}</span>
          <button className="secondary" disabled={(page+1)*100>=report.rows.length} onClick={()=>setPage(p=>p+1)}>Next rows</button></div>
      </section>
      <section className="config-card"><h2>How to read this report</h2><ul>{report.limitations.map(text=><li key={text}>{text}</li>)}</ul>
        <p>Visits beginning before the selected dates: {report.summary.cross_boundary_sessions}. Average visit duration includes the full recorded visit; daily and hourly state times include only the selected period.</p>
        <p>Corrections applied: {report.summary.corrections_applied}. Excluded incomplete/invalid sessions: {report.summary.excluded_sessions}; reset attempts: {report.summary.excluded_attempts}.</p>
        <p>CSV includes one report-summary row followed by table/bucket rows. Unsafe spreadsheet labels receive a visible “Text:” prefix. A new export has its own cutoff and can include changes since this preview.</p>
      </section>
    </>}
  </main>;
}
