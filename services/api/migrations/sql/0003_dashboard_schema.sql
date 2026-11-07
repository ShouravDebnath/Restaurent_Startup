-- Additive Phase 3 schema; existing state/history and credentials are preserved.
ALTER TABLE public.dining_tables
    ADD COLUMN operational_revision integer NOT NULL DEFAULT 0,
    ADD COLUMN state_source varchar(16) NOT NULL DEFAULT 'unverified',
    ADD COLUMN occupancy_session_id uuid,
    ADD COLUMN occupied_since timestamptz,
    ADD COLUMN source_status varchar(24) NOT NULL DEFAULT 'NOT_CONFIGURED',
    ADD COLUMN observation varchar(16) NOT NULL DEFAULT 'UNKNOWN',
    ADD COLUMN observed_at timestamptz;


CREATE TABLE location_operations (
	location_id UUID NOT NULL,
	is_synthetic BOOLEAN DEFAULT 'false' NOT NULL,
	revision INTEGER DEFAULT '0' NOT NULL,
	organization_id UUID NOT NULL,
	PRIMARY KEY (location_id),
	FOREIGN KEY(location_id, organization_id) REFERENCES locations (id, organization_id),
	CONSTRAINT location_revision CHECK (revision >= 0)
)

;
CREATE INDEX ix_location_operations_organization_id ON location_operations (organization_id);

CREATE TABLE table_events (
	table_id UUID NOT NULL,
	revision INTEGER NOT NULL,
	event_type VARCHAR(64) NOT NULL,
	source VARCHAR(16) NOT NULL,
	actor_id UUID,
	occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	ingested_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	schema_version INTEGER DEFAULT '1' NOT NULL,
	previous_state VARCHAR(30) NOT NULL,
	new_state VARCHAR(30) NOT NULL,
	payload JSONB NOT NULL,
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	location_id UUID NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(table_id, organization_id, location_id) REFERENCES dining_tables (id, organization_id, location_id),
	UNIQUE (location_id, revision),
	FOREIGN KEY(actor_id) REFERENCES identity.users (id)
)

;
CREATE INDEX event_location_order ON table_events (location_id, revision);
CREATE INDEX ix_table_events_location_id ON table_events (location_id);
CREATE INDEX ix_table_events_organization_id ON table_events (organization_id);

CREATE TABLE staff_tasks (
	table_id UUID NOT NULL,
	occupancy_session_id UUID NOT NULL,
	status VARCHAR(24) DEFAULT 'OPEN' NOT NULL,
	acknowledged_at TIMESTAMP WITH TIME ZONE,
	started_at TIMESTAMP WITH TIME ZONE,
	completed_at TIMESTAMP WITH TIME ZONE,
	resolution VARCHAR(80),
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	organization_id UUID NOT NULL,
	location_id UUID NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(table_id, organization_id, location_id) REFERENCES dining_tables (id, organization_id, location_id),
	UNIQUE (table_id, occupancy_session_id),
	CONSTRAINT task_status CHECK (status IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS','COMPLETED','CANCELLED'))
)

;
CREATE INDEX ix_staff_tasks_location_id ON staff_tasks (location_id);
CREATE INDEX ix_staff_tasks_organization_id ON staff_tasks (organization_id);
CREATE UNIQUE INDEX one_active_reset_task ON staff_tasks (table_id) WHERE status IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS');

CREATE TABLE action_receipts (
	actor_id UUID NOT NULL,
	location_id UUID NOT NULL,
	request_key UUID NOT NULL,
	table_id UUID NOT NULL,
	fingerprint VARCHAR(64) NOT NULL,
	result JSONB NOT NULL,
	organization_id UUID NOT NULL,
	PRIMARY KEY (actor_id, location_id, request_key),
	FOREIGN KEY(table_id, organization_id, location_id) REFERENCES dining_tables (id, organization_id, location_id),
	FOREIGN KEY(actor_id) REFERENCES identity.users (id)
)

;
CREATE INDEX ix_action_receipts_organization_id ON action_receipts (organization_id);
