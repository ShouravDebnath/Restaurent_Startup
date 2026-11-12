"""Fabricated observations/clocks verify summaries and durable compatibility."""

import copy
from datetime import UTC, datetime, timedelta

import pytest
from test_device_recovery import durable

from restaurant_edge.association import Observation
from restaurant_edge.evidence_protocol import EvidenceRules, rules_digest
from restaurant_edge.outbox import OutboxError


def negotiated(engine):
    engine.configuration.update(
        protocol_versions=[1, 2],
        workflow={
            "mode": "ASSISTED_REVIEW",
            "revision": 1,
            "bindings": [engine.configuration["bindings"][0]["id"]],
            "rules": EvidenceRules().model_dump(),
            "rules_sha256": rules_digest({}),
            "sessions": [],
        },
    )


def step(engine, kind, now, generation="one"):
    engine.frame_age_seconds = 0.3
    obs = Observation(
        kind,
        1 if kind == "POSITIVE" else None,
        0.9 if kind == "POSITIVE" else None,
        "HIGH",
        "SIMULATED",
        0.95 if kind == "POSITIVE" else None,
    )
    utc = (datetime(2026, 11, 11, tzinfo=UTC) + timedelta(seconds=now)).isoformat()
    engine.step({k: obs for k in engine.tables}, now, utc, generation, round(now * 100))


def test_v2_windows_and_one_transition_with_bounded_snapshot_cadence(tmp_path):
    engine, box = durable(tmp_path)
    negotiated(engine)
    try:
        for i in range(81):
            step(engine, "POSITIVE", i * 0.5)
        rows = [r for r, _ in box.pending()]
        assert all(r["version"] == 2 for r in rows)
        transitions = [r for r in rows if r["evidence_type"] == "transition"]
        assert len(transitions) == 1
        assert transitions[0]["evidence"]["covered_seconds"] == 10
        assert transitions[0]["evidence"]["detector_score"] == 0.9
        snapshots = [r for r in rows if r["evidence_type"] == "snapshot"]
        assert len(snapshots) == 5
        assert snapshots[-1]["evidence"]["window_seconds"] <= 29
        assert engine.tables[next(iter(engine.tables))].state == "OCCUPIED"
    finally:
        box.close()


def test_cleaning_keeps_operational_protection_but_has_fresh_vacancy_summaries(tmp_path):
    engine, box = durable(tmp_path)
    negotiated(engine)
    try:
        key = next(iter(engine.tables))
        engine.manual(
            [
                {
                    "id": key,
                    "operational_revision": 1,
                    "current_state": "CLEANING",
                    "state_source": "manual",
                    "state_since": datetime.now(UTC).isoformat(),
                }
            ],
            0,
            datetime.now(UTC).isoformat(),
        )
        for i in range(1, 71):
            step(engine, "VACANT", i * 0.5)
        assert engine.tables[key].state == "CLEANING"
        rows = [r for r, _ in box.pending()]
        assert any(
            r["evidence"]["kind"] == "VACANT" and r["evidence"]["covered_seconds"] >= 25
            for r in rows
        )
        assert all(r["evidence_type"] == "snapshot" for r in rows)
        assert all(r["evidence"]["detector_score"] is None for r in rows)
    finally:
        box.close()


def test_v1_bytes_survive_v2_negotiation_and_restart(tmp_path):
    engine, box = durable(tmp_path)
    try:
        for i in range(21):
            step(engine, "POSITIVE", i * 0.5)
        original = box.db.execute("SELECT event_id,payload,sha256 FROM events").fetchall()
        assert original
        negotiated(engine)
        step(engine, "POSITIVE", 10.5)
        assert (
            box.db.execute(
                "SELECT event_id,payload,sha256 FROM events ORDER BY sequence LIMIT 1"
            ).fetchall()
            == original[:1]
        )
        assert any(r["version"] == 2 for r, _ in box.pending())
        assert any(r["version"] == 1 for r, _ in box.pending())
    finally:
        box.close()


