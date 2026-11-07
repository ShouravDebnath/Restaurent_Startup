-- Additive only. No existing geometry, credentials or operational state is replaced.
ALTER TABLE public.table_zones ADD COLUMN view_metadata jsonb;
ALTER TABLE public.table_zones ADD CONSTRAINT zone_scoped_id UNIQUE(id,organization_id,location_id);

CREATE TABLE public.table_zone_revisions (
    id uuid PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now(),
    organization_id uuid NOT NULL, location_id uuid NOT NULL,
    zone_id uuid NOT NULL, camera_id uuid NOT NULL, table_id uuid NOT NULL,
    revision integer NOT NULL CHECK(revision>=1), actor_id uuid REFERENCES identity.users(id),
    snapshot jsonb NOT NULL, reason varchar(32) NOT NULL,
    request_key uuid, fingerprint varchar(64),
    UNIQUE(zone_id,revision), UNIQUE(actor_id,location_id,request_key),
    FOREIGN KEY(zone_id,organization_id,location_id) REFERENCES public.table_zones(id,organization_id,location_id),
    FOREIGN KEY(camera_id,organization_id,location_id) REFERENCES public.cameras(id,organization_id,location_id),
    FOREIGN KEY(table_id,organization_id,location_id) REFERENCES public.dining_tables(id,organization_id,location_id)
);
CREATE INDEX ix_table_zone_revisions_organization_id ON public.table_zone_revisions(organization_id);
CREATE INDEX ix_table_zone_revisions_location_id ON public.table_zone_revisions(location_id);
INSERT INTO public.table_zone_revisions
    (id,organization_id,location_id,zone_id,camera_id,table_id,revision,snapshot,reason)
SELECT gen_random_uuid(),organization_id,location_id,id,camera_id,table_id,revision,to_jsonb(z),
    'legacy_snapshot' FROM public.table_zones z;

CREATE TABLE public.camera_preview_grants (
    id uuid PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now(),
    organization_id uuid NOT NULL, location_id uuid NOT NULL, camera_id uuid NOT NULL,
    viewer_id uuid NOT NULL REFERENCES identity.users(id),
    granted_by uuid NOT NULL REFERENCES identity.users(id), duration_seconds integer NOT NULL,
    expires_at timestamptz NOT NULL, revoked_at timestamptz,
    CONSTRAINT preview_duration CHECK(duration_seconds BETWEEN 60 AND 3600),
    CONSTRAINT preview_expiration CHECK(expires_at=created_at+duration_seconds*interval '1 second'),
    FOREIGN KEY(camera_id,organization_id,location_id) REFERENCES public.cameras(id,organization_id,location_id)
);
CREATE INDEX ix_camera_preview_grants_organization_id ON public.camera_preview_grants(organization_id);
CREATE INDEX ix_camera_preview_grants_location_id ON public.camera_preview_grants(location_id);
CREATE INDEX preview_viewer_camera ON public.camera_preview_grants(viewer_id,camera_id,expires_at);
ALTER TABLE public.table_zone_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.camera_preview_grants ENABLE ROW LEVEL SECURITY;
CREATE POLICY history_read ON public.table_zone_revisions FOR SELECT USING (
    security.allowed_location(organization_id,location_id) AND
    security.has_role(organization_id,ARRAY['owner','org_admin','manager','installer']));
CREATE POLICY preview_read ON public.camera_preview_grants FOR SELECT USING (
    security.allowed_location(organization_id,location_id) AND
    security.has_role(organization_id,ARRAY['owner','org_admin','manager','installer']) AND
    (viewer_id=security.actor() OR security.has_role(organization_id,ARRAY['owner','org_admin','manager'])));

