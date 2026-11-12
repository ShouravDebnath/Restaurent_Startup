"""Wire compatibility/security checks; constructed evidence is not AI accuracy."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from restaurant_api import edge_protocol as v1
from restaurant_api.evidence_protocol import (
    Evidence,
    EvidenceRules,
    ObservationV2,
    compatible_batch,
    rules_digest,
)


def event_v2():
    return dict(
        version=2,
        **{
            k: str(uuid4())
            for k in [
                "event_id",
                "device_id",
                "stream_id",
                "organization_id",
                "location_id",
                "binding_id",
                "binding_epoch",
                "camera_id",
                "table_id",
                "source_generation",
            ]
        },
        sequence=1,
        occurred_at=datetime.now(UTC).isoformat(),
        state="OCCUPIED",
        reason="STABLE_PERSON",
        manual_revision=0,
        zone_revision=1,
        profile_revision=1,
        profile_sha256="a" * 64,
        model_sha256="b" * 64,
        policy_revision=1,
        frame_sequence=1,
        evidence_type="transition",
        workflow_revision=1,
        rules_sha256=rules_digest({}),
        evidence={
            "kind": "POSITIVE",
            "quality": "HIGH",
            "detector_score": 0.8,
            "association_score": 0.95,
            "sample_count": 25,
            "window_seconds": 12,
            "covered_seconds": 12,
            "max_gap_seconds": 0.5,
            "frame_age_seconds": 0.4,
            "visibility_reviewed": True,
        },
    )


def test_contract_mirrors_and_v1_bytes():
    root = Path(__file__).resolve().parents[3]
    paths = [
        "packages/contracts/evidence_protocol.py",
        "services/api/src/restaurant_api/evidence_protocol.py",
        "services/edge-agent/src/restaurant_edge/evidence_protocol.py",
    ]
    assert len({(root / p).read_bytes() for p in paths}) == 1
    raw = event_v2()
    for key in ["evidence_type", "workflow_revision", "rules_sha256", "evidence"]:
        raw.pop(key)
    raw["version"] = 1
    body = v1.encode({"events": [raw]})
    assert compatible_batch(body, v1) == v1.batch_items(body)


@pytest.mark.parametrize(
    "change",
    [
        {"covered_seconds": 14},
        {"window_seconds": -1},
        {"sample_count": True},
        {"sample_count": 1},
        {"frame_age_seconds": float("nan")},
        {"detector_score": float("inf")},
        {"visibility_reviewed": 1},
        {"kind": "VACANT"},
        {"image": "private"},
        {"association_score": 1.1},
    ],
)
def test_invalid_evidence_is_rejected(change):
    raw = event_v2()["evidence"] | change
    with pytest.raises(ValidationError):
        Evidence.model_validate(raw)


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", True),
        ("kind", "fixture_arrive"),
        ("occurred_at", "2026-01-01T00:00:00"),
        ("workflow_revision", 0),
        ("rules_sha256", "unknown"),
        ("video", "private"),
        ("manual_revision", True),
    ],
)
def test_strict_v2_envelope(field, value):
    with pytest.raises(ValidationError):
        ObservationV2.model_validate(event_v2() | {field: value})


def test_v2_roundtrip_and_null_vacancy_score():
    event = ObservationV2.model_validate(event_v2())
    assert (
        compatible_batch(v1.encode({"events": [event.model_dump(mode="json")]}), v1)[0]["event"][
            "version"
        ]
        == 2
    )
    vacant = event_v2()["evidence"] | {
        "kind": "VACANT",
        "detector_score": None,
        "association_score": None,
    }
    assert Evidence.model_validate(vacant).detector_score is None
    assert rules_digest({}) == rules_digest(EvidenceRules().model_dump())


def test_invalid_supported_version_gets_safe_terminal_identity():
    raw = event_v2()
    raw.pop("evidence")
    item = compatible_batch(v1.encode({"events": [raw]}), v1)[0]
    assert item["event"]["_rejected"] is True
    assert "rules_sha256" not in item["event"]
    with pytest.raises(ValueError):
        compatible_batch(
            json.dumps({"events": [event_v2() | {"private_key": "never-allowed"}]}).encode(), v1
        )
