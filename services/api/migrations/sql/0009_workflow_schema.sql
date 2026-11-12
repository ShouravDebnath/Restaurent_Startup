-- Additive Phase 7 tables; existing rows are not rewritten or deleted.

ALTER TABLE public.edge_receipts ADD CONSTRAINT receipt_scope UNIQUE(event_id,organization_id,location_id);

ALTER TABLE public.staff_tasks ADD CONSTRAINT task_scope UNIQUE(id,organization_id,location_id);

ALTER TABLE public.table_events ADD CONSTRAINT event_scope UNIQUE(id,organization_id,location_id);


CREATE TABLE workflow_policies (
	location_id UUID NOT NULL,
	mode VARCHAR(24) DEFAULT 'OFF' NOT NULL,
	revision INTEGER NOT NULL,
	enabled_since TIMESTAMP WITH TIME ZONE NOT NULL,
	rules JSONB NOT NULL,
	rules_sha256 VARCHAR(64) NOT NULL,
	bindings JSONB NOT NULL,
	organization_id UUID NOT NULL,
	PRIMARY KEY (location_id),
	FOREIGN KEY(location_id, organization_id) REFERENCES locations (id, organization_id),
	CONSTRAINT workflow_mode CHECK (mode IN ('OFF','ASSISTED_REVIEW')),
	CONSTRAINT workflow_policy_revision CHECK (revision > 0)
);

CREATE INDEX ix_workflow_policies_organization_id ON workflow_policies (organization_id);


CREATE TABLE workflow_policy_history (
	actor_id UUID NOT NULL,
	revision INTEGER NOT NULL,
	snapshot JSONB NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	organization_id UUID NOT NULL,
	location_id UUID NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(location_id, organization_id) REFERENCES locations (id, organization_id),
	UNIQUE (location_id, revision),
	FOREIGN KEY(actor_id) REFERENCES identity.users (id)
);

CREATE INDEX ix_workflow_policy_history_location_id ON workflow_policy_history (location_id);

CREATE INDEX ix_workflow_policy_history_organization_id ON workflow_policy_history (organization_id);


CREATE TABLE workflow_evidence (
	receipt_id UUID NOT NULL,
	table_id UUID NOT NULL,
	device_id UUID NOT NULL,
	binding_id UUID NOT NULL,
	source_generation UUID NOT NULL,
	policy_revision INTEGER NOT NULL,
	manual_revision INTEGER NOT NULL,
	observed_at TIMESTAMP WITH TIME ZONE NOT NULL,
	valid_until TIMESTAMP WITH TIME ZONE NOT NULL,
	kind VARCHAR(12) NOT NULL,
	qualified BOOLEAN NOT NULL,
	reason VARCHAR(32) NOT NULL,
	summary JSONB NOT NULL,
	organization_id UUID NOT NULL,
	location_id UUID NOT NULL,
	PRIMARY KEY (receipt_id),
	UNIQUE (receipt_id, organization_id, location_id),
	FOREIGN KEY(receipt_id, organization_id, location_id) REFERENCES edge_receipts (event_id, organization_id, location_id),
	FOREIGN KEY(table_id, organization_id, location_id) REFERENCES dining_tables (id, organization_id, location_id),
	FOREIGN KEY(binding_id, device_id, organization_id, location_id) REFERENCES edge_bindings (id, device_id, organization_id, location_id),
	CONSTRAINT workflow_evidence_kind CHECK (kind IN ('POSITIVE','VACANT','UNCERTAIN')),
	CONSTRAINT workflow_evidence_interval CHECK (valid_until >= observed_at)
);

CREATE INDEX ix_workflow_evidence_location_id ON workflow_evidence (location_id);

CREATE INDEX ix_workflow_evidence_organization_id ON workflow_evidence (organization_id);

CREATE INDEX workflow_evidence_table_time ON workflow_evidence (table_id, observed_at);


