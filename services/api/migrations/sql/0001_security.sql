-- Immutable DDL. Runtime receives only selected table privileges and function execution.
CREATE FUNCTION security.actor() RETURNS uuid LANGUAGE sql STABLE
SET search_path = pg_catalog AS $$
    SELECT nullif(current_setting('app.user_id', true), '')::uuid
$$;

CREATE FUNCTION security.has_role(org uuid, roles text[]) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.memberships m JOIN identity.users u ON u.id = m.user_id
        WHERE m.user_id = security.actor() AND m.organization_id = org
          AND m.enabled AND u.enabled AND m.role = ANY(roles)
    )
$$;

CREATE FUNCTION security.allowed_org(org uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT security.has_role(org, ARRAY['owner','org_admin','manager','staff','installer'])
$$;

CREATE FUNCTION security.allowed_location(org uuid, loc uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.memberships m
        JOIN identity.users u ON u.id = m.user_id
        JOIN public.location_grants g ON g.membership_id = m.id AND g.organization_id = org
        WHERE m.user_id = security.actor() AND m.organization_id = org
          AND g.location_id = loc AND m.enabled AND g.enabled AND u.enabled
    )
$$;

CREATE FUNCTION security.own_membership(member uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT EXISTS (SELECT 1 FROM public.memberships m
        WHERE m.id = member AND m.user_id = security.actor())
$$;

CREATE FUNCTION security.credentials(email_ text)
RETURNS TABLE(user_id uuid, password_hash text, enabled boolean)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT u.id, u.password_hash::text, u.enabled FROM identity.users u WHERE u.email = email_
$$;

CREATE FUNCTION security.login_attempt(key_ text, limit_ integer) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE attempts_ integer;
BEGIN
    INSERT INTO identity.login_buckets AS b (key, attempts, window_start)
    VALUES (key_, 1, now())
    ON CONFLICT (key) DO UPDATE SET
        attempts = CASE WHEN b.window_start < now()-interval '15 minutes'
                        THEN 1 ELSE b.attempts+1 END,
        window_start = CASE WHEN b.window_start < now()-interval '15 minutes'
                            THEN now() ELSE b.window_start END
    RETURNING attempts INTO attempts_;
    RETURN attempts_ <= least(greatest(limit_,1),100);
END $$;

CREATE FUNCTION security.new_session(user_ uuid, digest_ text, lifetime_ integer) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM identity.users WHERE id=user_ AND enabled) THEN
        RAISE EXCEPTION 'Invalid identity' USING ERRCODE='42501';
    END IF;
    INSERT INTO identity.sessions (token_digest,user_id,created_at,last_seen_at,expires_at,revoked)
    VALUES(digest_,user_,now(),now(),now()+make_interval(secs=>least(lifetime_,28800)),false);
END $$;

CREATE FUNCTION security.resolve_session(digest_ text, idle_ integer) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE result uuid;
BEGIN
    UPDATE identity.sessions s SET last_seen_at=now() FROM identity.users u
    WHERE s.token_digest=digest_ AND s.user_id=u.id AND u.enabled AND NOT s.revoked
      AND s.expires_at>now() AND s.last_seen_at>now()-make_interval(secs=>least(idle_,1800))
    RETURNING s.user_id INTO result;
    RETURN result;
END $$;

CREATE FUNCTION security.revoke_session(digest_ text) RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog AS $$
    UPDATE identity.sessions SET revoked=true WHERE token_digest=digest_
$$;

CREATE FUNCTION security.profile()
RETURNS TABLE(id uuid, email text, display_name text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT u.id,u.email::text,u.display_name::text FROM identity.users u
    WHERE u.id=security.actor() AND u.enabled
$$;

CREATE FUNCTION security.member_profile(member uuid)
RETURNS TABLE(email text, display_name text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT u.email::text,u.display_name::text FROM identity.users u
    JOIN public.memberships m ON m.user_id=u.id
    WHERE m.id=member AND (m.user_id=security.actor()
        OR security.has_role(m.organization_id,ARRAY['owner','org_admin']))
$$;

CREATE FUNCTION security.find_user(org uuid, email_ text) RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT u.id FROM identity.users u WHERE u.email=email_ AND u.enabled
      AND security.has_role(org,ARRAY['owner','org_admin'])
$$;

CREATE FUNCTION security.create_organization(name_ text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE org uuid := gen_random_uuid();
BEGIN
    IF NOT EXISTS(SELECT 1 FROM identity.users WHERE id=security.actor() AND enabled) THEN
        RAISE EXCEPTION 'Invalid identity' USING ERRCODE='42501';
    END IF;
    INSERT INTO public.organizations(id,name) VALUES(org,name_);
    INSERT INTO public.memberships(id,user_id,organization_id,role)
        VALUES(gen_random_uuid(),security.actor(),org,'owner');
    INSERT INTO public.audit_logs(id,organization_id,actor_id,action,details)
        VALUES(gen_random_uuid(),org,security.actor(),'organization.created','{}'::jsonb);
    RETURN org;
END $$;

CREATE FUNCTION security.create_location(org uuid, name_ text, zone_ text, address_ text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE loc uuid := gen_random_uuid(); member uuid;
BEGIN
    IF NOT security.has_role(org,ARRAY['owner','org_admin']) THEN
        RAISE EXCEPTION 'Not authorized' USING ERRCODE='42501';
    END IF;
    IF NOT EXISTS(SELECT 1 FROM pg_timezone_names WHERE name=zone_) THEN
        RAISE EXCEPTION 'Invalid time zone' USING ERRCODE='23514';
    END IF;
    SELECT id INTO member FROM public.memberships
        WHERE user_id=security.actor() AND organization_id=org;
    INSERT INTO public.locations(id,organization_id,name,time_zone,address)
        VALUES(loc,org,name_,zone_,address_);
    INSERT INTO public.location_grants(membership_id,organization_id,location_id)
        VALUES(member,org,loc);
    RETURN loc;
END $$;

CREATE FUNCTION security.keep_owner() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog AS $$
BEGIN
    IF OLD.role='owner' AND OLD.enabled AND (NEW.role<>'owner' OR NOT NEW.enabled) THEN
        PERFORM 1 FROM public.organizations WHERE id=OLD.organization_id FOR UPDATE;
        IF NOT EXISTS(SELECT 1 FROM public.memberships WHERE organization_id=OLD.organization_id
                      AND id<>OLD.id AND enabled AND role='owner') THEN
            RAISE EXCEPTION 'An enabled owner is required' USING ERRCODE='23514';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER memberships_keep_owner BEFORE UPDATE ON public.memberships
FOR EACH ROW EXECUTE FUNCTION security.keep_owner();

ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
CREATE POLICY organization_read ON public.organizations FOR SELECT
    USING(security.allowed_org(id));
CREATE POLICY organization_update ON public.organizations FOR UPDATE
    USING(security.has_role(id,ARRAY['owner','org_admin']))
    WITH CHECK(security.has_role(id,ARRAY['owner','org_admin']));

ALTER TABLE public.locations ENABLE ROW LEVEL SECURITY;
CREATE POLICY location_read ON public.locations FOR SELECT
    USING(security.allowed_location(organization_id,id));
CREATE POLICY location_update ON public.locations FOR UPDATE
    USING(security.allowed_location(organization_id,id)
          AND security.has_role(organization_id,ARRAY['owner','org_admin']))
    WITH CHECK(security.allowed_location(organization_id,id)
          AND security.has_role(organization_id,ARRAY['owner','org_admin']));

ALTER TABLE public.memberships ENABLE ROW LEVEL SECURITY;
CREATE POLICY membership_read ON public.memberships FOR SELECT
    USING(user_id=security.actor() OR security.has_role(organization_id,ARRAY['owner','org_admin']));
CREATE POLICY membership_insert ON public.memberships FOR INSERT
    WITH CHECK(security.has_role(organization_id,ARRAY['owner'])
        OR (role<>'owner' AND security.has_role(organization_id,ARRAY['org_admin'])));
CREATE POLICY membership_update ON public.memberships FOR UPDATE
    USING(security.has_role(organization_id,ARRAY['owner'])
        OR (role<>'owner' AND security.has_role(organization_id,ARRAY['org_admin'])))
    WITH CHECK(security.has_role(organization_id,ARRAY['owner'])
        OR (role<>'owner' AND security.has_role(organization_id,ARRAY['org_admin'])));

ALTER TABLE public.location_grants ENABLE ROW LEVEL SECURITY;
CREATE POLICY grant_read ON public.location_grants FOR SELECT
    USING(security.own_membership(membership_id)
        OR security.has_role(organization_id,ARRAY['owner','org_admin']));
CREATE POLICY grant_insert ON public.location_grants FOR INSERT
    WITH CHECK(security.has_role(organization_id,ARRAY['owner','org_admin']));
CREATE POLICY grant_update ON public.location_grants FOR UPDATE
    USING(security.has_role(organization_id,ARRAY['owner','org_admin']))
    WITH CHECK(security.has_role(organization_id,ARRAY['owner','org_admin']));

DO $$ DECLARE table_ text; roles_ text; BEGIN
    FOREACH table_ IN ARRAY ARRAY['cameras','dining_tables','table_zones'] LOOP
        roles_ := CASE WHEN table_='dining_tables' THEN '''owner'',''org_admin'',''manager'''
                      ELSE '''owner'',''org_admin'',''manager'',''installer''' END;
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',table_);
        EXECUTE format('CREATE POLICY resource_read ON public.%I FOR SELECT
            USING(security.allowed_location(organization_id,location_id))',table_);
        EXECUTE format('CREATE POLICY resource_insert ON public.%I FOR INSERT
            WITH CHECK(security.allowed_location(organization_id,location_id)
            AND security.has_role(organization_id,ARRAY[%s]))',table_,roles_);
        EXECUTE format('CREATE POLICY resource_update ON public.%I FOR UPDATE
            USING(security.allowed_location(organization_id,location_id)
            AND security.has_role(organization_id,ARRAY[%s]))
            WITH CHECK(security.allowed_location(organization_id,location_id)
            AND security.has_role(organization_id,ARRAY[%s]))',table_,roles_,roles_);
    END LOOP;
END $$;

ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY audit_read ON public.audit_logs FOR SELECT USING(
    (location_id IS NULL AND security.has_role(organization_id,ARRAY['owner','org_admin']))
    OR (location_id IS NOT NULL AND security.allowed_location(organization_id,location_id)
        AND security.has_role(organization_id,ARRAY['owner','org_admin','manager'])));
CREATE POLICY audit_insert ON public.audit_logs FOR INSERT WITH CHECK(
    actor_id=security.actor() AND security.allowed_org(organization_id)
    AND (location_id IS NULL OR security.allowed_location(organization_id,location_id)));

REVOKE ALL ON ALL TABLES IN SCHEMA identity FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA security FROM PUBLIC;