CREATE FUNCTION security.capture_calibration() RETURNS trigger LANGUAGE plpgsql
SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor_ uuid:=security.actor(); key_ uuid; fingerprint_ text;
BEGIN
    IF actor_ IS NULL THEN
        IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=session_user AND (rolsuper OR rolbypassrls)) THEN
            RAISE EXCEPTION 'Authentication required' USING ERRCODE='42501';
        END IF;
    ELSIF NOT security.allowed_location(NEW.organization_id,NEW.location_id) OR
          NOT security.has_role(NEW.organization_id,ARRAY['owner','org_admin','manager','installer']) THEN
        RAISE EXCEPTION 'Not permitted' USING ERRCODE='42501';
    END IF;
    IF TG_OP='UPDATE' AND NEW.revision<>OLD.revision+1 THEN
        RAISE EXCEPTION 'Revision must advance once' USING ERRCODE='23514';
    END IF;
    key_:=nullif(current_setting('app.calibration_key',true),'')::uuid;
    fingerprint_:=nullif(current_setting('app.calibration_fingerprint',true),'');
    INSERT INTO public.table_zone_revisions
        (id,organization_id,location_id,zone_id,camera_id,table_id,revision,actor_id,snapshot,reason,request_key,fingerprint)
    VALUES(gen_random_uuid(),NEW.organization_id,NEW.location_id,NEW.id,NEW.camera_id,NEW.table_id,
        NEW.revision,actor_,to_jsonb(NEW),CASE WHEN TG_OP='INSERT' THEN 'zone_created' ELSE 'zone_updated' END,
        key_,fingerprint_);
    RETURN NEW;
END $$;
CREATE TRIGGER capture_calibration AFTER INSERT OR UPDATE ON public.table_zones
FOR EACH ROW EXECUTE FUNCTION security.capture_calibration();

CREATE FUNCTION security.preview_action(camera_ uuid, grant_ uuid, viewer_ uuid, seconds_ integer, revoke_ boolean)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE c public.cameras; g public.camera_preview_grants; actor_ uuid:=security.actor(); time_ timestamptz;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended(grant_::text,724));
    SELECT * INTO c FROM public.cameras WHERE id=camera_;
    IF NOT FOUND OR NOT security.allowed_location(c.organization_id,c.location_id) THEN
        RAISE EXCEPTION 'Not found' USING ERRCODE='P0404';
    END IF;
    IF NOT security.has_role(c.organization_id,ARRAY['owner','org_admin','manager']) THEN
        RAISE EXCEPTION 'Not permitted' USING ERRCODE='P0403';
    END IF;
    SELECT * INTO g FROM public.camera_preview_grants WHERE id=grant_ FOR UPDATE;
    IF revoke_ THEN
        IF g.id IS NULL OR g.camera_id<>camera_ THEN RAISE EXCEPTION 'Not found' USING ERRCODE='P0404'; END IF;
        IF g.revoked_at IS NULL THEN
            UPDATE public.camera_preview_grants SET revoked_at=clock_timestamp() WHERE id=g.id;
            INSERT INTO public.audit_logs(id,organization_id,location_id,actor_id,action,details)
            VALUES(gen_random_uuid(),c.organization_id,c.location_id,actor_,'preview.revoked',jsonb_build_object('grant_id',g.id));
        END IF;
        RETURN grant_;
    END IF;
    IF seconds_ NOT BETWEEN 60 AND 3600 OR NOT EXISTS (
        SELECT 1 FROM public.memberships m JOIN identity.users u ON u.id=m.user_id
        JOIN public.location_grants l ON l.membership_id=m.id AND l.organization_id=m.organization_id
        WHERE m.user_id=viewer_ AND m.organization_id=c.organization_id AND m.enabled AND u.enabled
        AND m.role IN ('owner','org_admin','manager','installer') AND l.location_id=c.location_id AND l.enabled
    ) THEN RAISE EXCEPTION 'Viewer is not eligible' USING ERRCODE='P0422'; END IF;
    IF g.id IS NOT NULL THEN
        IF g.camera_id<>camera_ OR g.granted_by<>actor_ OR g.viewer_id<>viewer_ OR g.duration_seconds<>seconds_ THEN
            RAISE EXCEPTION 'Request conflicts' USING ERRCODE='P0409';
        END IF;
        RETURN grant_;
    END IF;
    time_:=clock_timestamp();
    INSERT INTO public.camera_preview_grants(id,created_at,organization_id,location_id,camera_id,viewer_id,
        granted_by,duration_seconds,expires_at)
    VALUES(grant_,time_,c.organization_id,c.location_id,camera_,viewer_,actor_,seconds_,time_+seconds_*interval '1 second');
    INSERT INTO public.audit_logs(id,organization_id,location_id,actor_id,action,details)
    VALUES(gen_random_uuid(),c.organization_id,c.location_id,actor_,'preview.granted',
        jsonb_build_object('grant_id',grant_,'camera_id',camera_,'viewer_id',viewer_,'duration_seconds',seconds_));
    RETURN grant_;
END $$;
REVOKE ALL ON FUNCTION security.capture_calibration() FROM PUBLIC;
REVOKE ALL ON FUNCTION security.preview_action(uuid,uuid,uuid,integer,boolean) FROM PUBLIC;

