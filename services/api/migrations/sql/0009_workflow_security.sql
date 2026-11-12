-- Phase 7: explicit human authority, additive provenance, OFF until approved.
-- Applied versions 0001-0008 stay byte-identical. No existing row is rewritten.
DO $$ DECLARE name_ text; BEGIN
    FOREACH name_ IN ARRAY ARRAY['workflow_policies','workflow_sessions','workflow_evidence',
        'workflow_suggestions','workflow_task_attempts','workflow_decisions','workflow_policy_history','workflow_journal','workflow_quality_boundaries'] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',name_);
        EXECUTE format('CREATE POLICY workflow_read ON public.%I FOR SELECT USING(
            security.allowed_location(organization_id,location_id) AND
            security.has_role(organization_id,ARRAY[''owner'',''org_admin'',''manager'',''staff'']))',name_);
        EXECUTE format('CREATE TRIGGER immutable_ownership BEFORE UPDATE ON public.%I
            FOR EACH ROW EXECUTE FUNCTION security.immutable_ownership(''organization_id'',''location_id'')',name_);
    END LOOP;
END $$;

CREATE FUNCTION security.workflow_rules_digest(rules_ jsonb) RETURNS text
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $$
    SELECT encode(sha256(convert_to('{'||string_agg(to_json(key)::text||':'||value::text,',' ORDER BY key)||'}','UTF8')),'hex')
    FROM jsonb_each(rules_)
$$;

CREATE FUNCTION security.workflow_quality(e_ jsonb,rules_ jsonb) RETURNS boolean
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog AS $$
DECLARE q jsonb:=e_->'evidence'; kind_ text:=q->>'kind'; duration_ numeric;
BEGIN
    IF jsonb_typeof(q)<>'object' OR jsonb_typeof(q->'visibility_reviewed')<>'boolean'
        OR q->>'visibility_reviewed'<>'true'
        OR NOT (q->>'quality'='HIGH' OR (kind_='VACANT' AND q->>'quality'='MEDIUM'))
        OR kind_ NOT IN ('POSITIVE','VACANT') THEN RETURN false; END IF;
    IF q->>'sample_count' IS NULL OR q->>'frame_age_seconds' IS NULL OR q->>'window_seconds' IS NULL
        OR q->>'covered_seconds' IS NULL OR q->>'max_gap_seconds' IS NULL THEN RETURN false; END IF;
    IF (q->>'sample_count')::numeric<(rules_->>'min_samples')::numeric
        OR (q->>'sample_count')::numeric>10000
        OR (q->>'frame_age_seconds')::numeric NOT BETWEEN 0 AND (rules_->>'result_max_age')::numeric
        OR (q->>'max_gap_seconds')::numeric NOT BETWEEN 0 AND (rules_->>'max_gap_seconds')::numeric
        OR (q->>'window_seconds')::numeric NOT BETWEEN .001 AND 310
        OR (q->>'covered_seconds')::numeric<0
        OR (q->>'covered_seconds')::numeric>(q->>'window_seconds')::numeric+.000001
        OR (q->>'covered_seconds')::numeric/(q->>'window_seconds')::numeric<(rules_->>'minimum_coverage')::numeric
        THEN RETURN false; END IF;
    duration_:=CASE WHEN kind_='POSITIVE' THEN (rules_->>'arrival_seconds')::numeric
                   ELSE (rules_->>'departure_seconds')::numeric END;
    IF (q->>'covered_seconds')::numeric<duration_ THEN RETURN false; END IF;
    IF kind_='POSITIVE' AND (q->>'detector_score' IS NULL OR q->>'association_score' IS NULL
        OR (q->>'detector_score')::numeric NOT BETWEEN (rules_->>'retention_score')::numeric AND 1
        OR (q->>'association_score')::numeric NOT BETWEEN .5 AND 1) THEN RETURN false; END IF;
    IF kind_='VACANT' AND q->>'detector_score' IS NOT NULL THEN RETURN false; END IF;
    RETURN true;
EXCEPTION WHEN invalid_text_representation OR division_by_zero OR numeric_value_out_of_range THEN RETURN false;
END $$;

CREATE FUNCTION security.workflow_receive() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE e jsonb:=NEW.payload; p public.workflow_policies; b public.edge_bindings;
    a public.edge_assignments; d public.edge_devices; t public.dining_tables; h public.edge_health;
    q jsonb; valid_ boolean:=false; why_ text:='CONTEXT'; action_ text; s public.workflow_sessions;
    pending_ public.workflow_suggestions; moment_ timestamptz:=clock_timestamp(); observed_ timestamptz;
BEGIN
    IF OLD.disposition<>'pending' OR NEW.disposition='pending' OR e->>'version'<>'2'
        OR coalesce((e->>'_rejected')::boolean,false) THEN RETURN NEW; END IF;
    SELECT * INTO p FROM public.workflow_policies WHERE location_id=NEW.location_id;
    IF p.location_id IS NULL OR p.mode<>'ASSISTED_REVIEW' THEN RETURN NEW; END IF;
    SELECT * INTO b FROM public.edge_bindings WHERE id=(e->>'binding_id')::uuid;
    SELECT * INTO a FROM public.edge_assignments WHERE id=b.assignment_id;
    SELECT * INTO d FROM public.edge_devices WHERE id=NEW.device_id;
    SELECT * INTO t FROM public.dining_tables WHERE id=b.table_id;
    SELECT * INTO h FROM public.edge_health WHERE device_id=d.id;
    q:=e->'evidence'; observed_:=(e->>'occurred_at')::timestamptz;
    IF NEW.disposition IN ('shadow','history') AND NEW.reason IN ('ACCEPTED','PROTECTED')
        AND d.status='ACTIVE' AND d.purpose='AI_SHADOW' AND d.processing_enabled AND b.enabled AND a.enabled
        AND b.device_id=d.id AND b.location_id=p.location_id AND p.bindings ? b.id::text
        AND b.epoch=(e->>'binding_epoch')::uuid AND b.zone_revision=(e->>'zone_revision')::integer
        AND a.profile_sha256=e->>'profile_sha256' AND a.profile_revision=(e->>'profile_revision')::integer
        AND a.model_sha256=e->>'model_sha256' AND a.policy_revision=(e->>'policy_revision')::integer
        AND p.revision=(e->>'workflow_revision')::integer AND p.rules_sha256=e->>'rules_sha256'
        AND t.operational_revision=(e->>'manual_revision')::integer
        AND observed_>=p.enabled_since AND observed_>=moment_-interval '30 seconds'
        AND observed_<=moment_+interval '2 seconds'
        AND h.measured_at>moment_-interval '45 seconds' AND h.metrics->>'camera'='ONLINE'
        AND h.metrics->>'inference'='RUNNING'
        AND NOT EXISTS(SELECT 1 FROM public.edge_shadows sh WHERE sh.binding_id=b.id AND sh.needs_context
            AND sh.source_generation IS NOT DISTINCT FROM (e->>'source_generation')::uuid)
        AND security.workflow_quality(e,p.rules) THEN
        valid_:=true; why_:='QUALIFIED';
        -- Legacy ingestion deliberately preserves CLEANING/OUT_OF_SERVICE. For
        -- valid V2 evidence from a NEW generation only, finish its separate
        -- rejection-context recovery without changing any operational state.
        IF NEW.reason='PROTECTED' THEN
            UPDATE public.edge_shadows SET needs_context=false,source_generation=(e->>'source_generation')::uuid,
                sequence=NEW.sequence,state='UNKNOWN',reason='FRESH_PROTECTED_CONTEXT',occurred_at=observed_
                WHERE binding_id=b.id AND needs_context
                AND source_generation IS DISTINCT FROM (e->>'source_generation')::uuid;
        END IF;
    ELSIF NEW.reason NOT IN ('ACCEPTED','PROTECTED') THEN why_:=NEW.reason;
    ELSE why_:='LOW_QUALITY_OR_STALE'; END IF;
    INSERT INTO public.workflow_evidence(receipt_id,organization_id,location_id,table_id,device_id,binding_id,
        source_generation,policy_revision,manual_revision,observed_at,valid_until,kind,qualified,reason,summary)
    VALUES(NEW.event_id,NEW.organization_id,NEW.location_id,b.table_id,d.id,b.id,(e->>'source_generation')::uuid,
        (e->>'workflow_revision')::integer,(e->>'manual_revision')::integer,observed_,
        observed_+CASE WHEN valid_ THEN interval '15 seconds' ELSE interval '0 seconds' END,
        CASE WHEN valid_ THEN q->>'kind' ELSE 'UNCERTAIN' END,valid_,why_,q);
    -- Any current contrary/uncertain context withdraws old actionable suggestions.
    UPDATE public.workflow_suggestions SET status='SUPERSEDED',revision=revision+1
        WHERE table_id=t.id AND status='PENDING' AND (NOT valid_ OR table_revision<>t.operational_revision
            OR policy_revision<>p.revision OR source_generation<>(e->>'source_generation')::uuid
            OR (e->>'occupancy_session_id' IS NOT NULL AND source_episode<>(e->>'occupancy_session_id')::uuid)
            OR (action='ARRIVAL' AND q->>'kind'<>'POSITIVE')
            OR (action='DEPARTURE' AND q->>'kind'<>'VACANT'));
    IF NOT valid_ OR t.current_state IN ('CLEANING','OUT_OF_SERVICE') THEN RETURN NEW; END IF;
    action_:=CASE WHEN q->>'kind'='POSITIVE' THEN 'ARRIVAL' ELSE 'DEPARTURE' END;
    SELECT * INTO pending_ FROM public.workflow_suggestions WHERE table_id=t.id AND status='PENDING' AND action=action_;
    IF pending_.id IS NOT NULL THEN
        UPDATE public.workflow_suggestions SET latest_receipt_id=NEW.event_id,
            expires_at=least(observed_+interval '15 seconds',moment_+interval '15 seconds'),revision=revision+1 WHERE id=pending_.id;
        RETURN NEW;
    END IF;
    -- A snapshot or human-state echo cannot create a new arrival/departure.
    IF e->>'evidence_type'<>'transition' OR e->>'occupancy_session_id' IS NULL
        OR (action_='ARRIVAL' AND (e->>'reason'<>'STABLE_PERSON' OR e->>'state'<>'OCCUPIED'
             OR (q->>'detector_score')::numeric<(p.rules->>'entry_score')::numeric))
        OR (action_='DEPARTURE' AND (e->>'reason'<>'STABLE_VACANCY' OR e->>'state'<>'RESET_PENDING')) THEN RETURN NEW; END IF;
    IF EXISTS(SELECT 1 FROM public.workflow_suggestions old_ WHERE old_.binding_id=b.id
        AND old_.source_generation=(e->>'source_generation')::uuid
        AND old_.source_episode=(e->>'occupancy_session_id')::uuid AND old_.action=action_
        AND old_.status IN ('ACCEPTED','DISMISSED')) THEN RETURN NEW; END IF;
    IF action_='ARRIVAL' THEN
        IF t.current_state NOT IN ('UNKNOWN','AVAILABLE') OR EXISTS(SELECT 1 FROM public.staff_tasks
            WHERE table_id=t.id AND status IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS')) THEN RETURN NEW; END IF;
        IF EXISTS(SELECT 1 FROM public.workflow_sessions WHERE binding_id=b.id
            AND source_generation=(e->>'source_generation')::uuid AND source_episode=(e->>'occupancy_session_id')::uuid)
            THEN RETURN NEW; END IF;
    ELSE
        SELECT * INTO s FROM public.workflow_sessions WHERE id=t.occupancy_session_id AND table_id=t.id
            AND binding_id=b.id AND source_generation=(e->>'source_generation')::uuid
            AND source_episode=(e->>'occupancy_session_id')::uuid AND status='OPEN';
        IF t.current_state<>'OCCUPIED' OR s.id IS NULL THEN RETURN NEW; END IF;
    END IF;
    INSERT INTO public.workflow_suggestions(id,organization_id,location_id,table_id,device_id,binding_id,
        source_generation,source_episode,receipt_id,latest_receipt_id,session_id,action,table_revision,policy_revision,expires_at)
    VALUES(gen_random_uuid(),NEW.organization_id,NEW.location_id,t.id,d.id,b.id,(e->>'source_generation')::uuid,
        (e->>'occupancy_session_id')::uuid,NEW.event_id,NEW.event_id,s.id,action_,t.operational_revision,p.revision,
        least(observed_+interval '15 seconds',moment_+interval '15 seconds'));
    RETURN NEW;
END $$;
CREATE TRIGGER workflow_receive AFTER UPDATE OF disposition ON public.edge_receipts
    FOR EACH ROW EXECUTE FUNCTION security.workflow_receive();

CREATE FUNCTION security.workflow_live(receipt_ uuid) RETURNS boolean
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
    SELECT EXISTS(SELECT 1 FROM public.workflow_evidence e
        JOIN public.edge_receipts r ON r.event_id=e.receipt_id
        JOIN public.workflow_policies p ON p.location_id=e.location_id
        JOIN public.edge_bindings b ON b.id=e.binding_id
        JOIN public.edge_assignments a ON a.id=b.assignment_id
        JOIN public.edge_devices d ON d.id=e.device_id
        JOIN public.edge_health h ON h.device_id=d.id
        JOIN public.dining_tables t ON t.id=e.table_id
        WHERE e.receipt_id=receipt_ AND security.allowed_location(e.organization_id,e.location_id)
        AND e.qualified AND e.valid_until>clock_timestamp() AND e.observed_at<=clock_timestamp()+interval '2 seconds'
        AND p.mode='ASSISTED_REVIEW' AND p.revision=e.policy_revision AND p.bindings ? b.id::text
        AND p.rules_sha256=r.payload->>'rules_sha256' AND e.observed_at>=p.enabled_since
        AND t.operational_revision=e.manual_revision AND d.status='ACTIVE' AND d.processing_enabled
        AND b.enabled AND a.enabled AND b.epoch=(r.payload->>'binding_epoch')::uuid
        AND a.profile_sha256=r.payload->>'profile_sha256' AND a.model_sha256=r.payload->>'model_sha256'
        AND a.profile_revision=(r.payload->>'profile_revision')::integer
        AND a.policy_revision=(r.payload->>'policy_revision')::integer
        AND EXISTS(SELECT 1 FROM public.table_zones z WHERE z.table_id=t.id AND z.camera_id=b.camera_id AND z.revision=b.zone_revision)
        AND h.measured_at>clock_timestamp()-interval '45 seconds' AND h.metrics->>'camera'='ONLINE' AND h.metrics->>'inference'='RUNNING'
        AND EXISTS(SELECT 1 FROM public.edge_keys k WHERE k.device_id=d.id AND NOT k.revoked AND k.expires_at>clock_timestamp())
        AND NOT EXISTS(SELECT 1 FROM public.edge_shadows sh WHERE sh.binding_id=b.id AND sh.needs_context)
        AND NOT EXISTS(SELECT 1 FROM public.workflow_evidence newer JOIN public.edge_receipts nr ON nr.event_id=newer.receipt_id
            WHERE newer.binding_id=e.binding_id AND nr.sequence>r.sequence))
$$;

CREATE FUNCTION security.workflow_task_projection() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE s public.workflow_sessions; a public.workflow_task_attempts; number_ integer; moment_ timestamptz:=clock_timestamp();
BEGIN
    SELECT * INTO s FROM public.workflow_sessions WHERE id=NEW.occupancy_session_id
        AND table_id=NEW.table_id AND organization_id=NEW.organization_id AND location_id=NEW.location_id;
    IF s.id IS NULL THEN RETURN NEW; END IF;
    SELECT * INTO a FROM public.workflow_task_attempts WHERE task_id=NEW.id ORDER BY number DESC LIMIT 1;
    IF NEW.status='OPEN' AND (a.id IS NULL OR (a.status='CANCELLED' AND TG_OP='UPDATE' AND OLD.status='CANCELLED')) THEN
        number_:=coalesce(a.number,0)+1;
        INSERT INTO public.workflow_task_attempts(id,organization_id,location_id,task_id,session_id,number,pending_since,status)
        VALUES(gen_random_uuid(),NEW.organization_id,NEW.location_id,NEW.id,s.id,number_,moment_,'OPEN');
    ELSIF a.id IS NOT NULL AND a.status IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS') THEN
        UPDATE public.workflow_task_attempts SET status=NEW.status,acknowledged_at=NEW.acknowledged_at,
            started_at=NEW.started_at,completed_at=CASE WHEN NEW.status='COMPLETED' THEN NEW.completed_at ELSE NULL END,
            cancelled_at=CASE WHEN NEW.status='CANCELLED' THEN NEW.completed_at ELSE NULL END,resolution=NEW.resolution WHERE id=a.id;
    END IF;
    IF NEW.status='COMPLETED' THEN
        UPDATE public.workflow_sessions SET status='COMPLETE',ready_at=NEW.completed_at WHERE id=s.id;
    ELSIF NEW.status='CANCELLED' AND NEW.resolution='manager_blocked' THEN
        UPDATE public.workflow_sessions SET status='INVALIDATED' WHERE id=s.id;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER workflow_task_projection AFTER INSERT OR UPDATE ON public.staff_tasks
    FOR EACH ROW EXECUTE FUNCTION security.workflow_task_projection();

CREATE FUNCTION security.workflow_journal_capture() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE session_ uuid; attempt_ uuid; basis_ text;
BEGIN
    SELECT id INTO session_ FROM public.workflow_sessions WHERE table_id=NEW.table_id
        AND (id=(NEW.payload->>'session_id')::uuid OR id=(SELECT occupancy_session_id FROM public.dining_tables WHERE id=NEW.table_id))
        ORDER BY arrived_at DESC LIMIT 1;
    IF session_ IS NULL AND NEW.event_type='table.mark_ready' THEN
        SELECT id INTO session_ FROM public.workflow_sessions WHERE table_id=NEW.table_id AND ready_at=NEW.occurred_at LIMIT 1;
    END IF;
    SELECT a.id INTO attempt_ FROM public.workflow_task_attempts a WHERE a.session_id=session_ ORDER BY number DESC LIMIT 1;
    basis_:=CASE WHEN EXISTS(SELECT 1 FROM public.location_operations WHERE location_id=NEW.location_id AND is_synthetic)
        THEN 'DEMO' WHEN session_ IS NOT NULL OR NEW.event_type LIKE 'workflow.%' THEN 'CONFIRMED_WORKFLOW' ELSE 'LEGACY' END;
    INSERT INTO public.workflow_journal(event_id,organization_id,location_id,table_id,session_id,attempt_id,occurred_at,basis)
        VALUES(NEW.id,NEW.organization_id,NEW.location_id,NEW.table_id,session_,attempt_,NEW.occurred_at,basis_);
    RETURN NEW;
END $$;
CREATE TRIGGER workflow_journal_capture AFTER INSERT ON public.table_events
    FOR EACH ROW EXECUTE FUNCTION security.workflow_journal_capture();

CREATE FUNCTION security.workflow_quality_boundary() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE why_ text; h public.edge_health;
BEGIN
    IF NOT EXISTS(SELECT 1 FROM public.workflow_policies WHERE location_id=NEW.location_id) THEN RETURN NEW; END IF;
    why_:=CASE NEW.kind WHEN 'offline' THEN 'OFFLINE' WHEN 'configuration' THEN 'CONFIG_CHANGED'
        WHEN 'workflow' THEN 'POLICY_CHANGED' ELSE NULL END;
    IF NEW.kind='health' THEN
        SELECT * INTO h FROM public.edge_health WHERE device_id=NEW.device_id;
        IF h.metrics->>'camera'<>'ONLINE' OR h.metrics->>'inference'<>'RUNNING' THEN why_:='DEGRADED'; END IF;
    END IF;
    IF why_ IS NOT NULL THEN
        INSERT INTO public.workflow_quality_boundaries(organization_id,location_id,revision,device_id,occurred_at,reason)
            VALUES(NEW.organization_id,NEW.location_id,NEW.revision,NEW.device_id,NEW.created_at,why_);
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER workflow_quality_boundary AFTER INSERT ON public.location_notifications
    FOR EACH ROW EXECUTE FUNCTION security.workflow_quality_boundary();

CREATE FUNCTION security.workflow_event(table_ uuid,old_ text,action_ text,details_ jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE t public.dining_tables; seq_ integer; id_ uuid:=gen_random_uuid(); moment_ timestamptz:=clock_timestamp();
BEGIN
    SELECT * INTO STRICT t FROM public.dining_tables WHERE id=table_;
    UPDATE public.location_operations SET revision=revision+1 WHERE location_id=t.location_id RETURNING revision INTO seq_;
    INSERT INTO public.table_events(id,organization_id,location_id,table_id,revision,event_type,source,actor_id,
        occurred_at,ingested_at,previous_state,new_state,payload)
    VALUES(id_,t.organization_id,t.location_id,t.id,seq_,'workflow.'||action_,'manual',security.actor(),moment_,moment_,old_,t.current_state,
        details_||jsonb_build_object('table_revision',t.operational_revision,
            'session_id',coalesce(t.occupancy_session_id,(details_->>'session_id')::uuid)));
    INSERT INTO public.audit_logs(id,organization_id,location_id,actor_id,action,details)
        VALUES(gen_random_uuid(),t.organization_id,t.location_id,security.actor(),'workflow.'||action_,
            details_||jsonb_build_object('event_id',id_,'table_id',t.id,'previous_state',old_,'new_state',t.current_state));
    RETURN jsonb_build_object('table_id',t.id,'event_id',id_,'revision',t.operational_revision,
        'state',t.current_state,'cursor',t.location_id::text||':'||seq_::text);
END $$;

-- Direct legacy entry is made internal. Existing OFF/unenrolled behavior stays intact.
ALTER FUNCTION security.table_action(uuid,text,integer,uuid,text,uuid,boolean,text,boolean,boolean) RENAME TO workflow_legacy_action;
CREATE FUNCTION security.table_action(table_ uuid,operation_ text,expected_ integer,key_ uuid,fingerprint_ text,
    task_ uuid,confirmed_ boolean,reason_ text,demo_ boolean,demo_enabled_ boolean) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE t public.dining_tables;
BEGIN
    SELECT * INTO t FROM public.dining_tables WHERE id=table_;
    IF NOT security.allowed_location(t.organization_id,t.location_id) THEN
        RAISE EXCEPTION 'Resource not found' USING ERRCODE='P0404'; END IF;
    IF (operation_='mark_ready' OR demo_) AND (EXISTS(SELECT 1 FROM public.workflow_sessions
        WHERE table_id=table_ AND status IN ('OPEN','VACATED')) OR EXISTS(SELECT 1 FROM public.workflow_policies p
        JOIN public.edge_bindings b ON p.bindings ? b.id::text WHERE b.table_id=table_)) THEN
        RAISE EXCEPTION 'Use reviewed workflow with fresh evidence' USING ERRCODE='P0409'; END IF;
    RETURN security.workflow_legacy_action(table_,operation_,expected_,key_,fingerprint_,task_,confirmed_,reason_,demo_,demo_enabled_);
END $$;

CREATE FUNCTION security.workflow_device_config() RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE d public.edge_devices; p public.workflow_policies; sessions_ jsonb;
BEGIN
    SELECT * INTO STRICT d FROM public.edge_devices WHERE id=security.edge_actor() AND status='ACTIVE';
    SELECT * INTO p FROM public.workflow_policies WHERE location_id=d.location_id;
    SELECT coalesce(jsonb_agg(jsonb_build_object('table_id',s.table_id,'session_id',s.id,'binding_id',s.binding_id,
        'source_generation',s.source_generation,'source_episode',s.source_episode)),'[]'::jsonb) INTO sessions_
        FROM public.workflow_sessions s WHERE s.device_id=d.id AND s.status='OPEN';
    RETURN jsonb_build_object('protocol_versions',jsonb_build_array(1,2),'workflow',
        CASE WHEN p.location_id IS NULL THEN jsonb_build_object('mode','OFF') ELSE
        jsonb_build_object('mode',p.mode,'revision',p.revision,'rules',p.rules,'rules_sha256',p.rules_sha256,
            'bindings',p.bindings,'enabled_since',p.enabled_since,'sessions',sessions_) END);
END $$;

CREATE FUNCTION security.workflow_policy_set(loc_ uuid,value_ jsonb,demo_ boolean) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE org_ uuid; p public.workflow_policies; prior_ public.workflow_decisions;
    fingerprint_ text; result_ jsonb; binding_ uuid; did_ uuid; revision_ integer; key_ uuid;
BEGIN
    SELECT organization_id INTO org_ FROM public.locations WHERE id=loc_;
    IF NOT security.allowed_location(org_,loc_) THEN RAISE EXCEPTION 'Resource not found' USING ERRCODE='P0404'; END IF;
    IF NOT security.has_role(org_,ARRAY['owner','org_admin','manager']) THEN RAISE EXCEPTION 'Manager required' USING ERRCODE='P0403'; END IF;
    key_:=(value_->>'request_key')::uuid;
    fingerprint_:=encode(sha256(convert_to(value_::text,'UTF8')),'hex');
    -- Same global order as ingestion: device, all tables in UUID order, location.
    PERFORM id FROM public.edge_devices WHERE location_id=loc_ ORDER BY id FOR UPDATE;
    PERFORM id FROM public.dining_tables WHERE location_id=loc_ ORDER BY id FOR UPDATE;
    PERFORM location_id FROM public.location_operations WHERE location_id=loc_ FOR UPDATE;
    IF NOT security.allowed_location(org_,loc_) OR NOT security.has_role(org_,ARRAY['owner','org_admin','manager']) THEN
        RAISE EXCEPTION 'Permission changed' USING ERRCODE='P0403'; END IF;
    SELECT * INTO prior_ FROM public.workflow_decisions WHERE actor_id=security.actor() AND location_id=loc_ AND request_key=key_;
    IF FOUND THEN
        IF prior_.fingerprint<>fingerprint_ THEN RAISE EXCEPTION 'Key conflict' USING ERRCODE='P0409'; END IF;
        RETURN prior_.result;
    END IF;
    SELECT * INTO p FROM public.workflow_policies WHERE location_id=loc_;
    IF key_ IS NULL OR coalesce(p.revision,0)<>(value_->>'expected_revision')::integer
        OR value_->>'mode' NOT IN ('OFF','ASSISTED_REVIEW') OR jsonb_typeof(value_->'bindings')<>'array'
        OR jsonb_array_length(value_->'bindings')>64 THEN RAISE EXCEPTION 'Policy conflict' USING ERRCODE='P0409'; END IF;
    IF value_->>'mode'='ASSISTED_REVIEW' AND (NOT demo_ OR NOT EXISTS(SELECT 1 FROM public.location_operations
        WHERE location_id=loc_ AND is_synthetic) OR jsonb_array_length(value_->'bindings')=0) THEN
        RAISE EXCEPTION 'Synthetic local activation only' USING ERRCODE='P0403'; END IF;
    FOR binding_ IN SELECT value::text::uuid FROM jsonb_array_elements_text(value_->'bindings') LOOP
        IF NOT EXISTS(SELECT 1 FROM public.edge_bindings b JOIN public.edge_devices d ON d.id=b.device_id
            WHERE b.id=binding_ AND b.location_id=loc_ AND b.organization_id=org_ AND b.enabled
            AND d.status='ACTIVE' AND d.purpose='AI_SHADOW') THEN RAISE EXCEPTION 'Binding unavailable' USING ERRCODE='P0404'; END IF;
    END LOOP;
    IF jsonb_array_length(value_->'bindings')<>(SELECT count(DISTINCT value) FROM jsonb_array_elements_text(value_->'bindings'))
        OR jsonb_typeof(value_->'rules')<>'object' THEN RAISE EXCEPTION 'Invalid policy' USING ERRCODE='P0422'; END IF;
    revision_:=coalesce(p.revision,0)+1;
    INSERT INTO public.workflow_policies(location_id,organization_id,mode,revision,enabled_since,rules,rules_sha256,bindings)
    VALUES(loc_,org_,value_->>'mode',revision_,clock_timestamp(),value_->'rules',security.workflow_rules_digest(value_->'rules'),value_->'bindings')
    ON CONFLICT(location_id) DO UPDATE SET mode=EXCLUDED.mode,revision=EXCLUDED.revision,enabled_since=EXCLUDED.enabled_since,
        rules=EXCLUDED.rules,rules_sha256=EXCLUDED.rules_sha256,bindings=EXCLUDED.bindings;
    UPDATE public.workflow_suggestions SET status='SUPERSEDED',revision=revision+1 WHERE location_id=loc_ AND status='PENDING';
    INSERT INTO public.workflow_policy_history(id,organization_id,location_id,actor_id,revision,snapshot)
        VALUES(gen_random_uuid(),org_,loc_,security.actor(),revision_,value_);
    INSERT INTO public.audit_logs(id,organization_id,location_id,actor_id,action,details)
        VALUES(gen_random_uuid(),org_,loc_,security.actor(),'workflow.policy',jsonb_build_object('revision',revision_,'mode',value_->>'mode'));
    FOR did_ IN SELECT id FROM public.edge_devices WHERE location_id=loc_ LOOP PERFORM security.edge_publish(did_,'workflow'); END LOOP;
    result_:=jsonb_build_object('location_id',loc_,'revision',revision_,'mode',value_->>'mode');
    INSERT INTO public.workflow_decisions(id,organization_id,location_id,actor_id,action,request_key,fingerprint,reason,result)
        VALUES(gen_random_uuid(),org_,loc_,security.actor(),'policy',key_,fingerprint_,'policy_changed',result_);
    RETURN result_;
END $$;

CREATE FUNCTION security.workflow_decide(table_ uuid,suggestion_ uuid,value_ jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE t public.dining_tables; p public.workflow_policies; d public.edge_devices; b public.edge_bindings;
    s public.workflow_suggestions; ev public.workflow_evidence; episode_ public.workflow_sessions;
    task_ public.staff_tasks; prior_ public.workflow_decisions; old_ text; result_ jsonb; fingerprint_ text;
    action_ text:=value_->>'action'; reason_ text:=coalesce(value_->>'reason',''); key_ uuid:=(value_->>'request_key')::uuid;
    moment_ timestamptz; event_ jsonb; session_ uuid; did_ uuid; extra_ jsonb:='{}'::jsonb; alias_ uuid;
BEGIN
    SELECT * INTO t FROM public.dining_tables WHERE id=table_;
    IF NOT security.allowed_location(t.organization_id,t.location_id) THEN RAISE EXCEPTION 'Resource not found' USING ERRCODE='P0404'; END IF;
    IF NOT security.has_role(t.organization_id,ARRAY['owner','org_admin','manager','staff']) THEN
        RAISE EXCEPTION 'Staff required' USING ERRCODE='P0403'; END IF;
    IF action_ IN ('correct_departure','correct_arrival','reconcile_source') AND NOT security.has_role(t.organization_id,ARRAY['owner','org_admin','manager']) THEN
        RAISE EXCEPTION 'Manager required' USING ERRCODE='P0403'; END IF;
    IF action_ NOT IN ('confirm','dismiss','ready','correct_departure','correct_arrival','reconcile_source') OR key_ IS NULL
        OR reason_ NOT IN ('','staff_crossing','wrong_table','guests_still_present','insufficient_view','other','source_restarted') THEN
        RAISE EXCEPTION 'Invalid action' USING ERRCODE='P0422'; END IF;
    -- Lock every device potentially providing this table's evidence before table/location.
    FOR did_ IN SELECT DISTINCT device_id FROM public.edge_bindings WHERE table_id=table_ ORDER BY device_id LOOP
        PERFORM id FROM public.edge_devices WHERE id=did_ FOR UPDATE;
    END LOOP;
    SELECT * INTO t FROM public.dining_tables WHERE id=table_ FOR UPDATE;
    PERFORM location_id FROM public.location_operations WHERE location_id=t.location_id FOR UPDATE;
    IF NOT security.allowed_location(t.organization_id,t.location_id) OR NOT security.has_role(t.organization_id,
        CASE WHEN action_ IN ('correct_departure','correct_arrival','reconcile_source') THEN ARRAY['owner','org_admin','manager']
             ELSE ARRAY['owner','org_admin','manager','staff'] END) THEN RAISE EXCEPTION 'Permission changed' USING ERRCODE='P0403'; END IF;
    fingerprint_:=encode(sha256(convert_to(jsonb_build_object('table_id',table_,'suggestion_id',suggestion_,'body',value_)::text,'UTF8')),'hex');
    SELECT * INTO prior_ FROM public.workflow_decisions WHERE actor_id=security.actor() AND location_id=t.location_id AND request_key=key_;
    IF FOUND THEN
        IF prior_.fingerprint<>fingerprint_ THEN RAISE EXCEPTION 'Key conflict' USING ERRCODE='P0409'; END IF;
        RETURN prior_.result;
    END IF;
    IF t.operational_revision<>(value_->>'expected_revision')::integer OR value_->>'expected_revision' IS NULL THEN
        RAISE EXCEPTION 'Table changed' USING ERRCODE='P0409'; END IF;
    IF action_<>'dismiss' AND NOT coalesce((value_->>'confirmed')::boolean,false) THEN
        RAISE EXCEPTION 'Physical check required' USING ERRCODE='P0409'; END IF;
    moment_:=clock_timestamp(); old_:=t.current_state; session_:=t.occupancy_session_id;
    SELECT * INTO p FROM public.workflow_policies WHERE location_id=t.location_id;
    SELECT * INTO task_ FROM public.staff_tasks WHERE table_id=t.id AND status IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS');
    IF action_ IN ('confirm','dismiss') THEN
        SELECT * INTO s FROM public.workflow_suggestions WHERE id=suggestion_ AND table_id=t.id;
        IF s.id IS NULL THEN RAISE EXCEPTION 'Resource not found' USING ERRCODE='P0404'; END IF;
        IF s.status<>'PENDING' OR s.revision<>(value_->>'expected_suggestion_revision')::integer
            OR value_->>'expected_suggestion_revision' IS NULL OR s.table_revision<>t.operational_revision
            OR s.expires_at<=moment_ THEN RAISE EXCEPTION 'Suggestion changed' USING ERRCODE='P0409'; END IF;
        IF action_='dismiss' THEN
            IF reason_='' THEN RAISE EXCEPTION 'Reason required' USING ERRCODE='P0422'; END IF;
            UPDATE public.workflow_suggestions SET status='DISMISSED',revision=revision+1 WHERE id=s.id;
        ELSE
            SELECT * INTO ev FROM public.workflow_evidence WHERE receipt_id=s.latest_receipt_id;
            IF NOT security.workflow_live(ev.receipt_id) OR p.revision<>s.policy_revision
                OR ev.source_generation<>s.source_generation
                OR (s.action='ARRIVAL' AND ev.kind<>'POSITIVE') OR (s.action='DEPARTURE' AND ev.kind<>'VACANT') THEN
                RAISE EXCEPTION 'Evidence is no longer safe' USING ERRCODE='P0409'; END IF;
            IF s.action='ARRIVAL' THEN
                IF t.current_state NOT IN ('UNKNOWN','AVAILABLE') OR task_.id IS NOT NULL THEN
                    RAISE EXCEPTION 'Protected state' USING ERRCODE='P0409'; END IF;
                session_:=gen_random_uuid();
                INSERT INTO public.workflow_sessions(id,organization_id,location_id,table_id,device_id,binding_id,
                    source_generation,source_episode,arrival_receipt_id,arrived_at)
                    VALUES(session_,t.organization_id,t.location_id,t.id,s.device_id,s.binding_id,
                        s.source_generation,s.source_episode,s.receipt_id,moment_);
                t.current_state:='OCCUPIED'; t.occupancy_session_id:=session_; t.occupied_since:=moment_;
                UPDATE public.workflow_suggestions SET session_id=session_ WHERE id=s.id;
            ELSE
                SELECT * INTO episode_ FROM public.workflow_sessions WHERE id=s.session_id AND id=t.occupancy_session_id
                    AND table_id=t.id AND status='OPEN' AND binding_id=s.binding_id
                    AND source_generation=s.source_generation AND source_episode=s.source_episode;
                IF t.current_state<>'OCCUPIED' OR episode_.id IS NULL THEN RAISE EXCEPTION 'Session changed' USING ERRCODE='P0409'; END IF;
                t.current_state:='RESET_PENDING';
                UPDATE public.workflow_sessions SET status='VACATED',departed_at=moment_ WHERE id=episode_.id;
                SELECT * INTO task_ FROM public.staff_tasks WHERE table_id=t.id AND occupancy_session_id=episode_.id;
                IF task_.id IS NULL THEN
                    INSERT INTO public.staff_tasks(id,organization_id,location_id,table_id,occupancy_session_id,status,created_at)
                        VALUES(gen_random_uuid(),t.organization_id,t.location_id,t.id,episode_.id,'OPEN',moment_);
                ELSIF task_.status='CANCELLED' AND task_.resolution='correction' THEN
                    UPDATE public.staff_tasks SET status='OPEN',acknowledged_at=NULL,started_at=NULL,completed_at=NULL,resolution=NULL WHERE id=task_.id;
                ELSE RAISE EXCEPTION 'Task already exists' USING ERRCODE='P0409'; END IF;
            END IF;
            UPDATE public.workflow_suggestions SET status='ACCEPTED',revision=revision+1 WHERE id=s.id;
        END IF;
    ELSIF action_='ready' THEN
        IF t.current_state NOT IN ('UNKNOWN','CLEANING') OR (t.current_state='CLEANING' AND task_.status<>'IN_PROGRESS') THEN
            RAISE EXCEPTION 'Not ready for confirmation' USING ERRCODE='P0409'; END IF;
        SELECT e.* INTO ev FROM public.workflow_evidence e JOIN public.edge_receipts r ON r.event_id=e.receipt_id
            WHERE e.table_id=t.id ORDER BY e.observed_at DESC,r.sequence DESC LIMIT 1;
        IF ev.receipt_id IS NULL OR ev.kind<>'VACANT' OR NOT security.workflow_live(ev.receipt_id) THEN
            RAISE EXCEPTION 'Current vacant evidence required' USING ERRCODE='P0409'; END IF;
        IF task_.id IS NOT NULL THEN
            UPDATE public.staff_tasks SET status='COMPLETED',completed_at=moment_,resolution='staff_confirmed_ready' WHERE id=task_.id;
        END IF;
        t.current_state:='AVAILABLE'; t.occupancy_session_id:=NULL; t.occupied_since:=NULL;
    ELSE
        IF reason_='' OR t.occupancy_session_id IS NULL OR t.occupancy_session_id IS DISTINCT FROM (value_->>'session_id')::uuid THEN
            RAISE EXCEPTION 'Current session and reason required' USING ERRCODE='P0409'; END IF;
        SELECT * INTO episode_ FROM public.workflow_sessions WHERE id=t.occupancy_session_id AND table_id=t.id;
        IF episode_.id IS NULL THEN RAISE EXCEPTION 'Reviewed session required' USING ERRCODE='P0409'; END IF;
        IF action_='reconcile_source' THEN
            IF t.current_state<>'OCCUPIED' OR episode_.status<>'OPEN' OR task_.id IS NOT NULL OR reason_<>'source_restarted' THEN
                RAISE EXCEPTION 'Current open session required' USING ERRCODE='P0409'; END IF;
            SELECT e.* INTO ev FROM public.workflow_evidence e JOIN public.edge_receipts r ON r.event_id=e.receipt_id
                WHERE e.table_id=t.id ORDER BY e.observed_at DESC,r.sequence DESC LIMIT 1;
            IF ev.receipt_id IS NULL OR NOT security.workflow_live(ev.receipt_id)
                OR (ev.source_generation=episode_.source_generation AND ev.binding_id=episode_.binding_id) THEN
                RAISE EXCEPTION 'Fresh changed source context required' USING ERRCODE='P0409'; END IF;
            alias_:=gen_random_uuid();
            extra_:=jsonb_build_object('previous_source_generation',episode_.source_generation,
                'previous_source_episode',episode_.source_episode,'new_source_generation',ev.source_generation,
                'new_source_episode',alias_,'evidence_receipt_id',ev.receipt_id);
            UPDATE public.workflow_sessions SET source_generation=ev.source_generation,source_episode=alias_,
                binding_id=ev.binding_id,device_id=ev.device_id WHERE id=episode_.id;
        ELSIF action_='correct_departure' THEN
            IF t.current_state<>'RESET_PENDING' OR task_.id IS NULL OR task_.status='IN_PROGRESS' THEN
                RAISE EXCEPTION 'Protected state' USING ERRCODE='P0409'; END IF;
            UPDATE public.staff_tasks SET status='CANCELLED',completed_at=moment_,resolution='correction' WHERE id=task_.id;
            UPDATE public.workflow_sessions SET status='OPEN',departed_at=NULL WHERE id=episode_.id;
            -- Keep original departure evidence/attempt in immutable history; allow a NEW genuine transition.
            UPDATE public.workflow_suggestions SET status='SUPERSEDED',revision=revision+1
                WHERE session_id=episode_.id AND action='DEPARTURE' AND status='ACCEPTED';
            t.current_state:='OCCUPIED';
        ELSE
            IF t.current_state<>'OCCUPIED' OR task_.id IS NOT NULL THEN RAISE EXCEPTION 'Protected state' USING ERRCODE='P0409'; END IF;
            UPDATE public.workflow_sessions SET status='INVALIDATED' WHERE id=episode_.id;
            t.current_state:='UNKNOWN'; t.occupancy_session_id:=NULL; t.occupied_since:=NULL;
        END IF;
    END IF;
    IF action_<>'dismiss' THEN
        IF old_<>t.current_state THEN t.state_since:=moment_; END IF;
        t.operational_revision:=t.operational_revision+1;
        UPDATE public.dining_tables SET current_state=t.current_state,state_since=t.state_since,state_source='manual',
            operational_revision=t.operational_revision,occupancy_session_id=t.occupancy_session_id,occupied_since=t.occupied_since
            WHERE id=t.id;
    END IF;
    UPDATE public.workflow_suggestions SET status='SUPERSEDED',revision=revision+1 WHERE table_id=t.id AND status='PENDING';
    event_:=security.workflow_event(t.id,old_,action_,extra_||jsonb_build_object('suggestion_id',suggestion_,
        'reason',reason_,'session_id',session_,
        'corrected_session_id',CASE WHEN action_ LIKE 'correct_%' THEN episode_.id ELSE NULL END));
    result_:=event_||jsonb_build_object('action',action_);
    INSERT INTO public.workflow_decisions(id,organization_id,location_id,table_id,suggestion_id,actor_id,action,
        request_key,fingerprint,reason,result) VALUES(gen_random_uuid(),t.organization_id,t.location_id,t.id,suggestion_,
        security.actor(),action_,key_,fingerprint_,reason_,result_);
    RETURN result_;
END $$;

-- Existing restricted roles must not retain ACL access to the renamed legacy helper.
DO $$ DECLARE role_ record; fn_ text; BEGIN
    FOR role_ IN SELECT rolname FROM pg_roles WHERE rolname<>current_user AND NOT rolsuper LOOP
        FOREACH fn_ IN ARRAY ARRAY[
            'security.workflow_legacy_action(uuid,text,integer,uuid,text,uuid,boolean,text,boolean,boolean)',
            'security.workflow_event(uuid,text,text,jsonb)', 'security.workflow_receive()',
            'security.workflow_task_projection()', 'security.workflow_journal_capture()',
            'security.workflow_quality(jsonb,jsonb)', 'security.workflow_rules_digest(jsonb)', 'security.workflow_quality_boundary()'] LOOP
            EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %I',fn_,role_.rolname);
        END LOOP;
    END LOOP;
END $$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA security FROM PUBLIC;
