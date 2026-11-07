-- Passive viewing never refreshes idle expiry. Active, CSRF-protected writes use resolve_session.
CREATE FUNCTION security.peek_session(digest_ text, idle_ integer) RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
    SELECT s.user_id FROM identity.sessions s JOIN identity.users u ON u.id=s.user_id
    WHERE s.token_digest=digest_ AND u.enabled AND NOT s.revoked AND s.expires_at>now()
      AND s.last_seen_at>now()-make_interval(secs=>least(greatest(idle_,1),1800))
$$;

DO $$ DECLARE table_ text; BEGIN
    FOREACH table_ IN ARRAY ARRAY['location_operations','table_events','staff_tasks','action_receipts'] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',table_);
        EXECUTE format('CREATE POLICY operation_read ON public.%I FOR SELECT
            USING(security.allowed_location(organization_id,location_id))',table_);
        EXECUTE format('CREATE TRIGGER immutable_ownership BEFORE UPDATE ON public.%I
            FOR EACH ROW EXECUTE FUNCTION security.immutable_ownership(''organization_id'',''location_id'')',table_);
    END LOOP;
END $$;
DROP POLICY operation_read ON public.action_receipts;
CREATE POLICY operation_read ON public.action_receipts FOR SELECT
    USING(actor_id=security.actor() AND security.allowed_location(organization_id,location_id));

INSERT INTO public.location_operations(location_id,organization_id)
    SELECT id,organization_id FROM public.locations;
CREATE FUNCTION security.initialize_location_operations() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    INSERT INTO public.location_operations(location_id,organization_id) VALUES(NEW.id,NEW.organization_id);
    RETURN NEW;
END $$;
CREATE TRIGGER initialize_location_operations AFTER INSERT ON public.locations
    FOR EACH ROW EXECUTE FUNCTION security.initialize_location_operations();

-- Metadata changes also publish ordered invalidations; lock order is table then location.
CREATE FUNCTION security.publish_table_configuration() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE seq integer; version_ integer;
BEGIN
    UPDATE public.location_operations SET revision=revision+1 WHERE location_id=NEW.location_id
        RETURNING revision INTO seq;
    UPDATE public.dining_tables SET operational_revision=operational_revision+1 WHERE id=NEW.id
        RETURNING operational_revision INTO version_;
    INSERT INTO public.table_events(id,organization_id,location_id,table_id,revision,event_type,
        source,actor_id,previous_state,new_state,payload)
    VALUES(gen_random_uuid(),NEW.organization_id,NEW.location_id,NEW.id,seq,'table.configuration',
        'configuration',security.actor(),NEW.current_state,NEW.current_state,
        jsonb_build_object('table_revision',version_));
    RETURN NEW;
END $$;
CREATE TRIGGER publish_table_configuration AFTER INSERT OR UPDATE OF label,seats ON public.dining_tables
    FOR EACH ROW EXECUTE FUNCTION security.publish_table_configuration();

-- The only operational write entry point granted to the restricted application role.
-- This definer deliberately checks membership, location, role, input and transition itself.
CREATE FUNCTION security.table_action(table_ uuid, operation_ text, expected_ integer,
    key_ uuid, fingerprint_ text, task_ uuid, confirmed_ boolean, reason_ text,
    demo_ boolean, demo_enabled_ boolean) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE
    t public.dining_tables%ROWTYPE; ops public.location_operations%ROWTYPE;
    prior public.action_receipts%ROWTYPE; active_ public.staff_tasks%ROWTYPE;
    old_state text; seq integer; event_ uuid := gen_random_uuid(); result_ jsonb;
    moment_ timestamptz := clock_timestamp(); actor_ uuid := security.actor();
BEGIN
    SELECT * INTO t FROM public.dining_tables WHERE id=table_;
    IF NOT FOUND OR NOT security.allowed_location(t.organization_id,t.location_id) THEN
        RAISE EXCEPTION 'Resource not found' USING ERRCODE='P0404';
    END IF;
    IF NOT security.has_role(t.organization_id,ARRAY['owner','org_admin','manager','staff']) THEN
        RAISE EXCEPTION 'Operation not permitted' USING ERRCODE='P0403';
    END IF;
    IF demo_ THEN
        IF NOT coalesce(demo_enabled_,false) OR NOT EXISTS(SELECT 1 FROM public.location_operations
            WHERE location_id=t.location_id AND is_synthetic) THEN
            RAISE EXCEPTION 'Demo unavailable' USING ERRCODE='P0404';
        END IF;
        IF NOT security.has_role(t.organization_id,ARRAY['owner','org_admin','manager']) THEN
            RAISE EXCEPTION 'Operation not permitted' USING ERRCODE='P0403';
        END IF;
        IF operation_ NOT IN ('arrive','depart','vacant','source_offline','source_resume') THEN
            RAISE EXCEPTION 'Invalid demo operation' USING ERRCODE='P0422';
        END IF;
    ELSE
        IF operation_ NOT IN ('acknowledge','start_cleaning','mark_ready','out_of_service','reopen') THEN
            RAISE EXCEPTION 'Invalid staff operation' USING ERRCODE='P0422';
        END IF;
        IF operation_ IN ('out_of_service','reopen') AND
            NOT security.has_role(t.organization_id,ARRAY['owner','org_admin','manager']) THEN
            RAISE EXCEPTION 'Manager permission required' USING ERRCODE='P0403';
        END IF;
    END IF;
    IF operation_ IS NULL OR key_ IS NULL OR expected_ IS NULL OR expected_<0 OR fingerprint_ IS NULL
        OR length(fingerprint_)<>64 OR length(coalesce(reason_,''))>200 THEN
        RAISE EXCEPTION 'Invalid action fields' USING ERRCODE='P0422';
    END IF;
    IF coalesce(reason_,'') NOT IN ('','maintenance','reserved','safety','other') THEN
        RAISE EXCEPTION 'Use a safe operational reason code' USING ERRCODE='P0422';
    END IF;
    -- Compute the receipt fingerprint ourselves; a caller cannot hide a changed payload.
    fingerprint_ := encode(sha256(convert_to(jsonb_build_object('table',table_,
        'operation',operation_,'expected',expected_,'task',task_,'confirmed',confirmed_,
        'reason',coalesce(reason_,''),'demo',demo_)::text,'UTF8')),'hex');
    SELECT * INTO t FROM public.dining_tables WHERE id=table_ FOR UPDATE;
    SELECT * INTO ops FROM public.location_operations WHERE location_id=t.location_id FOR UPDATE;
    -- Revalidate current permissions after any lock wait, including before a cached reply.
    IF NOT security.allowed_location(t.organization_id,t.location_id) THEN
        RAISE EXCEPTION 'Resource not found' USING ERRCODE='P0404';
    END IF;
    IF NOT security.has_role(t.organization_id,
        CASE WHEN demo_ OR operation_ IN ('out_of_service','reopen')
             THEN ARRAY['owner','org_admin','manager']
             ELSE ARRAY['owner','org_admin','manager','staff'] END) THEN
        RAISE EXCEPTION 'Operation not permitted' USING ERRCODE='P0403';
    END IF;
    IF demo_ AND NOT ops.is_synthetic THEN
        RAISE EXCEPTION 'Demo unavailable' USING ERRCODE='P0404';
    END IF;
    SELECT * INTO prior FROM public.action_receipts WHERE actor_id=actor_
        AND location_id=t.location_id AND request_key=key_;
    IF FOUND THEN
        IF prior.fingerprint<>fingerprint_ OR prior.table_id<>table_ THEN
            RAISE EXCEPTION 'Request key already used' USING ERRCODE='P0409';
        END IF;
        RETURN prior.result;
    END IF;
    IF t.operational_revision<>expected_ THEN
        RAISE EXCEPTION 'Table changed; refresh before retrying' USING ERRCODE='P0409';
    END IF;
    SELECT * INTO active_ FROM public.staff_tasks WHERE table_id=table_
        AND status IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS');
    IF task_ IS NOT NULL AND (active_.id IS NULL OR active_.id<>task_) THEN
        RAISE EXCEPTION 'Task not found' USING ERRCODE='P0404';
    END IF;
    old_state := t.current_state;
    IF demo_ THEN
        t.observed_at := moment_;
        IF operation_='source_offline' THEN
            t.source_status := 'OFFLINE'; t.observation := 'UNKNOWN';
            IF t.state_source<>'manual' THEN t.current_state := 'UNKNOWN'; END IF;
        ELSIF operation_='source_resume' THEN
            t.source_status := 'ONLINE'; t.observation := 'UNKNOWN';
        ELSE
            t.source_status := 'ONLINE';
            t.observation := CASE WHEN operation_='arrive' THEN 'OCCUPIED' ELSE 'VACANT' END;
            IF t.current_state NOT IN ('CLEANING','OUT_OF_SERVICE') THEN
                IF operation_='arrive' THEN
                    IF t.current_state<>'OCCUPIED' THEN
                        IF active_.id IS NOT NULL THEN
                            UPDATE public.staff_tasks SET status='CANCELLED',completed_at=moment_,
                                resolution='occupancy_returned' WHERE id=active_.id;
                        END IF;
                        t.occupancy_session_id := gen_random_uuid(); t.occupied_since := moment_;
                    END IF;
                    t.current_state := 'OCCUPIED'; t.state_source := 'demo';
                ELSIF t.occupancy_session_id IS NOT NULL THEN
                    t.current_state := 'RESET_PENDING'; t.state_source := 'demo';
                    INSERT INTO public.staff_tasks(id,organization_id,location_id,table_id,
                        occupancy_session_id,created_at,status)
                    VALUES(gen_random_uuid(),t.organization_id,t.location_id,table_,
                        t.occupancy_session_id,moment_,'OPEN') ON CONFLICT DO NOTHING;
                ELSIF operation_='depart' THEN
                    RAISE EXCEPTION 'No occupancy session to depart' USING ERRCODE='P0409';
                END IF;
            END IF;
        END IF;
    ELSIF operation_='acknowledge' THEN
        IF active_.id IS NULL OR active_.status<>'OPEN' THEN
            RAISE EXCEPTION 'Task is not open' USING ERRCODE='P0409';
        END IF;
        UPDATE public.staff_tasks SET status='ACKNOWLEDGED',acknowledged_at=moment_ WHERE id=active_.id;
    ELSIF operation_='start_cleaning' THEN
        IF t.current_state<>'RESET_PENDING' OR active_.id IS NULL THEN
            RAISE EXCEPTION 'Table is not awaiting reset' USING ERRCODE='P0409';
        END IF;
        t.current_state := 'CLEANING'; t.state_source := 'manual';
        UPDATE public.staff_tasks SET status='IN_PROGRESS',started_at=moment_,
            acknowledged_at=coalesce(acknowledged_at,moment_) WHERE id=active_.id;
    ELSIF operation_='mark_ready' THEN
        IF NOT coalesce(confirmed_,false) OR t.current_state NOT IN ('CLEANING','UNKNOWN')
            OR t.source_status<>'ONLINE' OR t.observation<>'VACANT' THEN
            RAISE EXCEPTION 'Confirm readiness with current vacant source information' USING ERRCODE='P0409';
        END IF;
        t.current_state := 'AVAILABLE'; t.state_source := 'manual';
        t.occupancy_session_id := NULL; t.occupied_since := NULL;
        IF active_.id IS NOT NULL THEN
            UPDATE public.staff_tasks SET status='COMPLETED',completed_at=moment_,
                resolution='staff_confirmed_ready' WHERE id=active_.id;
        END IF;
    ELSIF operation_='out_of_service' THEN
        IF length(btrim(coalesce(reason_,'')))=0 OR t.current_state='OUT_OF_SERVICE' THEN
            RAISE EXCEPTION 'Provide a reason for an unblocked table' USING ERRCODE='P0409';
        END IF;
        t.current_state := 'OUT_OF_SERVICE'; t.state_source := 'manual';
        t.occupancy_session_id := NULL; t.occupied_since := NULL;
        IF active_.id IS NOT NULL THEN
            UPDATE public.staff_tasks SET status='CANCELLED',completed_at=moment_,
                resolution='manager_blocked' WHERE id=active_.id;
        END IF;
    ELSIF operation_='reopen' THEN
        IF t.current_state<>'OUT_OF_SERVICE' THEN
            RAISE EXCEPTION 'Table is not blocked' USING ERRCODE='P0409';
        END IF;
        t.current_state := 'UNKNOWN'; t.state_source := 'unverified';
    END IF;
    IF t.current_state<>old_state THEN t.state_since := moment_; END IF;
    t.operational_revision := t.operational_revision+1;
    UPDATE public.dining_tables SET current_state=t.current_state,state_since=t.state_since,
        state_source=t.state_source,operational_revision=t.operational_revision,
        occupancy_session_id=t.occupancy_session_id,occupied_since=t.occupied_since,
        source_status=t.source_status,observation=t.observation,observed_at=t.observed_at WHERE id=table_;
    UPDATE public.location_operations SET revision=revision+1 WHERE location_id=t.location_id
        RETURNING revision INTO seq;
    INSERT INTO public.table_events(id,organization_id,location_id,table_id,revision,event_type,source,
        actor_id,occurred_at,ingested_at,previous_state,new_state,payload)
    VALUES(event_,t.organization_id,t.location_id,table_,seq,'table.'||operation_,
        CASE WHEN demo_ THEN 'demo' ELSE 'manual' END,actor_,moment_,moment_,old_state,t.current_state,
        jsonb_build_object('table_revision',t.operational_revision,'source_status',t.source_status,
            'observation',t.observation,'state_source',t.state_source,'reason',coalesce(reason_,'')));
    INSERT INTO public.audit_logs(id,organization_id,location_id,actor_id,action,details)
    VALUES(gen_random_uuid(),t.organization_id,t.location_id,actor_,'table.'||operation_,
        jsonb_build_object('table_id',table_,'event_id',event_,'previous_state',old_state,
            'new_state',t.current_state,'source',CASE WHEN demo_ THEN 'demo' ELSE 'manual' END,
            'reason',coalesce(reason_,'')));
    result_ := jsonb_build_object('table_id',table_,'event_id',event_,'revision',t.operational_revision,
        'cursor',t.location_id::text||':'||seq::text,'state',t.current_state);
    INSERT INTO public.action_receipts(actor_id,organization_id,location_id,request_key,table_id,fingerprint,result)
    VALUES(actor_,t.organization_id,t.location_id,key_,table_,fingerprint_,result_);
    RETURN result_;
END $$;

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA security FROM PUBLIC;
