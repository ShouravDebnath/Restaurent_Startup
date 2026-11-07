-- Immutable supporting DDL for revision 0001. Add new revisions for future changes.
CREATE SCHEMA identity;
CREATE SCHEMA security;
REVOKE ALL ON SCHEMA identity, security FROM PUBLIC;

CREATE FUNCTION security.valid_polygon(p jsonb) RETURNS boolean
LANGUAGE plpgsql IMMUTABLE SET search_path = pg_catalog AS $$
DECLARE
    n integer; i integer; j integer; k integer; l integer;
    ax double precision; ay double precision; bx double precision; by_ double precision;
    cx double precision; cy double precision; dx double precision; dy double precision;
    o1 double precision; o2 double precision; o3 double precision; o4 double precision;
    area double precision := 0;
BEGIN
    IF jsonb_typeof(p) <> 'array' THEN RETURN false; END IF;
    n := jsonb_array_length(p);
    IF n < 3 OR n > 64 THEN RETURN false; END IF;
    FOR i IN 0..n-1 LOOP
        IF jsonb_typeof(p->i) <> 'array' OR jsonb_array_length(p->i) <> 2
           OR jsonb_typeof(p->i->0) <> 'number' OR jsonb_typeof(p->i->1) <> 'number'
        THEN RETURN false; END IF;
        ax := (p->i->>0)::double precision; ay := (p->i->>1)::double precision;
        IF ax < 0 OR ax > 1 OR ay < 0 OR ay > 1 THEN RETURN false; END IF;
        FOR j IN i+1..n-1 LOOP
            IF p->i = p->j THEN RETURN false; END IF;
        END LOOP;
        k := (i+1) % n;
        area := area + ax*(p->k->>1)::double precision - ay*(p->k->>0)::double precision;
    END LOOP;
    IF abs(area) < 0.00000001 THEN RETURN false; END IF;
    FOR i IN 0..n-1 LOOP
        k := (i+1) % n;
        ax := (p->i->>0)::double precision; ay := (p->i->>1)::double precision;
        bx := (p->k->>0)::double precision; by_ := (p->k->>1)::double precision;
        FOR j IN i+1..n-1 LOOP
            l := (j+1) % n;
            IF j = k OR l = i THEN CONTINUE; END IF;
            cx := (p->j->>0)::double precision; cy := (p->j->>1)::double precision;
            dx := (p->l->>0)::double precision; dy := (p->l->>1)::double precision;
            o1 := (bx-ax)*(cy-ay)-(by_-ay)*(cx-ax);
            o2 := (bx-ax)*(dy-ay)-(by_-ay)*(dx-ax);
            o3 := (dx-cx)*(ay-cy)-(dy-cy)*(ax-cx);
            o4 := (dx-cx)*(by_-cy)-(dy-cy)*(bx-cx);
            IF o1*o2 <= 0 AND o3*o4 <= 0
               AND greatest(least(ax,bx),least(cx,dx)) <= least(greatest(ax,bx),greatest(cx,dx))
               AND greatest(least(ay,by_),least(cy,dy)) <= least(greatest(ay,by_),greatest(cy,dy))
            THEN RETURN false; END IF;
        END LOOP;
    END LOOP;
    RETURN true;
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;
