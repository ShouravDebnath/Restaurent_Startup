"""Independent, hand-calculated synthetic ground truth; no AI accuracy claims."""

import csv
import io
from datetime import UTC, date, datetime, timedelta

import pytest

from restaurant_api.analytics_domain import (
    buckets,
    calculate,
    csv_bytes,
    report_range,
    spreadsheet_text,
)

DAY = date(2026, 11, 11)
MID = datetime(2026, 11, 11, tzinfo=UTC)


def snapshot():
    def at(minutes):
        return (MID + timedelta(minutes=minutes)).isoformat()

    events = []
    for i, (minute, state) in enumerate(
        [
            (0, "AVAILABLE"),
            (60, "OCCUPIED"),
            (120, "RESET_PENDING"),
            (130, "CLEANING"),
            (140, "AVAILABLE"),
        ]
    ):
        events.append(
            {
                "table_id": "one",
                "occurred_at": at(minute),
                "revision": i + 1,
                "new_state": state,
                "basis": "DEMO",
                "payload": {"table_revision": i + 1},
            }
        )
    return {
        "as_of": at(1440),
        "synthetic": True,
        "cursor": "location:5",
        "tables": [{"id": "one", "label": "Table 1", "created_at": at(-1440)}],
        "events": events,
        "sessions": [
            {
                "id": "session",
                "table_id": "one",
                "arrived_at": at(60),
                "departed_at": at(120),
                "ready_at": at(140),
                "status": "COMPLETE",
            }
        ],
        "attempts": [
            {
                "session_id": "session",
                "pending_since": at(120),
                "started_at": at(130),
                "completed_at": at(140),
                "cancelled_at": None,
                "status": "COMPLETED",
                "resolution": "staff_confirmed_ready",
            }
        ],
        "evidence": [],
        "corrections": [],
        "boundaries": [],
    }


def report(data=None, **kwargs):
    return calculate(
        data or snapshot(), DAY, DAY + timedelta(days=1), "UTC", basis="DEMO", **kwargs
    )


def test_hand_calculated_state_session_and_reset_metrics():
    result = report()
    row = result["rows"][0]
    summary = result["summary"]
    assert row["state_seconds"] == {
        "UNKNOWN": 0,
        "AVAILABLE": 81600,
        "OCCUPIED": 3600,
        "RESET_PENDING": 600,
        "CLEANING": 600,
        "OUT_OF_SERVICE": 0,
    }
    assert sum(row["state_seconds"].values()) == row["configured_seconds"] == 86400
    assert (
        summary["average_occupied_seconds"] == 3600 and summary["completed_occupied_sessions"] == 1
    )
    assert (
        summary["average_wait_to_clean_seconds"] == 600
        and summary["average_cleaning_seconds"] == 600
    )
    assert summary["average_time_to_ready_seconds"] == 1200 and summary["completed_resets"] == 1
    assert row["known_evidence_seconds"] == 0 and row["evidence_coverage"] == 0
    assert row["estimated_occupied_fraction"] is None


def test_hourly_totals_equal_daily_and_ack_does_not_reset_state_time():
    data = snapshot()
    data["events"].append(
        {
            "table_id": "one",
            "occurred_at": (MID + timedelta(minutes=125)).isoformat(),
            "revision": 20,
            "new_state": "RESET_PENDING",
            "basis": "DEMO",
            "payload": {},
        }
    )
    hourly = report(data, group="hour")
    daily = report(data)
    for state in daily["rows"][0]["state_seconds"]:
        assert (
            sum(r["state_seconds"][state] for r in hourly["rows"])
            == daily["rows"][0]["state_seconds"][state]
        )
    assert daily["summary"]["average_time_to_ready_seconds"] == 1200


def test_predecessor_carries_state_but_missing_history_is_unknown():
    data = snapshot()
    data["events"] = [
        {
            "table_id": "one",
            "occurred_at": (MID - timedelta(minutes=10)).isoformat(),
            "revision": 1,
            "new_state": "OCCUPIED",
            "basis": "DEMO",
            "payload": {},
        }
    ]
    assert report(data)["rows"][0]["occupied_seconds"] == 86400
    data["events"] = []
    result = report(data)
    assert result["rows"][0]["state_seconds"]["UNKNOWN"] == 86400
    assert result["rows"][0]["occupied_seconds"] == 0
    assert result["rows"][0]["recorded_occupied_fraction"] is None


def test_legacy_and_synthetic_do_not_become_confirmed_production_metrics():
    data = snapshot()
    result = calculate(data, DAY, DAY + timedelta(days=1), "UTC", basis="CONFIRMED_WORKFLOW")
    assert result["rows"][0]["state_seconds"]["UNKNOWN"] == 86400
    assert result["summary"]["completed_resets"] == 0
    for event in data["events"]:
        event["basis"] = "LEGACY"
    assert report(data)["rows"][0]["occupied_seconds"] == 0


