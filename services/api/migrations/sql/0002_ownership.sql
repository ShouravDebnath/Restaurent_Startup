CREATE FUNCTION security.location_belongs(org uuid, loc uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
    SELECT security.has_role(org,ARRAY['owner','org_admin']) AND EXISTS(
        SELECT 1 FROM public.locations WHERE id=loc AND organization_id=org)
$$;
CREATE FUNCTION security.can_manage_grants(org uuid, member uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
    SELECT security.has_role(org,ARRAY['owner']) OR (
        security.has_role(org,ARRAY['org_admin']) AND EXISTS(
            SELECT 1 FROM public.memberships WHERE id=member AND organization_id=org AND role<>'owner'))
$$;
DROP POLICY grant_insert ON public.location_grants;
DROP POLICY grant_update ON public.location_grants;
CREATE POLICY grant_insert ON public.location_grants FOR INSERT
    WITH CHECK(security.can_manage_grants(organization_id,membership_id));
CREATE POLICY grant_update ON public.location_grants FOR UPDATE
    USING(security.can_manage_grants(organization_id,membership_id))
    WITH CHECK(security.can_manage_grants(organization_id,membership_id));

CREATE FUNCTION security.immutable_ownership() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE field_ text;
BEGIN
    FOREACH field_ IN ARRAY TG_ARGV LOOP
        IF to_jsonb(NEW)->field_ IS DISTINCT FROM to_jsonb(OLD)->field_ THEN
            RAISE EXCEPTION 'Ownership is immutable' USING ERRCODE='23514';
        END IF;
    END LOOP;
    RETURN NEW;
END $$;
CREATE TRIGGER immutable_ownership BEFORE UPDATE ON public.locations
FOR EACH ROW EXECUTE FUNCTION security.immutable_ownership('id','organization_id');
CREATE TRIGGER immutable_ownership BEFORE UPDATE ON public.memberships
FOR EACH ROW EXECUTE FUNCTION security.immutable_ownership('id','organization_id','user_id');
CREATE TRIGGER immutable_ownership BEFORE UPDATE ON public.location_grants
FOR EACH ROW EXECUTE FUNCTION security.immutable_ownership('organization_id','membership_id','location_id');
CREATE TRIGGER immutable_ownership BEFORE UPDATE ON public.cameras
FOR EACH ROW EXECUTE FUNCTION security.immutable_ownership('id','organization_id','location_id');
CREATE TRIGGER immutable_ownership BEFORE UPDATE ON public.dining_tables
FOR EACH ROW EXECUTE FUNCTION security.immutable_ownership('id','organization_id','location_id');
CREATE TRIGGER immutable_ownership BEFORE UPDATE ON public.table_zones
FOR EACH ROW EXECUTE FUNCTION security.immutable_ownership('id','organization_id','location_id');
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA security FROM PUBLIC;