def test_queue_full_does_not_publish_windows_or_snapshot_cursor(tmp_path):
    engine, box = durable(tmp_path, max_pending=1)
    negotiated(engine)
    try:
        step(engine, "POSITIVE", 0)
        old = copy.deepcopy(engine.windows.samples)
        checkpoint = box.checkpoint()
        with pytest.raises(OutboxError):
            engine.invalidate("CAMERA_OFFLINE", 1, datetime.now(UTC).isoformat())
        assert engine.windows.samples == old and box.checkpoint() == checkpoint
        assert box.pending_count == 1
    finally:
        box.close()


def test_generation_gap_and_manual_revision_clear_old_window(tmp_path):
    engine, box = durable(tmp_path)
    negotiated(engine)
    try:
        for i in range(30):
            step(engine, "POSITIVE", i * 0.5)
        generation = engine.source_generation
        step(engine, "POSITIVE", 15, generation="two")
        assert engine.source_generation != generation
        assert max(len(r) for r in engine.windows.samples.values()) == 1
        key = next(iter(engine.tables))
        engine.manual(
            [
                {
                    "id": key,
                    "operational_revision": 10,
                    "current_state": "CLEANING",
                    "state_source": "manual",
                    "state_since": datetime.now(UTC).isoformat(),
                }
            ],
            16,
            datetime.now(UTC).isoformat(),
        )
        assert not engine.windows.samples
        step(engine, "VACANT", 17, generation="two")
        assert engine.windows.samples[key][0][0] == 17
    finally:
        box.close()


def test_only_same_generation_server_episode_can_be_reused(tmp_path):
    from uuid import uuid4

    engine, box = durable(tmp_path)
    negotiated(engine)
    try:
        key = next(iter(engine.tables))
        episode = str(uuid4())
        engine.configuration["workflow"]["sessions"] = [
            {
                "table_id": key,
                "source_generation": engine.source_generation,
                "source_episode": episode,
            }
        ]
        engine.manual(
            [
                {
                    "id": key,
                    "operational_revision": 2,
                    "current_state": "OCCUPIED",
                    "state_source": "manual",
                    "state_since": datetime.now(UTC).isoformat(),
                }
            ],
            0,
            datetime.now(UTC).isoformat(),
        )
        assert engine.tables[key].session_id == episode
        for i in range(1, 60):
            step(engine, "VACANT", i * 0.5)
        assert any(
            r["evidence_type"] == "transition"
            and r["occupancy_session_id"] == episode
            and r["state"] == "RESET_PENDING"
            for r, _ in box.pending()
        )
    finally:
        box.close()


def test_duplicate_native_frame_does_not_destroy_or_extend_evidence_window(tmp_path):
    engine, box = durable(tmp_path)
    negotiated(engine)
    try:
        for i in range(16):
            step(engine, "POSITIVE", i * 0.5)
        rows = copy.deepcopy(engine.windows.samples)
        pending = box.pending_count
        step(engine, "POSITIVE", 7.5)
        assert engine.windows.samples == rows and box.pending_count == pending
        for i in range(16, 21):
            step(engine, "POSITIVE", i * 0.5)
        assert any(
            r["evidence_type"] == "transition" and r["evidence"]["covered_seconds"] == 10
            for r, _ in box.pending()
        )
    finally:
        box.close()


def test_repeated_manual_poll_does_not_publish_false_unknown_between_frames(tmp_path):
    engine, box = durable(tmp_path)
    negotiated(engine)
    key = next(iter(engine.tables))
    row = {
        "id": key,
        "operational_revision": 1,
        "current_state": "UNKNOWN",
        "state_source": "manual",
        "state_since": datetime.now(UTC).isoformat(),
    }
    try:
        engine.manual([row], 0, datetime.now(UTC).isoformat())
        for i in range(1, 65):
            now = i * 0.5
            obs = Observation("VACANT", 0, None, "MEDIUM", "REVIEWED_VIEW_NO_PERSON")
            engine.frame_age_seconds = 0.3
            engine.step({key: obs}, now, datetime.now(UTC).isoformat(), "one", i)
            count = box.pending_count
            engine.manual([row], now + 0.1, datetime.now(UTC).isoformat())
            assert box.pending_count == count
        summaries = [r["evidence"] for r, _ in box.pending()]
        assert summaries[-1]["covered_seconds"] >= 25
        assert summaries[-1]["quality"] == "MEDIUM"
        assert summaries[-1]["detector_score"] is None
    finally:
        box.close()
