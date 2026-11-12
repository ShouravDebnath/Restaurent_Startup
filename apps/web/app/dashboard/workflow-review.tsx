"use client";

import {useEffect,useState} from "react";
import type {Table} from "./types";
import type {WorkflowView} from "./workflow-types";

type Policy={mode:"OFF"|"ASSISTED_REVIEW";revision:number;bindings:string[];
  rules:{arrival_seconds:number;departure_seconds:number;[key:string]:number}};
type Binding={id:string;table_id:string;enabled:boolean;device_id:string};
type Props={locationId:string;view:WorkflowView;tables:Table[];selected:Table|undefined;manager:boolean;
  synthetic:boolean;disabled:boolean;now:number;timeZone:string;
  submit:(path:string,body:object,method?:"POST"|"PUT")=>void};

export function WorkflowReview({locationId,view,tables,selected,manager,synthetic,disabled,now,timeZone,submit}:Props) {
  const [checked,setChecked]=useState<Record<string,boolean>>({});
  const [reasons,setReasons]=useState<Record<string,string>>({});
  const [policy,setPolicy]=useState<Policy|null>(null);
  const [bindings,setBindings]=useState<Binding[]>([]);
  const [chosen,setChosen]=useState<string[]>([]);
  const [approve,setApprove]=useState(false);
  const [error,setError]=useState("");
  const [correctChecked,setCorrectChecked]=useState(false);
  useEffect(()=>{setCorrectChecked(false);},[selected?.id,selected?.operational_revision]);
  useEffect(()=>{
    const controller=new AbortController();
    setPolicy(null);setBindings([]);setChosen([]);setApprove(false);setError("");
    if(manager)void (async()=>{
      try{
        const prefix=`/api/v1/locations/${locationId}`;
        const [p,d]=await Promise.all([fetch(prefix+"/workflow-policy",{cache:"no-store",signal:controller.signal}),
          fetch(prefix+"/devices",{cache:"no-store",signal:controller.signal})]);
        if(!p.ok||!d.ok)throw new Error("Review settings are unavailable. Refresh or sign in again.");
        const saved:Policy=await p.json();
        const devices:{bindings:Binding[];devices:{id:string;purpose:string;status:string}[]}=await d.json();
        if(controller.signal.aborted)return;
        setPolicy(saved);setChosen(saved.bindings);
        setBindings((devices.bindings||[]).filter(b=>b.enabled&&devices.devices.some(x=>x.id===b.device_id&&x.purpose==="AI_SHADOW"&&x.status==="ACTIVE")));
      }catch(reason){if(!controller.signal.aborted)setError(reason instanceof Error?reason.message:"Review settings unavailable.");}
    })();
    return()=>controller.abort();
  },[locationId,manager,view.policy_revision]);
  const context=view.tables.find(t=>t.table_id===selected?.id);
  function changeMode(mode:"OFF"|"ASSISTED_REVIEW"){
    if(!policy)return;
    submit(`/api/v1/locations/${locationId}/workflow-policy`,{mode,expected_revision:policy.revision,
      request_key:crypto.randomUUID(),bindings:mode==="OFF"?policy.bindings:chosen,rules:policy.rules},"PUT");
  }
  return <section className="config-card review-panel" aria-label="Reviewed AI suggestions">
    <div className="panel-heading"><h2>Needs review</h2><span className="badge">{view.mode==="OFF"?"Suggestions OFF":"Human review enabled"}</span></div>
    <p>AI suggests a possible change. Check the physical table before confirming. It cannot confirm cleanliness or mark a table ready.</p>
    {view.suggestions_truncated&&<p role="alert" className="offline-banner">More suggestions exist than this overview can show. Review them in smaller batches.</p>}
    {!view.suggestions.length&&<p>{view.mode==="OFF"?"Existing table controls and shadow processing remain separate.":"No pending arrival or departure suggestions."}</p>}
    <div className="review-list">{view.suggestions.map(s=>{
      const key=s.id+":"+s.revision;
      const active=s.actionable&&now<Date.parse(s.expires_at);
      const reason=reasons[key]||(s.action==="ARRIVAL"?"staff_crossing":"guests_still_present");
      const label=tables.find(t=>t.id===s.table_id)?.label||"Table";
      return <article key={s.id} className="review-card" data-suggestion-id={s.id}>
        <h3>{label}: possible {s.action.toLowerCase()}</h3>
        <p>{active?"Check before confirming":"Expired or changed — waiting for fresh qualified evidence"}</p>
        <p className="hint">Observed {new Date(s.observed_at).toLocaleTimeString([], {timeZone})} · Evidence {s.evidence.quality.toLowerCase()} · {s.evidence.covered_seconds.toFixed(1)} seconds supported.
          {s.evidence.detector_score!==null?` Model score ${s.evidence.detector_score.toFixed(2)}; this is not an accuracy measurement.`:" Vacancy has no person-confidence percentage."}</p>
        <label className="check"><input type="checkbox" checked={!!checked[key]} disabled={disabled||!active}
          onChange={e=>setChecked(v=>({...v,[key]:e.target.checked}))}/>I checked this table: {s.action==="ARRIVAL"?"guests are present":"guests have left"}.</label>
        <div className="review-actions"><button disabled={disabled||!active||!checked[key]} onClick={()=>submit(
          `/api/v1/locations/${locationId}/workflow-suggestions/${s.id}/decisions`,{action:"confirm",expected_revision:s.table_revision,
            expected_suggestion_revision:s.revision,request_key:crypto.randomUUID(),confirmed:true})}>Confirm {s.action.toLowerCase()}</button>
          <label>Dismissal reason<select disabled={disabled||!active} value={reason} onChange={e=>setReasons(v=>({...v,[key]:e.target.value}))}>
            <option value="staff_crossing">Passing staff member</option><option value="wrong_table">Wrong table</option>
            <option value="guests_still_present">Guests still present</option><option value="insufficient_view">Insufficient view</option><option value="other">Other</option>
          </select></label>
          <button className="secondary" disabled={disabled||!active} onClick={()=>submit(
            `/api/v1/locations/${locationId}/workflow-suggestions/${s.id}/decisions`,{action:"dismiss",expected_revision:s.table_revision,
              expected_suggestion_revision:s.revision,request_key:crypto.randomUUID(),confirmed:false,reason})}>Dismiss suggestion</button>
        </div>
      </article>;
    })}</div>
    {manager&&context?.controlled&&context.session_id&&selected&&["OCCUPIED","RESET_PENDING"].includes(selected.current_state)&&
      <details className="manager-correction"><summary>Manager correction for {selected.label}</summary>
        <p>{selected.current_state==="RESET_PENDING"?"Correct a mistaken departure while the guests are still present. The cancelled cleaning attempt stays in history.":context.needs_source_review?"The source restarted or changed. Check whether this is still the same table-use session; reconnecting its evidence keeps the original occupancy timer.":"Correct an arrival accepted for the wrong table. The state returns to unknown, not ready."}</p>
        <label className="check"><input type="checkbox" checked={correctChecked} disabled={disabled} onChange={e=>setCorrectChecked(e.target.checked)}/>I physically checked this table and confirm the selected manager action is correct.</label>
        {context.needs_source_review&&selected.current_state==="OCCUPIED"&&<button disabled={disabled||!correctChecked||!context.evidence_live} onClick={()=>submit(`/api/v1/tables/${selected.id}/workflow-actions`,{
          action:"reconcile_source",expected_revision:context.table_revision,request_key:crypto.randomUUID(),confirmed:true,
          session_id:context.session_id,reason:"source_restarted"})}>Reconnect the same table session</button>}
        <button className="secondary" disabled={disabled||!correctChecked} onClick={()=>submit(`/api/v1/tables/${selected.id}/workflow-actions`,{
          action:selected.current_state==="RESET_PENDING"?"correct_departure":"correct_arrival",expected_revision:context.table_revision,
          request_key:crypto.randomUUID(),confirmed:true,session_id:context.session_id,
          reason:selected.current_state==="RESET_PENDING"?"guests_still_present":"wrong_table"})}>Record correction</button>
      </details>}
    {manager&&<details><summary>Manager review settings</summary>
      {error&&<p role="status">{error}</p>}
      {!synthetic&&<p>Initial activation is limited to explicitly synthetic local test locations. Existing restaurant locations stay off.</p>}
      {policy&&<><p>Approved evidence settings: arrival {policy.rules.arrival_seconds}s, departure {policy.rules.departure_seconds}s. These development thresholds have not been validated on restaurant footage.</p>
        {synthetic&&policy.mode==="OFF"&&<>
          <fieldset><legend>Synthetic tables to include</legend>{bindings.map(b=><label className="check" key={b.id}>
            <input type="checkbox" checked={chosen.includes(b.id)} disabled={disabled} onChange={e=>setChosen(v=>e.target.checked?[...v,b.id]:v.filter(id=>id!==b.id))}/>
            {tables.find(t=>t.id===b.table_id)?.label||"Configured table"}</label>)}
            {!bindings.length&&<p>First approve a synthetic device and its camera/table binding in Settings.</p>}
          </fieldset>
          <label className="check"><input type="checkbox" checked={approve} disabled={disabled} onChange={e=>setApprove(e.target.checked)}/>I approve these settings and human review for the selected DEMO tables.</label>
          <button disabled={disabled||!approve||!chosen.length} onClick={()=>changeMode("ASSISTED_REVIEW")}>Enable reviewed DEMO suggestions</button>
        </>}
        {policy.mode==="ASSISTED_REVIEW"&&<><p>Turning suggestions off preserves tasks and decisions. Fresh approved evidence is still required to finish a protected readiness check.</p>
          <button className="secondary" disabled={disabled} onClick={()=>changeMode("OFF")}>Turn suggestions off</button></>}
      </>}
    </details>}
  </section>;
}
