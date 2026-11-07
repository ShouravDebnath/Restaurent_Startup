"""Protect ownership and scope organization-admin grant management."""

from pathlib import Path

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    path = Path(__file__).resolve().parents[1] / "sql" / "0002_ownership.sql"
    op.get_bind().exec_driver_sql(
        path.read_text(encoding="utf-8"), execution_options={"no_parameters": True}
    )


def downgrade() -> None:
    raise RuntimeError("Phase 2 downgrade is intentionally disabled to preserve data")
