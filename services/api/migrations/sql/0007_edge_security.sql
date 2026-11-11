-- Phase 6 controlled device boundary. All data mutations use fixed-search-path
-- functions; the API login receives SELECT only on new public tables.
CREATE FUNCTION security.edge_actor() RETURNS uuid LANGUAGE sql STABLE
SET search_path=pg_catalog AS $$
    SELECT nullif(current_setting('app.edge_device_id',true),'')::uuid
$$;
CREATE FUNCTION security.edge_key_actor() RETURNS uuid LANGUAGE sql STABLE
SET search_path=pg_catalog AS $$
    SELECT nullif(current_setting('app.edge_key_id',true),'')::uuid
$$;
CREATE FUNCTION security.edge_visible(org_ uuid,loc_ uuid,device_ uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
    SELECT security.actor() IS NULL AND security.edge_actor()=device_ AND EXISTS(
        SELECT 1 FROM public.edge_devices d WHERE d.id=device_ AND d.organization_id=org_
        AND d.location_id=loc_ AND d.status='ACTIVE')
$$;

DO $$ DECLARE name_ text; BEGIN
    FOREACH name_ IN ARRAY ARRAY['edge_devices','edge_keys','edge_assignments','edge_bindings',
        'edge_receipts','edge_shadows','edge_health','edge_audits'] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',name_);
        EXECUTE format('CREATE POLICY human_edge_read ON public.%I FOR SELECT
            USING(security.allowed_location(organization_id,location_id))',name_);
        EXECUTE format('CREATE TRIGGER immutable_ownership BEFORE UPDATE ON public.%I
            FOR EACH ROW EXECUTE FUNCTION security.immutable_ownership(''organization_id'',''location_id'')',name_);
    END LOOP;
END $$;
ALTER TABLE public.location_notifications ENABLE ROW LEVEL SECURITY;
CREATE POLICY scoped_notification ON public.location_notifications FOR SELECT
    USING(security.allowed_location(organization_id,location_id));
CREATE POLICY machine_device ON public.edge_devices FOR SELECT
    USING(security.edge_visible(organization_id,location_id,id));
CREATE POLICY machine_binding ON public.edge_bindings FOR SELECT
    USING(security.edge_visible(organization_id,location_id,device_id));
CREATE POLICY machine_assignment ON public.edge_assignments FOR SELECT
    USING(security.edge_visible(organization_id,location_id,device_id));
CREATE POLICY machine_receipt ON public.edge_receipts FOR SELECT
    USING(security.edge_visible(organization_id,location_id,device_id));

CREATE FUNCTION security.edge_publish(device_ uuid,kind_ text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE d public.edge_devices; seq_ integer;
BEGIN
    SELECT * INTO STRICT d FROM public.edge_devices WHERE id=device_;
    UPDATE public.location_operations SET revision=revision+1 WHERE location_id=d.location_id
        RETURNING revision INTO seq_;
    INSERT INTO public.location_notifications(organization_id,location_id,revision,device_id,kind)
        VALUES(d.organization_id,d.location_id,seq_,d.id,kind_);
END $$;

CREATE FUNCTION security.edge_pair_start(id_ uuid,key_ uuid,pub_ text,fp_ text,peer_ text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE nonce_ text := replace(gen_random_uuid()::text,'-',''); expiry_ timestamptz := clock_timestamp()+interval '10 minutes';
BEGIN
    -- One lock bounds aggregate work across API processes. Never trust X-Forwarded-For.
    PERFORM pg_advisory_xact_lock(600061);
    IF length(pub_)<>44 OR fp_ !~ '^[0-9a-f]{64}$' OR peer_ !~ '^[0-9a-f]{64}$'
       OR (SELECT count(*) FROM edge_private.pairings WHERE expires_at>clock_timestamp())>=100
       OR (SELECT count(*) FROM edge_private.pairings WHERE peer_hash=peer_
            AND created_at>clock_timestamp()-interval '10 minutes')>=5 THEN
        RAISE EXCEPTION 'Pairing unavailable' USING ERRCODE='54000';
    END IF;
    INSERT INTO edge_private.pairings(id,key_id,public_key,fingerprint,challenge,peer_hash,expires_at)
        VALUES(id_,key_,pub_,fp_,nonce_,peer_,expiry_);
    RETURN jsonb_build_object('request_id',id_,'challenge',nonce_,'expires_at',expiry_,'fingerprint',fp_);
END $$;

CREATE FUNCTION security.edge_public_key(key_ uuid,pairing_ boolean) RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
    SELECT k.public_key::text FROM public.edge_keys k JOIN public.edge_devices d ON d.id=k.device_id
        WHERE k.id=key_ AND NOT pairing_ AND NOT k.revoked AND k.expires_at>clock_timestamp() AND d.status='ACTIVE'
    UNION ALL SELECT p.public_key::text FROM edge_private.pairings p WHERE p.key_id=key_
        AND pairing_ AND p.expires_at>clock_timestamp()
$$;

CREATE FUNCTION security.edge_pair_accept(key_ uuid,nonce_ text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    IF nonce_ !~ '^[0-9a-f]{32}$' OR NOT EXISTS(SELECT 1 FROM edge_private.pairings
        WHERE key_id=key_ AND expires_at>clock_timestamp()) THEN
        RAISE EXCEPTION 'Pairing authentication failed' USING ERRCODE='42501';
    END IF;
    IF (SELECT count(*) FROM edge_private.nonces WHERE key_id=key_
        AND expires_at>clock_timestamp()+interval '9 minutes')>=120 THEN
        RAISE EXCEPTION 'Device rate limited' USING ERRCODE='54000';
    END IF;
    INSERT INTO edge_private.nonces(key_id,nonce,expires_at)
        VALUES(key_,nonce_,clock_timestamp()+interval '10 minutes');
    PERFORM set_config('app.user_id','',true);
    PERFORM set_config('app.edge_device_id','',true);
    PERFORM set_config('app.edge_key_id',key_::text,true);
END $$;

CREATE FUNCTION security.edge_pair_prove(id_ uuid,challenge_ text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE p edge_private.pairings;
BEGIN
    SELECT * INTO p FROM edge_private.pairings WHERE id=id_ AND key_id=security.edge_key_actor()
        AND expires_at>clock_timestamp() FOR UPDATE;
    IF NOT FOUND OR p.challenge<>challenge_ THEN
        RAISE EXCEPTION 'Invalid proof' USING ERRCODE='42501';
    END IF;
    UPDATE edge_private.pairings SET proved=true WHERE id=p.id;
    RETURN jsonb_build_object('request_id',p.id,'fingerprint',p.fingerprint,'proved',true,'device_id',p.device_id);
END $$;

CREATE FUNCTION security.edge_accept(key_ uuid,nonce_ text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE d public.edge_devices; k public.edge_keys;
BEGIN
    SELECT * INTO k FROM public.edge_keys WHERE id=key_;
    SELECT * INTO d FROM public.edge_devices WHERE id=k.device_id FOR UPDATE;
    -- Re-read key after the device lock: rotation and revocation use this same order.
    SELECT * INTO k FROM public.edge_keys WHERE id=key_;
    IF d.id IS NULL OR d.status<>'ACTIVE' OR k.revoked OR k.expires_at<=clock_timestamp()
        OR nonce_ !~ '^[0-9a-f]{32}$' THEN
        RAISE EXCEPTION 'Device authentication failed' USING ERRCODE='42501';
    END IF;
    IF (SELECT count(*) FROM edge_private.nonces WHERE key_id=key_
        AND expires_at>clock_timestamp()+interval '9 minutes')>=120 THEN
        RAISE EXCEPTION 'Device rate limited' USING ERRCODE='54000';
    END IF;
    INSERT INTO edge_private.nonces(key_id,nonce,expires_at)
        VALUES(key_,nonce_,clock_timestamp()+interval '10 minutes');
    PERFORM set_config('app.user_id','',true);
    PERFORM set_config('app.edge_device_id',d.id::text,true);
    PERFORM set_config('app.edge_key_id',key_::text,true);
    RETURN d.id;
END $$;

CREATE FUNCTION security.edge_manage(loc_ uuid,action_ text,value_ jsonb,demo_ boolean) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE org_ uuid; p edge_private.pairings; d public.edge_devices; a public.edge_assignments;
        id_ uuid; camera_ uuid; table_ uuid; zone_ integer; revision_ integer;
BEGIN
    SELECT organization_id INTO org_ FROM public.locations WHERE id=loc_;
    IF org_ IS NULL OR NOT security.allowed_location(org_,loc_)
        OR NOT security.has_role(org_,ARRAY['owner','org_admin','manager']) THEN
        RAISE EXCEPTION 'Not authorized' USING ERRCODE='42501';
    END IF;
    IF action_ IN ('approve','rotate') THEN
        SELECT * INTO p FROM edge_private.pairings WHERE id=(value_->>'request_id')::uuid FOR UPDATE;
        IF p.id IS NULL OR NOT p.proved OR p.expires_at<=clock_timestamp() OR p.device_id IS NOT NULL
            OR p.fingerprint<>value_->>'fingerprint' THEN
            RAISE EXCEPTION 'Pairing not eligible' USING ERRCODE='23514';
        END IF;
    END IF;
    IF action_='approve' THEN
        IF value_->>'purpose' NOT IN ('AI_SHADOW','SYNTHETIC_WORKFLOW_TEST')
            OR length(value_->>'label') NOT BETWEEN 1 AND 80 THEN
            RAISE EXCEPTION 'Invalid device' USING ERRCODE='23514';
        END IF;
        IF value_->>'purpose'='SYNTHETIC_WORKFLOW_TEST' AND (NOT demo_ OR NOT EXISTS(
            SELECT 1 FROM public.location_operations WHERE location_id=loc_ AND is_synthetic)) THEN
            RAISE EXCEPTION 'Synthetic location required' USING ERRCODE='42501';
        END IF;
        id_:=gen_random_uuid();
        INSERT INTO public.edge_devices(id,organization_id,location_id,label,purpose)
            VALUES(id_,org_,loc_,value_->>'label',value_->>'purpose') RETURNING * INTO d;
    ELSE
        SELECT * INTO d FROM public.edge_devices WHERE id=(value_->>'device_id')::uuid
            AND organization_id=org_ AND location_id=loc_ FOR UPDATE;
        IF d.id IS NULL OR d.status<>'ACTIVE' OR d.revision<>(value_->>'expected_revision')::integer THEN
            RAISE EXCEPTION 'Device changed or unavailable' USING ERRCODE='23514';
        END IF;
        IF NOT security.allowed_location(org_,loc_)
            OR NOT security.has_role(org_,ARRAY['owner','org_admin','manager']) THEN
            RAISE EXCEPTION 'Not authorized after lock' USING ERRCODE='42501';
        END IF;
        IF action_='revoke' THEN
            UPDATE public.edge_devices SET status='REVOKED',processing_enabled=false,revision=revision+1 WHERE id=d.id;
            UPDATE public.edge_keys SET revoked=true WHERE device_id=d.id;
        ELSIF action_='processing' THEN
            -- Phase 6 authorizes only explicitly synthetic local processing.
            IF (value_->>'enabled')::boolean AND NOT EXISTS(
                SELECT 1 FROM public.location_operations WHERE location_id=loc_ AND is_synthetic) THEN
                RAISE EXCEPTION 'Synthetic processing only' USING ERRCODE='42501';
            END IF;
            UPDATE public.edge_devices SET processing_enabled=(value_->>'enabled')::boolean,
                revision=revision+1 WHERE id=d.id;
        ELSIF action_='assign' THEN
            camera_:=(value_->>'camera_id')::uuid; table_:=(value_->>'table_id')::uuid;
            IF (SELECT count(*) FROM public.edge_bindings WHERE device_id=d.id AND enabled)>=64
                AND NOT EXISTS(SELECT 1 FROM public.edge_bindings WHERE device_id=d.id AND table_id=table_ AND enabled) THEN
                RAISE EXCEPTION 'Device table limit reached' USING ERRCODE='54000';
            END IF;
            SELECT revision INTO zone_ FROM public.table_zones WHERE table_id=table_ AND camera_id=camera_
                AND organization_id=org_ AND location_id=loc_;
            IF zone_ IS NULL OR zone_<>(value_->>'zone_revision')::integer
                OR (value_->>'profile_sha256') !~ '^[0-9a-f]{64}$'
                OR (value_->>'model_sha256') !~ '^[0-9a-f]{64}$'
                OR (value_->>'profile_revision')::integer<1 THEN
                RAISE EXCEPTION 'Configuration mismatch' USING ERRCODE='23514';
            END IF;
            SELECT * INTO a FROM public.edge_assignments WHERE camera_id=camera_ AND enabled FOR UPDATE;
            IF a.id IS NOT NULL AND a.device_id<>d.id THEN
                -- A revoked camera owner can be replaced by explicit manager approval.
                IF EXISTS(SELECT 1 FROM public.edge_devices WHERE id=a.device_id AND status='ACTIVE') THEN
                    RAISE EXCEPTION 'Camera already assigned' USING ERRCODE='23505';
                END IF;
                UPDATE public.edge_assignments SET enabled=false WHERE id=a.id;
                UPDATE public.edge_bindings SET enabled=false WHERE assignment_id=a.id;
                a.id:=NULL;
            END IF;
            IF a.id IS NULL THEN
                IF (SELECT count(*) FROM public.edge_assignments WHERE device_id=d.id AND enabled)>=4 THEN
                    RAISE EXCEPTION 'Device camera limit reached' USING ERRCODE='54000';
                END IF;
                INSERT INTO public.edge_assignments(id,organization_id,location_id,device_id,camera_id,epoch,
                    enabled,model_sha256,profile_sha256,profile_revision)
                    VALUES(gen_random_uuid(),org_,loc_,d.id,camera_,gen_random_uuid(),true,
                        value_->>'model_sha256',value_->>'profile_sha256',(value_->>'profile_revision')::integer)
                    RETURNING * INTO a;
            ELSE
                -- Changing camera policy retires every table epoch, not just this table.
                UPDATE public.edge_assignments SET epoch=gen_random_uuid(),policy_revision=policy_revision+1,
                    enabled=true,model_sha256=value_->>'model_sha256',profile_sha256=value_->>'profile_sha256',
                    profile_revision=(value_->>'profile_revision')::integer WHERE id=a.id RETURNING * INTO a;
                UPDATE public.edge_bindings SET epoch=gen_random_uuid() WHERE assignment_id=a.id;
            END IF;
            INSERT INTO public.edge_bindings(id,organization_id,location_id,assignment_id,device_id,
                camera_id,table_id,zone_revision,epoch)
                VALUES(gen_random_uuid(),org_,loc_,a.id,d.id,camera_,table_,zone_,gen_random_uuid())
                ON CONFLICT(table_id) WHERE enabled DO UPDATE SET zone_revision=EXCLUDED.zone_revision,
                    epoch=gen_random_uuid(),enabled=true
                WHERE public.edge_bindings.device_id=d.id AND public.edge_bindings.assignment_id=a.id;
            IF NOT FOUND THEN RAISE EXCEPTION 'Table already assigned' USING ERRCODE='23505'; END IF;
            UPDATE public.edge_devices SET revision=revision+1 WHERE id=d.id;
        ELSIF action_<>'rotate' THEN
            RAISE EXCEPTION 'Unsupported administration action' USING ERRCODE='23514';
        END IF;
    END IF;
    IF action_ IN ('approve','rotate') THEN
        IF action_='rotate' THEN
            UPDATE public.edge_keys SET expires_at=least(expires_at,clock_timestamp()+interval '10 minutes')
                WHERE device_id=d.id AND NOT revoked;
            UPDATE public.edge_devices SET revision=revision+1 WHERE id=d.id;
        END IF;
        INSERT INTO public.edge_keys(id,organization_id,location_id,device_id,public_key,fingerprint,expires_at)
            VALUES(p.key_id,org_,loc_,d.id,p.public_key,p.fingerprint,clock_timestamp()+interval '90 days');
        UPDATE edge_private.pairings SET device_id=d.id WHERE id=p.id;
    END IF;
    INSERT INTO public.audit_logs(id,organization_id,location_id,actor_id,action,details)
        VALUES(gen_random_uuid(),org_,loc_,security.actor(),'edge.'||action_,jsonb_build_object('device_id',d.id));
    PERFORM security.edge_publish(d.id,'configuration');
    SELECT revision INTO revision_ FROM public.edge_devices WHERE id=d.id;
    RETURN jsonb_build_object('device_id',d.id,'revision',revision_);
END $$;

CREATE FUNCTION security.edge_configuration() RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE d public.edge_devices;
BEGIN
    SELECT * INTO d FROM public.edge_devices WHERE id=security.edge_actor() AND status='ACTIVE';
    IF d.id IS NULL THEN RAISE EXCEPTION 'Device unavailable' USING ERRCODE='42501'; END IF;
    RETURN jsonb_build_object('device_id',d.id,'organization_id',d.organization_id,'location_id',d.location_id,
        'purpose',d.purpose,'revision',d.revision,'processing_enabled',d.processing_enabled,
        'assignments',coalesce((SELECT jsonb_agg(to_jsonb(a)) FROM public.edge_assignments a
            WHERE a.device_id=d.id AND a.enabled),'[]'::jsonb),
        'bindings',coalesce((SELECT jsonb_agg(to_jsonb(b)) FROM public.edge_bindings b
            JOIN public.edge_assignments a ON a.id=b.assignment_id WHERE b.device_id=d.id AND b.enabled AND a.enabled),'[]'::jsonb),
        'manual',coalesce((SELECT jsonb_agg(jsonb_build_object('id',t.id,'current_state',t.current_state,
            'operational_revision',t.operational_revision,'state_source',t.state_source,'state_since',t.state_since))
            FROM public.dining_tables t JOIN public.edge_bindings b ON b.table_id=t.id
            WHERE b.device_id=d.id AND b.enabled),'[]'::jsonb));
END $$;

CREATE FUNCTION security.edge_heartbeat(metrics_ jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE d public.edge_devices;
BEGIN
    SELECT * INTO STRICT d FROM public.edge_devices WHERE id=security.edge_actor() AND status='ACTIVE' FOR UPDATE;
    IF pg_column_size(metrics_)>1024 OR NOT metrics_ ?& ARRAY['camera','inference','queue_pending'] THEN
        RAISE EXCEPTION 'Invalid health' USING ERRCODE='23514';
    END IF;
    UPDATE public.edge_devices SET last_contact_at=clock_timestamp(),offline_published=false WHERE id=d.id;
    INSERT INTO public.edge_health(device_id,organization_id,location_id,measured_at,metrics)
        VALUES(d.id,d.organization_id,d.location_id,clock_timestamp(),metrics_)
        ON CONFLICT(device_id) DO UPDATE SET measured_at=EXCLUDED.measured_at,metrics=EXCLUDED.metrics;
    PERFORM security.edge_publish(d.id,'health');
    RETURN jsonb_build_object('server_time',clock_timestamp(),'lease_seconds',
        CASE WHEN d.processing_enabled THEN 3600 ELSE 0 END,'configuration',security.edge_configuration());
END $$;

CREATE FUNCTION security.edge_mark_offline() RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE d public.edge_devices; count_ integer := 0;
BEGIN
    FOR d IN SELECT * FROM public.edge_devices WHERE status='ACTIVE' AND NOT offline_published
        AND last_contact_at<clock_timestamp()-interval '45 seconds' ORDER BY id LIMIT 100 FOR UPDATE SKIP LOCKED LOOP
        UPDATE public.edge_devices SET offline_published=true WHERE id=d.id;
        PERFORM security.edge_publish(d.id,'offline');
        count_:=count_+1;
    END LOOP;
    RETURN count_;
END $$;

-- Test-only operational adapter. This cannot run in the business database.
-- Caller already owns device/table row locks; no human identity is manufactured.
CREATE FUNCTION security.edge_fixture(device_ uuid,event_ jsonb,demo_ boolean) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE d public.edge_devices; t public.dining_tables; old_ text; seq_ integer; episode_ uuid;
BEGIN
    SELECT * INTO STRICT d FROM public.edge_devices WHERE id=device_ AND id=security.edge_actor();
    IF NOT demo_ OR current_database() NOT LIKE 'phase2_security_test%'
        OR d.purpose<>'SYNTHETIC_WORKFLOW_TEST' OR NOT EXISTS(SELECT 1 FROM public.location_operations
            WHERE location_id=d.location_id AND organization_id=d.organization_id AND is_synthetic) THEN
        RAISE EXCEPTION 'Isolated synthetic fixture required' USING ERRCODE='42501';
    END IF;
    SELECT * INTO STRICT t FROM public.dining_tables WHERE id=(event_->>'table_id')::uuid
        AND organization_id=d.organization_id AND location_id=d.location_id FOR UPDATE;
    -- Previous fixture events are allowed to advance a synthetic episode; newer staff
    -- decisions, including ready confirmation, must always win over delayed messages.
    IF t.current_state IN ('CLEANING','OUT_OF_SERVICE') OR (t.state_source='manual'
        AND t.operational_revision<>(event_->>'manual_revision')::integer) THEN RETURN false; END IF;
    old_:=t.current_state; episode_:=(event_->>'occupancy_session_id')::uuid;
    IF episode_ IS NULL OR event_->>'reason'<>'FIXTURE' THEN RETURN false; END IF;
    IF event_->>'kind'='fixture_arrive' THEN
        IF t.current_state NOT IN ('UNKNOWN','AVAILABLE') OR EXISTS(SELECT 1 FROM public.staff_tasks
            WHERE table_id=t.id AND status IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS')) THEN RETURN false; END IF;
        t.current_state:='OCCUPIED'; t.occupancy_session_id:=episode_; t.occupied_since:=clock_timestamp();
        t.observation:='PRESENT';
    ELSIF event_->>'kind'='fixture_depart' THEN
        IF t.current_state<>'OCCUPIED' OR t.occupancy_session_id IS DISTINCT FROM episode_ THEN RETURN false; END IF;
        t.current_state:='RESET_PENDING'; t.observation:='VACANT';
        INSERT INTO public.staff_tasks(id,organization_id,location_id,table_id,occupancy_session_id)
            VALUES(gen_random_uuid(),d.organization_id,d.location_id,t.id,episode_) ON CONFLICT DO NOTHING;
    ELSE RETURN false;
    END IF;
    UPDATE public.dining_tables SET current_state=t.current_state,state_since=clock_timestamp(),
        state_source='edge_fixture',operational_revision=operational_revision+1,
        occupancy_session_id=t.occupancy_session_id,occupied_since=t.occupied_since,
        observation=t.observation,source_status='ONLINE',observed_at=clock_timestamp() WHERE id=t.id;
    UPDATE public.location_operations SET revision=revision+1 WHERE location_id=d.location_id RETURNING revision INTO seq_;
    INSERT INTO public.table_events(id,organization_id,location_id,table_id,revision,event_type,source,
        previous_state,new_state,payload) VALUES((event_->>'event_id')::uuid,d.organization_id,d.location_id,t.id,
            seq_,'table.fixture','edge_fixture',old_,t.current_state,
            jsonb_build_object('device_id',d.id,'synthetic',true,'authoritative_ai',false));
    RETURN true;
END $$;

CREATE FUNCTION security.edge_ingest(items_ jsonb,demo_ boolean) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE d public.edge_devices; r public.edge_receipts; existing_ public.edge_receipts;
        e jsonb; b public.edge_bindings; a public.edge_assignments; t public.dining_tables;
        disposition_ text; reason_ text; count_ integer:=0; replies_ jsonb;
BEGIN
    SELECT * INTO d FROM public.edge_devices WHERE id=security.edge_actor() AND status='ACTIVE' FOR UPDATE;
    IF d.id IS NULL OR jsonb_typeof(items_)<>'array' OR jsonb_array_length(items_) NOT BETWEEN 1 AND 100
        OR pg_column_size(items_)>262144 THEN
        RAISE EXCEPTION 'Invalid device batch' USING ERRCODE='42501';
    END IF;
    -- Global per-device cursor and UUID/hash identity survive backend/device restarts.
    FOR e IN SELECT value FROM jsonb_array_elements(items_) LOOP
        IF (e->'event'->>'device_id')::uuid<>d.id
            OR (e->'event'->>'organization_id')::uuid<>d.organization_id
            OR (e->'event'->>'location_id')::uuid<>d.location_id
            OR (e->>'sha256') !~ '^[0-9a-f]{64}$' THEN
            RAISE EXCEPTION 'Device scope mismatch' USING ERRCODE='42501';
        END IF;
        IF d.stream_id IS NULL THEN
            IF (e->'event'->>'sequence')::integer>1000 THEN
                RAISE EXCEPTION 'Stream gap too large' USING ERRCODE='23514';
            END IF;
            d.stream_id:=(e->'event'->>'stream_id')::uuid;
            UPDATE public.edge_devices SET stream_id=d.stream_id WHERE id=d.id;
        END IF;
        IF (e->'event'->>'stream_id')::uuid<>d.stream_id
            OR (e->'event'->>'sequence')::integer>d.stream_cursor+1000 THEN
            RAISE EXCEPTION 'Stream changed or gap too large' USING ERRCODE='23514';
        END IF;
        SELECT * INTO existing_ FROM public.edge_receipts WHERE event_id=(e->'event'->>'event_id')::uuid;
        IF existing_.event_id IS NOT NULL THEN
            IF existing_.device_id<>d.id OR existing_.sha256<>e->>'sha256'
                OR existing_.sequence<>(e->'event'->>'sequence')::integer THEN
                RAISE EXCEPTION 'Event identity conflict' USING ERRCODE='23505';
            END IF;
            CONTINUE;
        END IF;
        IF (e->'event'->>'sequence')::integer<=d.stream_cursor THEN
            RAISE EXCEPTION 'Sequence identity conflict' USING ERRCODE='23505';
        END IF;
        -- No foreign camera/table detail is returned or persisted for a forged binding.
        SELECT * INTO b FROM public.edge_bindings WHERE id=(e->'event'->>'binding_id')::uuid
            AND device_id=d.id AND organization_id=d.organization_id AND location_id=d.location_id
            AND table_id=(e->'event'->>'table_id')::uuid AND camera_id=(e->'event'->>'camera_id')::uuid;
        IF b.id IS NULL THEN RAISE EXCEPTION 'Invalid device binding' USING ERRCODE='42501'; END IF;
        INSERT INTO public.edge_receipts(event_id,organization_id,location_id,device_id,stream_id,sequence,sha256,payload)
            VALUES((e->'event'->>'event_id')::uuid,d.organization_id,d.location_id,d.id,d.stream_id,
                (e->'event'->>'sequence')::integer,e->>'sha256',e->'event');
    END LOOP;
    -- Match the existing human workflow lock order (tables in UUID order, then location).
    -- Revocation/configuration serialize first on this device, preventing write-after-revoke.
    PERFORM t_.id FROM public.dining_tables t_ JOIN public.edge_bindings b_ ON b_.table_id=t_.id
        WHERE b_.device_id=d.id ORDER BY t_.id FOR UPDATE OF t_;
    LOOP
        SELECT * INTO r FROM public.edge_receipts WHERE device_id=d.id AND stream_id=d.stream_id
            AND sequence=d.stream_cursor+1 AND disposition='pending';
        EXIT WHEN NOT FOUND OR count_>=1000;
        e:=r.payload; disposition_:='shadow'; reason_:='ACCEPTED';
        SELECT * INTO b FROM public.edge_bindings WHERE id=(e->>'binding_id')::uuid AND device_id=d.id;
        SELECT * INTO a FROM public.edge_assignments WHERE id=b.assignment_id;
        SELECT * INTO t FROM public.dining_tables WHERE id=b.table_id;
        IF NOT d.processing_enabled OR NOT b.enabled OR NOT a.enabled OR b.epoch<>(e->>'binding_epoch')::uuid
            OR b.zone_revision<>(e->>'zone_revision')::integer
            OR a.profile_revision<>(e->>'profile_revision')::integer
            OR a.profile_sha256<>e->>'profile_sha256' OR a.model_sha256<>e->>'model_sha256'
            OR a.policy_revision<>(e->>'policy_revision')::integer OR NOT EXISTS(SELECT 1 FROM public.table_zones z
                WHERE z.table_id=b.table_id AND z.camera_id=b.camera_id AND z.revision=b.zone_revision) THEN
            disposition_:='history'; reason_:='CONFIG_CHANGED';
        ELSIF (e->>'occurred_at')::timestamptz<clock_timestamp()-interval '30 seconds'
            OR (e->>'occurred_at')::timestamptz>clock_timestamp()+interval '2 minutes' THEN
            disposition_:='history'; reason_:='STALE';
        ELSIF t.state_source='manual' AND t.operational_revision<>(e->>'manual_revision')::integer THEN
            disposition_:='history'; reason_:='MANUAL_CHANGED';
        ELSIF t.current_state IN ('CLEANING','OUT_OF_SERVICE') THEN
            disposition_:='history'; reason_:='PROTECTED';
        ELSIF e->>'kind'<>'shadow' THEN
            IF security.edge_fixture(d.id,e,demo_) THEN disposition_:='fixture';
            ELSE disposition_:='history'; reason_:='PROTECTED'; END IF;
        ELSE
            INSERT INTO public.edge_shadows(binding_id,device_id,organization_id,location_id,sequence,state,occurred_at,reason)
                VALUES(b.id,d.id,d.organization_id,d.location_id,r.sequence,e->>'state',(e->>'occurred_at')::timestamptz,e->>'reason')
                ON CONFLICT(binding_id) DO UPDATE SET sequence=EXCLUDED.sequence,state=EXCLUDED.state,
                    occurred_at=EXCLUDED.occurred_at,reason=EXCLUDED.reason WHERE public.edge_shadows.sequence<EXCLUDED.sequence;
        END IF;
        UPDATE public.edge_receipts SET disposition=disposition_,reason=reason_ WHERE event_id=r.event_id;
        INSERT INTO public.edge_audits(id,organization_id,location_id,device_id,action,event_id)
            VALUES(gen_random_uuid(),d.organization_id,d.location_id,d.id,'event.'||disposition_,r.event_id);
        d.stream_cursor:=r.sequence; count_:=count_+1;
    END LOOP;
    UPDATE public.edge_devices SET stream_cursor=d.stream_cursor,last_contact_at=clock_timestamp(),offline_published=false WHERE id=d.id;
    IF count_>0 THEN PERFORM security.edge_publish(d.id,'shadow'); END IF;
    SELECT jsonb_agg(jsonb_build_object('event_id',r_.event_id,'sequence',r_.sequence,'sha256',r_.sha256,
        'disposition',r_.disposition,'reason',r_.reason) ORDER BY r_.sequence) INTO replies_
        FROM public.edge_receipts r_ WHERE r_.device_id=d.id AND r_.event_id IN
            (SELECT (value->'event'->>'event_id')::uuid FROM jsonb_array_elements(items_));
    RETURN jsonb_build_object('receipts',replies_,'cursor',d.stream_cursor);
END $$;

-- All functions are private to explicitly provisioned runtime roles.
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA security FROM PUBLIC;
