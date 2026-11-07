"""Add durable demo workflow, controlled actions and passive session validation."""

from pathlib import Path

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    directory = Path(__file__).resolve().parents[1] / "sql"
    for name in ("0003_dashboard_schema.sql", "0003_dashboard_security.sql"):
        op.get_bind().exec_driver_sql(
            (directory / name).read_text(encoding="utf-8"),
            execution_options={"no_parameters": True},
        )


def downgrade() -> None:
    raise RuntimeError("Dashboard downgrade is disabled; use a reviewed forward migration")
