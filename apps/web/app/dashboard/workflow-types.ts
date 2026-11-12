export type Evidence = {kind:"POSITIVE"|"VACANT"|"UNCERTAIN";quality:string;detector_score:number|null;
  covered_seconds:number;window_seconds:number;visibility_reviewed:boolean};
export type Suggestion = {id:string;table_id:string;session_id:string|null;action:"ARRIVAL"|"DEPARTURE";
  revision:number;table_revision:number;policy_revision:number;status:string;created_at:string;expires_at:string;
  observed_at:string;actionable:boolean;evidence:Evidence};
export type TableContext = {table_id:string;table_revision:number;controlled:boolean;verified_ready:boolean;
  ready_eligible:boolean;session_id:string|null;attempt_id:string|null;pending_since:string|null;
  evidence_at:string|null;evidence_kind:string|null;evidence_live:boolean;needs_source_review:boolean};
export type WorkflowView = {mode:"OFF"|"ASSISTED_REVIEW";policy_revision:number;server_time:string;cursor:string;
  tables:TableContext[];suggestions:Suggestion[];tables_truncated:boolean;suggestions_truncated:boolean};
export function fresh(context:TableContext|undefined,now:number) {
  return !!context?.evidence_live && !!context.evidence_at && !!now
    && now-Date.parse(context.evidence_at)<=15000 && now-Date.parse(context.evidence_at)>=-2000;
}
