-- Frozen additive Phase 6 DDL. No business row updates or deletes.

CREATE SCHEMA edge_private;

REVOKE ALL ON SCHEMA edge_private FROM PUBLIC;


CREATE TABLE edge_private.nonces (
	key_id UUID NOT NULL, 
	nonce VARCHAR(32) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (key_id, nonce)
)

;


CREATE TABLE edge_private.pairings (
	key_id UUID NOT NULL, 
	public_key VARCHAR(44) NOT NULL, 
	fingerprint VARCHAR(64) NOT NULL, 
	challenge VARCHAR(32) NOT NULL, 
	peer_hash VARCHAR(64) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	proved BOOLEAN DEFAULT 'false' NOT NULL, 
	device_id UUID, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (key_id), 
	UNIQUE (fingerprint)
)

;

CREATE INDEX ix_edge_private_pairings_peer_hash ON edge_private.pairings (peer_hash);


CREATE TABLE edge_devices (
	label VARCHAR(80) NOT NULL, 
	purpose VARCHAR(32) DEFAULT 'AI_SHADOW' NOT NULL, 
	status VARCHAR(12) DEFAULT 'ACTIVE' NOT NULL, 
	processing_enabled BOOLEAN DEFAULT 'false' NOT NULL, 
	revision INTEGER DEFAULT '1' NOT NULL, 
	stream_id UUID, 
	stream_cursor INTEGER DEFAULT '0' NOT NULL, 
	last_contact_at TIMESTAMP WITH TIME ZONE, 
	offline_published BOOLEAN DEFAULT 'false' NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	organization_id UUID NOT NULL, 
	location_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (id, organization_id, location_id), 
	FOREIGN KEY(location_id, organization_id) REFERENCES locations (id, organization_id), 
	CONSTRAINT edge_purpose CHECK (purpose IN ('AI_SHADOW','SYNTHETIC_WORKFLOW_TEST')), 
	CONSTRAINT edge_status CHECK (status IN ('ACTIVE','REVOKED'))
)

;

CREATE INDEX ix_edge_devices_location_id ON edge_devices (location_id);

CREATE INDEX ix_edge_devices_organization_id ON edge_devices (organization_id);


CREATE TABLE location_notifications (
	location_id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	device_id UUID NOT NULL, 
	kind VARCHAR(24) NOT NULL, 
	organization_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (location_id, revision), 
	FOREIGN KEY(location_id, organization_id) REFERENCES locations (id, organization_id)
)

;

CREATE INDEX ix_location_notifications_organization_id ON location_notifications (organization_id);


CREATE TABLE edge_assignments (
	device_id UUID NOT NULL, 
	camera_id UUID NOT NULL, 
	epoch UUID NOT NULL, 
	enabled BOOLEAN DEFAULT 'false' NOT NULL, 
	model_sha256 VARCHAR(64) NOT NULL, 
	profile_sha256 VARCHAR(64) NOT NULL, 
	profile_revision INTEGER NOT NULL, 
	policy_revision INTEGER DEFAULT '1' NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	organization_id UUID NOT NULL, 
	location_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (id, device_id, organization_id, location_id, camera_id), 
	FOREIGN KEY(device_id, organization_id, location_id) REFERENCES edge_devices (id, organization_id, location_id), 
	FOREIGN KEY(camera_id, organization_id, location_id) REFERENCES cameras (id, organization_id, location_id)
)

;

CREATE INDEX ix_edge_assignments_device_id ON edge_assignments (device_id);

CREATE INDEX ix_edge_assignments_location_id ON edge_assignments (location_id);

CREATE INDEX ix_edge_assignments_organization_id ON edge_assignments (organization_id);

CREATE UNIQUE INDEX one_active_edge_camera ON edge_assignments (camera_id) WHERE enabled;


CREATE TABLE edge_audits (
	device_id UUID NOT NULL, 
	action VARCHAR(40) NOT NULL, 
	event_id UUID, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	organization_id UUID NOT NULL, 
	location_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(device_id, organization_id, location_id) REFERENCES edge_devices (id, organization_id, location_id)
)

;

CREATE INDEX ix_edge_audits_location_id ON edge_audits (location_id);

CREATE INDEX ix_edge_audits_organization_id ON edge_audits (organization_id);


