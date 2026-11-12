"""Phase 7 opt-in evidence summaries; no video, detections, identities or URLs.

Mirrored byte-for-byte in API and edge packages. Version 1 stays frozen.
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Positive = Annotated[int, Field(strict=True, ge=1, le=2147483647)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, allow_inf_nan=False)


class EvidenceRules(Strict):
    entry_score: float = Field(default=0.6, ge=0.05, le=1)
    retention_score: float = Field(default=0.4, ge=0.05, le=1)
    arrival_seconds: float = Field(default=10, ge=2, le=120)
    departure_seconds: float = Field(default=25, ge=5, le=300)
    max_gap_seconds: float = Field(default=2, ge=0.5, le=3)
    result_max_age: float = Field(default=2, ge=0.5, le=5)
    border_margin: float = Field(default=0.015, ge=0, le=0.1)
    min_samples: int = Field(default=3, strict=True, ge=3, le=30)
    coverage_step_seconds: float = Field(default=1, ge=0.2, le=2)
    minimum_coverage: float = Field(default=0.8, ge=0.5, le=1)

    @model_validator(mode="after")
    def thresholds(self):
        if self.retention_score > self.entry_score:
            raise ValueError("Invalid threshold ordering")
        return self


def rules_digest(rules):
    rules = EvidenceRules.model_validate(rules).model_dump(mode="json")
    return hashlib.sha256(
        json.dumps(rules, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


class Evidence(Strict):
    kind: Literal["POSITIVE", "VACANT", "UNCERTAIN"]
    quality: Literal["HIGH", "MEDIUM", "LOW"]
    detector_score: float | None = Field(default=None, ge=0, le=1)
    association_score: float | None = Field(default=None, ge=0, le=1)
    sample_count: int = Field(strict=True, ge=0, le=10000)
    window_seconds: float = Field(ge=0, le=310)
    covered_seconds: float = Field(ge=0, le=310)
    max_gap_seconds: float = Field(ge=0, le=310)
    frame_age_seconds: float | None = Field(default=None, ge=0, le=3600)
    visibility_reviewed: bool = Field(strict=True)

    @model_validator(mode="after")
    def relationships(self):
        if self.covered_seconds > self.window_seconds + 0.000001:
            raise ValueError("Coverage exceeds window")
        if self.sample_count < 2 and (self.window_seconds or self.covered_seconds):
            raise ValueError("Duration requires multiple samples")
        if self.kind == "VACANT" and self.detector_score is not None:
            raise ValueError("Vacancy is not a person score")
        return self


class ObservationV2(Strict):
    version: Literal[2] = 2
    event_id: UUID
    device_id: UUID
    stream_id: UUID
    sequence: Positive
    organization_id: UUID
    location_id: UUID
    binding_id: UUID
    binding_epoch: UUID
    camera_id: UUID
    table_id: UUID
    occurred_at: datetime
    kind: Literal["shadow"] = "shadow"
    state: Literal[
        "UNKNOWN", "AVAILABLE", "OCCUPIED", "RESET_PENDING", "CLEANING", "OUT_OF_SERVICE"
    ]
    reason: Literal[
        "STABLE_PERSON",
        "STABLE_VACANCY",
        "NOT_OBSERVED",
        "OBSERVATION_GAP",
        "SOURCE_CHANGED",
        "CAMERA_OFFLINE",
        "CURRENT_HUMAN_STATE",
        "UNCERTAIN",
        "LEASE_EXPIRED",
    ]
    occupancy_session_id: UUID | None = None
    manual_revision: int = Field(strict=True, ge=0, le=2147483647)
    zone_revision: Positive
    profile_revision: Positive
    profile_sha256: Digest
    model_sha256: Digest
    policy_revision: Positive
    frame_sequence: int = Field(strict=True, ge=0, le=2147483647)
    source_generation: UUID
    evidence_type: Literal["transition", "snapshot"]
    workflow_revision: Positive
    rules_sha256: Digest
    evidence: Evidence

    @field_validator("version", mode="before")
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError("Integer version required")
        return value

    @field_validator("occurred_at")
    @classmethod
    def utc(cls, value):
        if value.tzinfo is None or value.utcoffset().total_seconds() != 0:
            raise ValueError("UTC timestamp required")
        return value.astimezone(UTC)


def compatible_batch(body, legacy):
    """Keep v1 canonical bytes/defaults. Malformed v2 cannot fall back to v1."""
    value = legacy.parse_json(body)
    if (
        not isinstance(value, dict)
        or set(value) != {"events"}
        or not isinstance(value["events"], list)
    ):
        raise ValueError("Invalid batch envelope")
    if not 1 <= len(value["events"]) <= legacy.MAX_EVENTS:
        raise ValueError("Invalid batch count")
    items, ids = [], set()
    for raw in value["events"]:
        if not isinstance(raw, dict):
            raise TypeError("Invalid event")
        is_v2 = type(raw.get("version")) is int and raw.get("version") == 2
        model = ObservationV2 if is_v2 else legacy.Observation
        if set(raw) - set(model.model_fields):
            raise ValueError("Unknown fields")
        try:
            event = model.model_validate(raw)
            identity = str(event.event_id)
            items.append(
                {
                    "event": event.model_dump(mode="json"),
                    "sha256": legacy.fingerprint(legacy.encode(event)),
                }
            )
        except ValueError:
            safe = legacy.OwnedEnvelope.model_validate(
                {k: raw[k] for k in legacy.OwnedEnvelope.model_fields if k in raw}
            )
            identity = str(safe.event_id)
            items.append(
                {
                    "event": dict(safe.model_dump(mode="json"), _rejected=True),
                    "sha256": legacy.fingerprint(legacy.encode(raw)),
                }
            )
        if identity in ids:
            raise ValueError("Duplicate event IDs")
        ids.add(identity)
    return items
