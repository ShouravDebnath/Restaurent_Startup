"""Actual pretrained CPU model, geometric synthetic MP4 and signed V2 transport.

No people footage, detection accuracy or occupancy accuracy is established here.
"""

import hashlib
import json
import os
import time
from pathlib import Path
from uuid import uuid4

import pytest
from restaurant_edge.analysis_config import AnalysisConfig, ConfigStore
from restaurant_edge.detectors.onnx_detector import ModelCatalog
from restaurant_edge.device_runner import DeviceRunner
from restaurant_edge.durable_engine import DurableEngine
from restaurant_edge.video_sources import synthetic_mp4
from sqlalchemy import text

from .test_edge_https import tls as tls_fixture
from .test_edge_transport import command, configure
from .test_edge_transport import edge as edge_fixture
from .test_edge_transport import edge_tenants as edge_tenants_fixture

edge = edge_fixture
edge_tenants = edge_tenants_fixture
tls = tls_fixture
ROOT = Path(__file__).resolve().parents[3]


def test_actual_model_v2_synthetic_evidence_never_creates_occupancy(edge, tls, monkeypatch):
    catalog = os.environ.get("RFDETR_TEST_CATALOG")
    if not catalog:
        pytest.skip("Use the already-approved private model catalog; never download in tests")
    artifact = ModelCatalog.load(catalog).get("rfdetr_nano")
    configure(edge)
    folder = ROOT / ".secrets/phase7-implementation" / ("native-" + uuid4().hex)
    folder.mkdir()
    config = AnalysisConfig.model_validate(
        {
            "organization_id": str(edge.org),
            "location_id": str(edge.loc),
            "camera_id": str(edge.camera),
            "model": "rfdetr_nano",
            "source_width": 640,
            "source_height": 360,
            "regions": [
                {
                    "table_id": str(edge.table),
                    "zone_id": str(uuid4()),
                    "zone_revision": 1,
                    "seating": [[0.1, 0.1], [0.8, 0.1], [0.8, 0.8], [0.1, 0.8]],
                    "visibility_reviewed": True,
                }
            ],
        }
    )
    saved = ConfigStore(folder / "profiles").save(
        config, 0, uuid4(), edge.suite.seed["accounts"]["a_owner"]["user_id"]
    )
    digest = hashlib.sha256(
        json.dumps(config.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()
    assert digest == saved["fingerprint"]
    assert (
        command(
            edge,
            action="assign",
            camera_id=str(edge.camera),
            table_id=str(edge.table),
            zone_revision=1,
            profile_revision=saved["revision"],
            profile_sha256=digest,
            model_sha256=artifact.sha256,
        ).status_code
        == 200
    )
    enabled = edge.clients["a_owner"].request(
        "PUT",
        f"/v1/locations/{edge.loc}/workflow-policy",
        json={
            "mode": "ASSISTED_REVIEW",
            "expected_revision": 0,
            "request_key": str(uuid4()),
            "bindings": [edge.binding["id"]],
            "rules": {},
        },
    )
    assert enabled.status_code == 200, enabled.text
    video = folder / "synthetic.mp4"
    synthetic_mp4(video, 75)
    # A separate stationary geometric fixture tests a complete vacancy window.
    # The original moving/counter fixture is retained: its changing text/shapes
    # can produce uncertain model outputs and must not be called reliable vacancy.
    import cv2

    capture = cv2.VideoCapture(str(video))
    ok, image = capture.read()
    capture.release()
    assert ok
    stationary = folder / "stationary-synthetic.mp4"
    writer = cv2.VideoWriter(str(stationary), cv2.VideoWriter_fourcc(*"mp4v"), 10, (640, 360))
    assert writer.isOpened()
    try:
        for _ in range(750):
            writer.write(image)
    finally:
        writer.release()
    sources = folder / "sources.json"
    sources.write_text(
        json.dumps(
            {
                "version": 1,
                "roots": [str(folder)],
                "sources": [
                    {
                        "reference": "phase7-synthetic",
                        "organization_id": str(edge.org),
                        "location_id": str(edge.loc),
                        "camera_id": str(edge.camera),
                        "kind": "mp4",
                        "synthetic": True,
                        "authorized": True,
                        "file": str(stationary),
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        "restaurant_edge.device_runner.load_identity", lambda _: ({"key_id": edge.kid}, edge.key)
    )
    settings = {
        "identity": "unused-fixture",
        "api": f"https://127.0.0.1:{tls.port}",
        "ca": tls.folder / "ca.pem",
        "profiles": folder / "profiles",
        "models": catalog,
        "sources": sources,
        "camera_id": str(edge.camera),
        "source_reference": "phase7-synthetic",
        "outbox": folder / "outbox.sqlite3",
    }
    with edge.suite.admin.connect() as db:
        before = db.scalar(
            text("SELECT to_jsonb(t) FROM dining_tables t WHERE id=:id"), {"id": edge.table}
        )
    # Allow model loading plus a complete 25-second evidence window and the
    # separate ten-second publication cadence; native safety timeouts stay intact.
    invalidations = []
    original = DurableEngine.invalidate

    def record_invalidation(engine, reason, now, utc):
        if engine.windows.samples and any(engine.windows.samples.values()):
            invalidations.append(
                {
                    "reason": reason,
                    "covered_samples": max(map(len, engine.windows.samples.values())),
                    "at": time.monotonic(),
                }
            )
        return original(engine, reason, now, utc)

    monkeypatch.setattr(DurableEngine, "invalidate", record_invalidation)
    result = DeviceRunner(settings).run(seconds=60)
    (folder / "diagnostics.json").write_text(
        json.dumps({"result": result, "invalidations": invalidations}, indent=2)
    )
    assert result["analysis_status"] == "RUNNING", result
    assert result["inference_ms"] > 0
    assert set(result["shadow_states"].values()) == {"UNKNOWN"}
    assert result["pending"] == 0
    with edge.suite.admin.connect() as db:
        assert (
            db.scalar(
                text("SELECT to_jsonb(t) FROM dining_tables t WHERE id=:id"), {"id": edge.table}
            )
            == before
        )
        summaries = db.execute(
            text("SELECT kind,qualified,summary FROM workflow_evidence WHERE table_id=:id"),
            {"id": edge.table},
        ).all()
        assert summaries
        assert any(row.kind == "VACANT" and row.qualified for row in summaries), summaries
        assert (
            db.scalar(
                text("SELECT count(*) FROM workflow_suggestions WHERE table_id=:id"),
                {"id": edge.table},
            )
            == 0
        )
        assert (
            db.scalar(
                text("SELECT count(*) FROM staff_tasks WHERE table_id=:id"), {"id": edge.table}
            )
            == 0
        )
    report = dict(
        result,
        actual_pretrained_model=True,
        synthetic_video=True,
        qualified_vacancy_evidence=True,
        evidence_records=len(summaries),
        canonical_table_preserved=True,
        real_person_accuracy=False,
        model_sha256=artifact.sha256,
    )
    (ROOT / ".secrets/phase7-implementation/native-result.json").write_text(
        json.dumps(report, indent=2)
    )