CREATE TABLE workflow_sessions (
	table_id UUID NOT NULL,
	device_id UUID NOT NULL,
	binding_id UUID NOT NULL,
	source_generation UUID NOT NULL,
	source_episode UUID NOT NULL,
	arrival_receipt_id UUID NOT NULL,
	arrived_at TIMESTAMP WITH TIME ZONE NOT NULL,
	departed_at TIMESTAMP WITH TIME ZONE,
	ready_at TIMESTAMP WITH TIME ZONE,
	status VARCHAR(16) DEFAULT 'OPEN' NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	organization_id UUID NOT NULL,
	location_id UUID NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (id, organization_id, location_id),
	UNIQUE (binding_id, source_generation, source_episode),
	FOREIGN KEY(table_id, organization_id, location_id) REFERENCES dining_tables (id, organization_id, location_id),
	FOREIGN KEY(binding_id, device_id, organization_id, location_id) REFERENCES edge_bindings (id, device_id, organization_id, location_id),
	FOREIGN KEY(arrival_receipt_id, organization_id, location_id) REFERENCES edge_receipts (event_id, organization_id, location_id),
	CONSTRAINT workflow_session_status CHECK (status IN ('OPEN','VACATED','COMPLETE','INVALIDATED'))
);

CREATE INDEX ix_workflow_sessions_location_id ON workflow_sessions (location_id);

CREATE INDEX ix_workflow_sessions_organization_id ON workflow_sessions (organization_id);

CREATE INDEX workflow_session_table_time ON workflow_sessions (table_id, arrived_at);


CREATE TABLE workflow_suggestions (
	table_id UUID NOT NULL,
	device_id UUID NOT NULL,
	binding_id UUID NOT NULL,
	source_generation UUID NOT NULL,
	source_episode UUID NOT NULL,
	receipt_id UUID NOT NULL,
	latest_receipt_id UUID NOT NULL,
	session_id UUID,
	action VARCHAR(12) NOT NULL,
	status VARCHAR(16) DEFAULT 'PENDING' NOT NULL,
	revision INTEGER DEFAULT '1' NOT NULL,
	table_revision INTEGER NOT NULL,
	policy_revision INTEGER NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	organization_id UUID NOT NULL,
	location_id UUID NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (id, organization_id, location_id),
	FOREIGN KEY(table_id, organization_id, location_id) REFERENCES dining_tables (id, organization_id, location_id),
	FOREIGN KEY(receipt_id, organization_id, location_id) REFERENCES edge_receipts (event_id, organization_id, location_id),
	FOREIGN KEY(latest_receipt_id, organization_id, location_id) REFERENCES workflow_evidence (receipt_id, organization_id, location_id),
	FOREIGN KEY(session_id, organization_id, location_id) REFERENCES workflow_sessions (id, organization_id, location_id),
	FOREIGN KEY(binding_id, device_id, organization_id, location_id) REFERENCES edge_bindings (id, device_id, organization_id, location_id),
	UNIQUE (receipt_id),
	CONSTRAINT workflow_suggestion_action CHECK (action IN ('ARRIVAL','DEPARTURE')),
	CONSTRAINT workflow_suggestion_status CHECK (status IN ('PENDING','ACCEPTED','DISMISSED','SUPERSEDED'))
);

CREATE INDEX ix_workflow_suggestions_location_id ON workflow_suggestions (location_id);

CREATE INDEX ix_workflow_suggestions_organization_id ON workflow_suggestions (organization_id);

CREATE UNIQUE INDEX workflow_pending_suggestion ON workflow_suggestions (table_id, action) WHERE status='PENDING';


