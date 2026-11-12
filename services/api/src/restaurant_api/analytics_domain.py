"""Deterministic UTC interval arithmetic. Recorded workflow is not AI accuracy."""

import csv
import io
import itertools
import unicodedata
from bisect import bisect_left, bisect_right
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from restaurant_api.analytics_scenarios import scenario_records

STATES = ("UNKNOWN", "AVAILABLE", "OCCUPIED", "RESET_PENDING", "CLEANING", "OUT_OF_SERVICE")
BASES = ("CONFIRMED_WORKFLOW", "DEMO", "LEGACY", "ESTIMATED_EVIDENCE")


def instant(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        raise ValueError("Stored instants require timezone information")
    return value.astimezone(UTC)


def local_boundary(day, zone):
    naive = datetime.combine(day, time.min)
    values = set()
    for fold in (0, 1):
        candidate = naive.replace(tzinfo=zone, fold=fold).astimezone(UTC)
        if candidate.astimezone(zone).replace(tzinfo=None) == naive:
            values.add(candidate)
    if len(values) != 1:
        raise ValueError(
            "This date has an ambiguous or missing local midnight; choose another boundary"
        )
    return values.pop()


def report_range(from_date, to_date, zone_name):
    if (
        not isinstance(from_date, date)
        or not isinstance(to_date, date)
        or not 1 <= (to_date - from_date).days <= 31
    ):
        raise ValueError("Choose 1 to 31 local days; the end date is exclusive")
    try:
        zone = ZoneInfo(zone_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Location time zone is unsupported") from None
    return local_boundary(from_date, zone), local_boundary(to_date, zone), zone


def buckets(from_date, to_date, zone_name, group):
    start, end, zone = report_range(from_date, to_date, zone_name)
    boundaries = {start, end}
    day = from_date
    while day < to_date:
        boundaries.add(local_boundary(day, zone))
        if group == "hour":
            for hour in range(24):
                naive = datetime.combine(day, time(hour))
                for fold in (0, 1):
                    value = naive.replace(tzinfo=zone, fold=fold).astimezone(UTC)
                    if value.astimezone(zone).replace(tzinfo=None) == naive:
                        boundaries.add(value)
        day += timedelta(days=1)
    if group == "hour":
        # Include partial-hour transitions too (for example Lord Howe's 30 minutes).
        probe = start
        while probe < end:
            following = min(end, probe + timedelta(minutes=15))
            if probe.astimezone(zone).utcoffset() != following.astimezone(zone).utcoffset():
                lo, hi = probe, following
                while (hi - lo).total_seconds() > 1:
                    mid = lo + timedelta(seconds=int((hi - lo).total_seconds() / 2))
                    if mid.astimezone(zone).utcoffset() == lo.astimezone(zone).utcoffset():
                        lo = mid
                    else:
                        hi = mid
                boundaries.add(hi)
            probe = following
    values = sorted(t for t in boundaries if start <= t <= end)
    return [(a, b, a.astimezone(zone).isoformat()) for a, b in itertools.pairwise(values)]


def overlap(a, b, start, end):
    return max(0.0, (min(b, end) - max(a, start)).total_seconds())


def average(values):
    return sum(values) / len(values) if values else None


def calculate(snapshot, from_date, to_date, zone_name, group="day", basis="CONFIRMED_WORKFLOW"):
    if basis not in BASES or group not in {"day", "hour"}:
        raise ValueError("Unsupported report grouping or basis")
    start, end, _zone = report_range(from_date, to_date, zone_name)
    as_of = min(end, instant(snapshot["as_of"]))
    spans = buckets(from_date, to_date, zone_name, group)
    tables = snapshot["tables"]
    if len(tables) > 100 or len(tables) * len(spans) > 20000:
        raise ValueError("Report is too large; select fewer tables, days or daily grouping")
    synthetic = snapshot["synthetic"]
    session_basis = "DEMO" if synthetic else "CONFIRMED_WORKFLOW"
    scenario_sessions, scenario_attempts = (
        scenario_records(snapshot) if basis == "DEMO" else ([], [])
    )
    sessions = [*snapshot["sessions"], *scenario_sessions] if basis == session_basis else []
    attempts = [*snapshot["attempts"], *scenario_attempts] if basis == session_basis else []
    session_map = {str(s["id"]): s for s in snapshot["sessions"]}
    corrections = []
    for a in snapshot["attempts"]:
        if (
            a["status"] == "CANCELLED"
            and a.get("resolution") == "correction"
            and a.get("cancelled_at")
        ):
            session = session_map.get(str(a["session_id"]))
            if session:
                corrections.append(
                    (
                        str(session["table_id"]),
                        instant(a["pending_since"]),
                        instant(a["cancelled_at"]),
                        "OCCUPIED",
                    )
                )
    for c in snapshot["corrections"]:
        if c["event_type"] == "workflow.correct_arrival":
            session = session_map.get(str(c["payload"].get("corrected_session_id")))
            if session:
                corrections.append(
                    (
                        str(session["table_id"]),
                        instant(session["arrived_at"]),
                        instant(c["occurred_at"]),
                        "UNKNOWN",
                    )
                )
    rows = []
    for table in tables:
        key = str(table["id"])
        created = instant(table["created_at"])
        history = sorted(
            (e for e in snapshot["events"] if str(e["table_id"]) == key),
            key=lambda e: (instant(e["occurred_at"]), e["revision"]),
        )
        intervals = []
        raw_intervals = []
        cursor = max(start, created)
        state = "UNKNOWN"
        raw_state = "UNKNOWN"
        for event in history:
            moment = instant(event["occurred_at"])
            if moment >= as_of:
                break
            if moment > cursor:
                intervals.append((cursor, moment, state))
                raw_intervals.append((cursor, moment, raw_state))
                cursor = moment
            state = event["new_state"] if event.get("basis", "LEGACY") == basis else "UNKNOWN"
            raw_state = event["new_state"]
        if cursor < as_of:
            intervals.append((cursor, as_of, state))
            raw_intervals.append((cursor, as_of, raw_state))
        adjusted = []
        changes = [c for c in corrections if c[0] == key and basis == session_basis]
        for a, b, state in intervals:
            points = sorted({a, b, *[t for _, c, d, _ in changes for t in (c, d) if a < t < b]})
            for left, right in itertools.pairwise(points):
                corrected = next((s for _, c, d, s in reversed(changes) if c <= left < d), state)
                adjusted.append((left, right, corrected))
        evidence = sorted(
            (e for e in snapshot["evidence"] if str(e["table_id"]) == key),
            key=lambda e: (instant(e["observed_at"]), e["sequence"]),
        )
        history_times = [instant(e["occurred_at"]) for e in history]
        source_boundaries = {}
        for boundary in snapshot["boundaries"]:
            source_boundaries.setdefault(str(boundary["device_id"]), []).append(
                instant(boundary["occurred_at"])
            )
        source_boundaries = {k: sorted(v) for k, v in source_boundaries.items()}
        known = []
        for i, event in enumerate(evidence):
            if not event["qualified"] or event["kind"] not in {"POSITIVE", "VACANT"}:
                continue
            a = instant(event["observed_at"])
            b = min(as_of, instant(event["valid_until"]))
            if i + 1 < len(evidence):
                b = min(b, instant(evidence[i + 1]["observed_at"]))
            boundaries = source_boundaries.get(str(event["device_id"]), [])
            index = bisect_left(boundaries, a)
            if index < len(boundaries):
                b = min(b, boundaries[index])
            index = bisect_right(history_times, a)
            if index < len(history_times):
                b = min(b, history_times[index])
            a = max(a, created)
            if b > a:
                known.append((a, b, event["kind"]))
        for a, b, label in spans:
            configured = overlap(created, as_of, a, b) if as_of >= created else 0.0
            durations = {
                s: sum(overlap(c, d, a, b) for c, d, state in adjusted if state == s)
                for s in STATES
            }
            unavailable = sum(
                overlap(c, d, a, b) for c, d, state in raw_intervals if state == "OUT_OF_SERVICE"
            )
            durations["UNKNOWN"] = max(
                0.0, durations["UNKNOWN"] - (unavailable - durations["OUT_OF_SERVICE"])
            )
            durations["OUT_OF_SERVICE"] = unavailable
            usable = max(0.0, configured - unavailable)
            good = sum(overlap(c, d, a, b) for c, d, kind in known)
            positive = sum(overlap(c, d, a, b) for c, d, kind in known if kind == "POSITIVE")
            # Exclude out-of-service time from both coverage numerator and denominator.
            for c, d, state in raw_intervals:
                if state == "OUT_OF_SERVICE":
                    for e, f, kind in known:
                        cut = overlap(max(c, e), min(d, f), a, b) if min(d, f) > max(c, e) else 0.0
                        good -= cut
                        if kind == "POSITIVE":
                            positive -= cut
            good = max(0.0, good)
            positive = max(0.0, positive)
            recorded_known = max(0.0, usable - durations["UNKNOWN"])
            rows.append(
                {
                    "table_id": key,
                    "table_label": table["label"],
                    "bucket_start": a.isoformat(),
                    "bucket_end": b.isoformat(),
                    "local_label": label,
                    "configured_seconds": configured,
                    "usable_seconds": usable,
                    "state_seconds": None if basis == "ESTIMATED_EVIDENCE" else durations,
                    "occupied_seconds": None
                    if basis == "ESTIMATED_EVIDENCE"
                    else durations["OCCUPIED"],
                    "recorded_occupied_fraction": durations["OCCUPIED"] / recorded_known
                    if recorded_known and basis != "ESTIMATED_EVIDENCE"
                    else None,
                    "workflow_coverage": recorded_known / usable
                    if usable and basis != "ESTIMATED_EVIDENCE"
                    else None,
                    "known_evidence_seconds": good,
                    "unknown_evidence_seconds": max(0.0, usable - good),
                    "evidence_coverage": good / usable if usable else None,
                    "estimated_occupied_seconds": positive,
                    "estimated_occupied_fraction": positive / good if good else None,
                }
            )
    occupied = []
    excluded_sessions = 0
    for s in sessions:
        if (
            s.get("departed_at")
            and start <= instant(s["departed_at"]) < as_of
            and s["status"] in {"VACATED", "COMPLETE"}
        ):
            duration = (instant(s["departed_at"]) - instant(s["arrived_at"])).total_seconds()
            if duration >= 0:
                occupied.append(duration)
            else:
                excluded_sessions += 1
    resets = []
    waits = []
    cleaning = []
    excluded_attempts = 0
    for a in attempts:
        if (
            a["status"] != "COMPLETED"
            or not a.get("completed_at")
            or not start <= instant(a["completed_at"]) < as_of
        ):
            continue
        if not a.get("started_at") or not (
            instant(a["pending_since"]) <= instant(a["started_at"]) <= instant(a["completed_at"])
        ):
            excluded_attempts += 1
            continue
        resets.append((instant(a["completed_at"]) - instant(a["pending_since"])).total_seconds())
        waits.append((instant(a["started_at"]) - instant(a["pending_since"])).total_seconds())
        cleaning.append((instant(a["completed_at"]) - instant(a["started_at"])).total_seconds())
    open_attempts = [
        a
        for a in attempts
        if instant(a["pending_since"]) < as_of
        and (not a.get("completed_at") or instant(a["completed_at"]) >= as_of)
        and (not a.get("cancelled_at") or instant(a["cancelled_at"]) >= as_of)
        and not (a["status"] == "CANCELLED" and a.get("resolution") == "correction")
    ]
    return {
        "from_date": from_date.isoformat(),
        "to_date_exclusive": to_date.isoformat(),
        "time_zone": zone_name,
        "group": group,
        "basis": basis,
        "estimate_basis": "ESTIMATED_EVIDENCE",
        "synthetic": synthetic,
        "as_of": instant(snapshot["as_of"]).isoformat(),
        "calculation_version": 2,
        "cursor": snapshot["cursor"],
        "rows": rows,
        "summary": {
            "average_occupied_seconds": average(occupied),
            "completed_occupied_sessions": len(occupied),
            "completed_resets": len(resets),
            "average_wait_to_clean_seconds": average(waits),
            "average_cleaning_seconds": average(cleaning),
            "average_time_to_ready_seconds": average(resets),
            "cancelled_attempts": sum(
                1
                for a in attempts
                if a["status"] == "CANCELLED"
                and a.get("cancelled_at")
                and start <= instant(a["cancelled_at"]) < as_of
            ),
            "open_reset_attempts": len(open_attempts),
            "oldest_open_reset_seconds": max(
                ((as_of - instant(a["pending_since"])).total_seconds() for a in open_attempts),
                default=None,
            ),
            "open_occupied_sessions": sum(
                s["status"] != "INVALIDATED"
                and instant(s["arrived_at"]) < as_of
                and (not s.get("departed_at") or instant(s["departed_at"]) >= as_of)
                for s in sessions
            ),
            "cross_boundary_sessions": sum(instant(s["arrived_at"]) < start for s in sessions),
            "excluded_sessions": excluded_sessions,
            "excluded_attempts": excluded_attempts,
            "corrections_applied": sum(
                overlap(c, d, start, as_of) > 0 for _, c, d, _ in corrections
            ),
        },
        "limitations": [
            "Recorded human workflow is not measured occupancy accuracy.",
            "Missing history and camera evidence remain UNKNOWN; empty denominators are null.",
            "Session/reset averages use full valid durations ending in the range; state-time totals are clipped.",
            "Each response has its own cutoff; a later export can include newer corrections.",
            "Synthetic records and estimated evidence are labeled separately.",
            *(
                [
                    "DEMO scenario totals use saved simulated transitions and staff task timestamps; repeated arrivals do not restart visits.",
                    "Full DEMO visit durations can start before this range or the tracking upgrade; state-time rows still respect their original record basis.",
                ]
                if scenario_attempts
                else []
            ),
        ],
    }


def spreadsheet_text(value):
    # A visible alphabetic prefix survives save/reopen better than quotes/apostrophes.
    # Preserve original database text; normalize only this exported string.
    text = "".join(
        " " if unicodedata.category(c) in {"Cc", "Cf", "Zl", "Zp"} else c for c in str(value)
    )
    check = unicodedata.normalize("NFKC", text).lstrip()
    return "Text: " + text if check.startswith(("=", "+", "-", "@")) else text


def csv_bytes(report):
    columns = [
        "row_type",
        "expected_table_rows",
        "from_date",
        "to_date_exclusive",
        "table_id",
        "table_label",
        "bucket_start",
        "bucket_end",
        "local_label",
        "basis",
        "synthetic",
        "time_zone",
        "as_of",
        "calculation_version",
        "cursor",
        "configured_seconds",
        "usable_seconds",
        "occupied_seconds",
        *["state_" + s for s in STATES],
        "workflow_coverage",
        "known_evidence_seconds",
        "unknown_evidence_seconds",
        "evidence_coverage",
        "estimated_occupied_seconds",
        "estimated_occupied_fraction",
        "estimate_basis",
        *["report_" + k for k in report["summary"]],
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\r\n")
    writer.writeheader()
    for index, row in enumerate([{}, *report["rows"]]):
        values = {k: row.get(k) for k in columns}
        values.update(
            {
                k: report[k]
                for k in [
                    "from_date",
                    "to_date_exclusive",
                    "basis",
                    "synthetic",
                    "time_zone",
                    "as_of",
                    "calculation_version",
                    "cursor",
                    "estimate_basis",
                ]
            }
        )
        values["row_type"] = "report_metadata" if index == 0 else "table_bucket"
        values["expected_table_rows"] = len(report["rows"])
        if index == 0:
            values.update({"report_" + k: v for k, v in report["summary"].items()})
        for state in STATES:
            values["state_" + state] = (row.get("state_seconds") or {}).get(state)
        writer.writerow(
            {k: spreadsheet_text(v) if isinstance(v, str) else v for k, v in values.items()}
        )
    return ("\ufeff" + stream.getvalue()).encode("utf-8")
