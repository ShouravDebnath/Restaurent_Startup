-- Additive follow-up: terminal owned-envelope rejection without invalid raw payload.
-- Existing 0007 stays frozen; no old business row is rewritten.
ALTER TABLE public.edge_shadows ADD COLUMN source_generation uuid;
ALTER TABLE public.edge_shadows ADD COLUMN needs_context boolean NOT NULL DEFAULT false;

CREATE OR REPLACE FUNCTION security.edge_ingest(items_ jsonb,demo_ boolean) RETURNS jsonb
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
        IF coalesce((e->>'_rejected')::boolean,false) THEN
            disposition_:='rejected'; reason_:='INVALID';
            INSERT INTO public.edge_shadows(binding_id,device_id,organization_id,location_id,sequence,state,
                occurred_at,reason,source_generation,needs_context)
                VALUES(b.id,d.id,d.organization_id,d.location_id,r.sequence,'UNKNOWN',clock_timestamp(),
                    'REJECTED_EVENT',(e->>'source_generation')::uuid,true)
                ON CONFLICT(binding_id) DO UPDATE SET sequence=EXCLUDED.sequence,state='UNKNOWN',
                    occurred_at=EXCLUDED.occurred_at,reason='REJECTED_EVENT',
                    source_generation=EXCLUDED.source_generation,needs_context=true;
        ELSIF EXISTS(SELECT 1 FROM public.edge_shadows s WHERE s.binding_id=b.id AND s.needs_context
            AND s.source_generation=(e->>'source_generation')::uuid) THEN
            disposition_:='history'; reason_:='CONTEXT_REQUIRED';
        ELSIF NOT d.processing_enabled OR NOT b.enabled OR NOT a.enabled OR b.epoch<>(e->>'binding_epoch')::uuid
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
            INSERT INTO public.edge_shadows(binding_id,device_id,organization_id,location_id,sequence,state,
                occurred_at,reason,source_generation,needs_context)
                VALUES(b.id,d.id,d.organization_id,d.location_id,r.sequence,e->>'state',
                    (e->>'occurred_at')::timestamptz,e->>'reason',(e->>'source_generation')::uuid,false)
                ON CONFLICT(binding_id) DO UPDATE SET sequence=EXCLUDED.sequence,state=EXCLUDED.state,
                    occurred_at=EXCLUDED.occurred_at,reason=EXCLUDED.reason,
                    source_generation=EXCLUDED.source_generation,needs_context=false
                WHERE public.edge_shadows.sequence<EXCLUDED.sequence;
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