def test_only_configured_time_before_cutoff_counts_and_empty_locations_are_valid():
    data = snapshot()
    data["tables"][0]["created_at"] = (MID + timedelta(hours=3)).isoformat()
    data["as_of"] = (MID + timedelta(hours=4)).isoformat()
    result = report(data)
    assert result["rows"][0]["configured_seconds"] == 3600
    data["tables"] = []
    result = report(data)
    assert result["rows"] == []
    assert len(list(csv.DictReader(io.StringIO(csv_bytes(result).decode("utf-8-sig"))))) == 1


def test_missing_timestamps_cancelled_and_open_tasks_do_not_fabricate_completion():
    data = snapshot()
    data["attempts"][0]["started_at"] = None
    result = report(data)
    assert (
        result["summary"]["completed_resets"] == 0 and result["summary"]["excluded_attempts"] == 1
    )
    data["attempts"][0].update(
        status="CANCELLED", cancelled_at=(MID + timedelta(hours=3)).isoformat()
    )
    assert report(data)["summary"]["completed_resets"] == 0
    data["attempts"][0].update(status="OPEN", completed_at=None, cancelled_at=None)
    result = report(data)
    assert result["summary"]["open_reset_attempts"] == 1
    assert result["summary"]["oldest_open_reset_seconds"] == 22 * 3600
    assert result["summary"]["average_time_to_ready_seconds"] is None


def test_cross_boundary_average_uses_full_valid_session_but_time_totals_clip():
    data = snapshot()
    session = data["sessions"][0]
    session["arrived_at"] = (MID - timedelta(hours=1)).isoformat()
    data["events"][0].update(new_state="OCCUPIED")
    result = report(data)
    assert result["summary"]["average_occupied_seconds"] == 3 * 3600
    assert result["summary"]["cross_boundary_sessions"] == 1
    assert result["rows"][0]["occupied_seconds"] == 2 * 3600


def test_false_departure_attempt_is_corrected_without_erasing_history():
    data = snapshot()
    data["attempts"][0].update(
        status="CANCELLED",
        resolution="correction",
        completed_at=None,
        cancelled_at=(MID + timedelta(minutes=140)).isoformat(),
    )
    data["sessions"][0].update(status="OPEN", departed_at=None, ready_at=None)
    data["events"][-1].update(new_state="OCCUPIED")
    result = report(data)
    assert (
        result["summary"]["completed_resets"] == 0 and result["summary"]["cancelled_attempts"] == 1
    )
    assert result["summary"]["corrections_applied"] == 1
    assert result["rows"][0]["state_seconds"]["RESET_PENDING"] == 0
    assert result["rows"][0]["state_seconds"]["CLEANING"] == 0
    assert data["attempts"][0]["pending_since"] == snapshot()["attempts"][0]["pending_since"]


def test_wrong_arrival_becomes_unknown_in_corrected_report():
    data = snapshot()
    data["sessions"][0]["status"] = "INVALIDATED"
    data["corrections"] = [
        {
            "event_type": "workflow.correct_arrival",
            "occurred_at": (MID + timedelta(hours=2)).isoformat(),
            "payload": {"corrected_session_id": "session"},
        }
    ]
    result = report(data)
    assert result["rows"][0]["occupied_seconds"] == 0
    assert result["summary"]["completed_occupied_sessions"] == 0


def test_coverage_expiry_unknown_and_health_boundaries_are_not_vacancy():
    data = snapshot()
    data["events"] = []

    def sample(seconds, kind="POSITIVE", qualified=True):
        return {
            "table_id": "one",
            "device_id": "device",
            "observed_at": (MID + timedelta(seconds=seconds)).isoformat(),
            "valid_until": (MID + timedelta(seconds=seconds + 15)).isoformat(),
            "sequence": seconds + 1,
            "kind": kind,
            "qualified": qualified,
            "manual_revision": 1,
        }

    data["evidence"] = [sample(0), sample(10, "VACANT"), sample(20, "UNCERTAIN", False), sample(50)]
    data["boundaries"] = [
        {"device_id": "device", "occurred_at": (MID + timedelta(seconds=55)).isoformat()}
    ]
    row = report(data)["rows"][0]
    assert row["known_evidence_seconds"] == 25
    assert row["estimated_occupied_seconds"] == 15
    assert row["estimated_occupied_fraction"] == 0.6
    assert row["state_seconds"]["AVAILABLE"] == 0


