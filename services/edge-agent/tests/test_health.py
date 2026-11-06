from restaurant_edge.health import heartbeat_time, initial_health


def test_edge_starts_without_a_camera() -> None:
    health = initial_health()

    assert health.status == "not_configured"
    assert health.last_frame_at is None


def test_heartbeat_is_utc() -> None:
    assert heartbeat_time().tzinfo is not None
