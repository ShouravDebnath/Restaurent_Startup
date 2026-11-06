from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class EdgeHealth:
    status: str
    source: str
    last_frame_at: datetime | None


def initial_health(source: str = "not_configured") -> EdgeHealth:
    return EdgeHealth(
        status="not_configured",
        source=source,
        last_frame_at=None,
    )


def heartbeat_time() -> datetime:
    return datetime.now(UTC)