def test_manual_event_closes_old_evidence_and_out_of_service_excludes_denominator():
    data = snapshot()
    data["events"] = [
        {
            "table_id": "one",
            "occurred_at": MID.isoformat(),
            "revision": 1,
            "new_state": "OUT_OF_SERVICE",
            "basis": "DEMO",
            "payload": {},
        }
    ]
    data["evidence"] = [
        {
            "table_id": "one",
            "device_id": "device",
            "observed_at": MID.isoformat(),
            "valid_until": (MID + timedelta(seconds=15)).isoformat(),
            "sequence": 1,
            "kind": "VACANT",
            "qualified": True,
            "manual_revision": 1,
        }
    ]
    row = report(data)["rows"][0]
    assert (
        row["usable_seconds"] == 0
        and row["known_evidence_seconds"] == 0
        and row["evidence_coverage"] is None
    )
    estimate = calculate(data, DAY, DAY + timedelta(days=1), "UTC", basis="ESTIMATED_EVIDENCE")[
        "rows"
    ][0]
    assert estimate["usable_seconds"] == 0 and estimate["state_seconds"] is None


@pytest.mark.parametrize("day,hours", [(date(2026, 3, 8), 23), (date(2026, 11, 1), 25)])
def test_new_york_real_dst_hours_and_distinct_repeated_hour(day, hours):
    result = buckets(day, day + timedelta(days=1), "America/New_York", "hour")
    assert len(result) == hours
    assert sum((b - a).total_seconds() for a, b, _ in result) == hours * 3600
    if hours == 25:
        repeated = [label for _, _, label in result if "T01:00" in label]
        assert len(repeated) == 2 and repeated[0] != repeated[1]


@pytest.mark.parametrize("zone", ["Asia/Dhaka", "Asia/Kolkata", "Asia/Kathmandu"])
def test_non_browser_time_zone_and_partial_hour_offsets(zone):
    start, end, _ = report_range(DAY, DAY + timedelta(days=1), zone)
    result = buckets(DAY, DAY + timedelta(days=1), zone, "hour")
    assert len(result) == 24 and (end - start).total_seconds() == 86400
    assert "T00:00" in result[0][2]


@pytest.mark.parametrize("day,hours", [(date(2026, 10, 4), 23.5), (date(2026, 4, 5), 24.5)])
def test_half_hour_dst_transition_has_real_partial_bucket(day, hours):
    result = buckets(day, day + timedelta(days=1), "Australia/Lord_Howe", "hour")
    assert sum((b - a).total_seconds() for a, b, _ in result) == hours * 3600
    assert any((b - a).total_seconds() == 1800 for a, b, _ in result)


@pytest.mark.parametrize(
    "start,end,zone",
    [
        (DAY, DAY, "UTC"),
        (DAY, DAY + timedelta(days=32), "UTC"),
        (DAY, DAY + timedelta(days=1), "invalid/zone"),
        (date(2011, 12, 30), date(2011, 12, 31), "Pacific/Apia"),
    ],
)
def test_invalid_ranges_and_missing_local_midnight_are_explicit(start, end, zone):
    with pytest.raises(ValueError):
        report_range(start, end, zone)


@pytest.mark.parametrize(
    "label",
    [
        "=1+1",
        " +SUM(A1:A2)",
        "\t@SUM(1)",
        "\r\n-1+2",
        "＝SUM(1)",
        "＋SUM(1)",
        '\u200b=HYPERLINK("x")',
    ],
)
def test_spreadsheet_formula_labels_have_visible_text_prefix(label):
    assert spreadsheet_text(label).startswith("Text: ")
    data = snapshot()
    data["tables"][0]["label"] = label
    result = report(data)
    parsed = list(csv.DictReader(io.StringIO(csv_bytes(result).decode("utf-8-sig"))))
    assert len(parsed) == 2 and parsed[1]["table_label"].startswith("Text: ")
    assert data["tables"][0]["label"] == label


def test_csv_quotes_delimiters_and_report_totals_are_not_repeated_per_bucket():
    data = snapshot()
    data["tables"][0]["label"] = 'Table "one", two\nthree'
    result = report(data, group="hour")
    rows = list(csv.DictReader(io.StringIO(csv_bytes(result).decode("utf-8-sig"))))
    assert len(rows) == 25 and rows[0]["row_type"] == "report_metadata"
    assert rows[0]["report_completed_resets"] == "1"
    assert all(r["report_completed_resets"] == "" for r in rows[1:])
    assert sum(float(r["occupied_seconds"]) for r in rows[1:]) == 3600
    assert all(r["table_label"] == 'Table "one", two three' for r in rows[1:])


def test_report_limits_reject_rather_than_truncate():
    data = snapshot()
    data["tables"] *= 101
    with pytest.raises(ValueError):
        report(data)
