"""Read-only DEMO summaries from saved scenario events and staff tasks.

These are simulated visits, never device evidence or confirmed customer metrics.
No history, workflow session or task-attempt row is created or backfilled.
"""


def scenario_records(snapshot):
    sessions, attempts = [], []
    if not snapshot["synthetic"]:
        return sessions, attempts
    canonical = {str(s["id"]) for s in snapshot["sessions"]}
    seen = set()
    tables = {str(t["id"]) for t in snapshot["tables"]}
    for task in snapshot.get("scenario_tasks", []):
        session_id = str(task["occupancy_session_id"])
        if (
            str(task["table_id"]) not in tables
            or session_id in canonical
            or session_id in seen
            or not task["departure_verified"]
        ):
            continue
        seen.add(session_id)
        completed = task["status"] == "COMPLETED"
        # Without the saved staff actions, retain an incomplete duration instead
        # of inventing a cleaning/ready confirmation from AVAILABLE alone.
        verified = (
            task["start_verified"]
            and task["ready_verified"]
            and task["resolution"] == "staff_confirmed_ready"
        )
        arrived = task["arrived_at"]
        if arrived is not None:
            sessions.append(
                {
                    "id": session_id,
                    "table_id": task["table_id"],
                    "arrived_at": arrived,
                    "departed_at": task["created_at"],
                    "ready_at": task["completed_at"] if completed and verified else None,
                    "status": "INVALIDATED"
                    if task["resolution"] == "manager_blocked"
                    else "COMPLETE"
                    if completed and verified
                    else "VACATED",
                }
            )
        attempts.append(
            {
                "session_id": session_id,
                "pending_since": task["created_at"],
                "started_at": task["started_at"]
                if task["start_verified"] and (not completed or verified)
                else None,
                "completed_at": task["completed_at"] if completed else None,
                "cancelled_at": task["completed_at"] if task["status"] == "CANCELLED" else None,
                "status": task["status"],
                "resolution": task["resolution"],
            }
        )
    return sessions, attempts