CREATE TABLE edge_health (
	device_id UUID NOT NULL, 
	measured_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	metrics JSONB NOT NULL, 
	organization_id UUID NOT NULL, 
	location_id UUID NOT NULL, 
	PRIMARY KEY (device_id), 
	FOREIGN KEY(device_id, organization_id, location_id) REFERENCES edge_devices (id, organization_id, location_id)
)

;

CREATE INDEX ix_edge_health_location_id ON edge_health (location_id);

CREATE INDEX ix_edge_health_organization_id ON edge_health (organization_id);


CREATE TABLE edge_keys (
	device_id UUID NOT NULL, 
	public_key VARCHAR(44) NOT NULL, 
	fingerprint VARCHAR(64) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	revoked BOOLEAN DEFAULT 'false' NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	organization_id UUID NOT NULL, 
	location_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(device_id, organization_id, location_id) REFERENCES edge_devices (id, organization_id, location_id), 
	UNIQUE (fingerprint)
)

;

CREATE INDEX ix_edge_keys_device_id ON edge_keys (device_id);

CREATE INDEX ix_edge_keys_location_id ON edge_keys (location_id);

CREATE INDEX ix_edge_keys_organization_id ON edge_keys (organization_id);


CREATE TABLE edge_receipts (
	event_id UUID NOT NULL, 
	device_id UUID NOT NULL, 
	stream_id UUID NOT NULL, 
	sequence INTEGER NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	payload JSONB NOT NULL, 
	disposition VARCHAR(12) DEFAULT 'pending' NOT NULL, 
	reason VARCHAR(24) DEFAULT 'PENDING_GAP' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	organization_id UUID NOT NULL, 
	location_id UUID NOT NULL, 
	PRIMARY KEY (event_id), 
	FOREIGN KEY(device_id, organization_id, location_id) REFERENCES edge_devices (id, organization_id, location_id), 
	UNIQUE (device_id, stream_id, sequence), 
	CONSTRAINT edge_disposition CHECK (disposition IN ('pending','shadow','fixture','history','rejected'))
)

;

CREATE INDEX ix_edge_receipts_device_id ON edge_receipts (device_id);

CREATE INDEX ix_edge_receipts_location_id ON edge_receipts (location_id);

CREATE INDEX ix_edge_receipts_organization_id ON edge_receipts (organization_id);


CREATE TABLE edge_bindings (
	assignment_id UUID NOT NULL, 
	device_id UUID NOT NULL, 
	camera_id UUID NOT NULL, 
	table_id UUID NOT NULL, 
	zone_revision INTEGER NOT NULL, 
	epoch UUID NOT NULL, 
	enabled BOOLEAN DEFAULT 'true' NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	organization_id UUID NOT NULL, 
	location_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (id, device_id, organization_id, location_id), 
	FOREIGN KEY(assignment_id, device_id, organization_id, location_id, camera_id) REFERENCES edge_assignments (id, device_id, organization_id, location_id, camera_id), 
	FOREIGN KEY(table_id, organization_id, location_id) REFERENCES dining_tables (id, organization_id, location_id)
)

;

CREATE INDEX ix_edge_bindings_device_id ON edge_bindings (device_id);

CREATE INDEX ix_edge_bindings_location_id ON edge_bindings (location_id);

CREATE INDEX ix_edge_bindings_organization_id ON edge_bindings (organization_id);

CREATE UNIQUE INDEX one_active_edge_table ON edge_bindings (table_id) WHERE enabled;


CREATE TABLE edge_shadows (
	binding_id UUID NOT NULL, 
	device_id UUID NOT NULL, 
	sequence INTEGER NOT NULL, 
	state VARCHAR(16) NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	reason VARCHAR(32) NOT NULL, 
	organization_id UUID NOT NULL, 
	location_id UUID NOT NULL, 
	PRIMARY KEY (binding_id), 
	FOREIGN KEY(binding_id, device_id, organization_id, location_id) REFERENCES edge_bindings (id, device_id, organization_id, location_id)
)

;

CREATE INDEX ix_edge_shadows_location_id ON edge_shadows (location_id);

CREATE INDEX ix_edge_shadows_organization_id ON edge_shadows (organization_id);