CREATE TABLE workflow_task_attempts (
	task_id UUID NOT NULL,
	session_id UUID NOT NULL,
	number INTEGER NOT NULL,
	pending_since TIMESTAMP WITH TIME ZONE NOT NULL,
	acknowledged_at TIMESTAMP WITH TIME ZONE,
	started_at TIMESTAMP WITH TIME ZONE,
	completed_at TIMESTAMP WITH TIME ZONE,
	cancelled_at TIMESTAMP WITH TIME ZONE,
	status VARCHAR(16) NOT NULL,
	resolution VARCHAR(80),
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	location_id UUID NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (id, organization_id, location_id),
	UNIQUE (task_id, number),
	FOREIGN KEY(task_id, organization_id, location_id) REFERENCES staff_tasks (id, organization_id, location_id),
	FOREIGN KEY(session_id, organization_id, location_id) REFERENCES workflow_sessions (id, organization_id, location_id),
	CONSTRAINT workflow_attempt_status CHECK (status IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS','COMPLETED','CANCELLED'))
);

CREATE INDEX ix_workflow_task_attempts_location_id ON workflow_task_attempts (location_id);

CREATE INDEX ix_workflow_task_attempts_organization_id ON workflow_task_attempts (organization_id);

CREATE UNIQUE INDEX workflow_current_attempt ON workflow_task_attempts (task_id) WHERE status IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS');


CREATE TABLE workflow_decisions (
	actor_id UUID NOT NULL,
	table_id UUID,
	suggestion_id UUID,
	action VARCHAR(32) NOT NULL,
	request_key UUID NOT NULL,
	fingerprint VARCHAR(64) NOT NULL,
	reason VARCHAR(32) NOT NULL,
	result JSONB NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	organization_id UUID NOT NULL,
	location_id UUID NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (actor_id, location_id, request_key),
	FOREIGN KEY(location_id, organization_id) REFERENCES locations (id, organization_id),
	FOREIGN KEY(table_id, organization_id, location_id) REFERENCES dining_tables (id, organization_id, location_id),
	FOREIGN KEY(suggestion_id, organization_id, location_id) REFERENCES workflow_suggestions (id, organization_id, location_id),
	FOREIGN KEY(actor_id) REFERENCES identity.users (id)
);

CREATE INDEX ix_workflow_decisions_location_id ON workflow_decisions (location_id);

CREATE INDEX ix_workflow_decisions_organization_id ON workflow_decisions (organization_id);


CREATE TABLE workflow_journal (
	event_id UUID NOT NULL,
	table_id UUID NOT NULL,
	session_id UUID,
	attempt_id UUID,
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
	basis VARCHAR(24) NOT NULL,
	organization_id UUID NOT NULL,
	location_id UUID NOT NULL,
	PRIMARY KEY (event_id),
	FOREIGN KEY(event_id, organization_id, location_id) REFERENCES table_events (id, organization_id, location_id),
	FOREIGN KEY(table_id, organization_id, location_id) REFERENCES dining_tables (id, organization_id, location_id),
	FOREIGN KEY(session_id, organization_id, location_id) REFERENCES workflow_sessions (id, organization_id, location_id),
	FOREIGN KEY(attempt_id, organization_id, location_id) REFERENCES workflow_task_attempts (id, organization_id, location_id),
	CONSTRAINT workflow_journal_basis CHECK (basis IN ('CONFIRMED_WORKFLOW','DEMO','LEGACY'))
);

CREATE INDEX ix_workflow_journal_location_id ON workflow_journal (location_id);

CREATE INDEX ix_workflow_journal_organization_id ON workflow_journal (organization_id);

CREATE INDEX workflow_journal_location_time ON workflow_journal (location_id, occurred_at);



CREATE TABLE workflow_quality_boundaries (
	location_id UUID NOT NULL,
	revision INTEGER NOT NULL,
	device_id UUID NOT NULL,
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
	reason VARCHAR(24) NOT NULL,
	organization_id UUID NOT NULL,
	PRIMARY KEY (location_id, revision),
	FOREIGN KEY(location_id, revision) REFERENCES location_notifications (location_id, revision),
	FOREIGN KEY(device_id, organization_id, location_id) REFERENCES edge_devices (id, organization_id, location_id),
	CONSTRAINT workflow_boundary_reason CHECK (reason IN ('OFFLINE','DEGRADED','CONFIG_CHANGED','POLICY_CHANGED'))
)

;

CREATE INDEX ix_workflow_quality_boundaries_organization_id ON workflow_quality_boundaries (organization_id);

CREATE INDEX workflow_boundary_device_time ON workflow_quality_boundaries (device_id, occurred_at);
