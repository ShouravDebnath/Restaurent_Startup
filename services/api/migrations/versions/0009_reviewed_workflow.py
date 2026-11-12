"""Opt-in reviewed workflow, task attempts and analytics provenance; preserve old data."""

from pathlib import Path

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("0009_workflow_schema.sql", "0009_workflow_security.sql"):
        path = Path(__file__).resolve().parents[1] / "sql" / name
        op.get_bind().exec_driver_sql(
            path.read_text(encoding="utf-8"), execution_options={"no_parameters": True}
        )


def downgrade():
    raise RuntimeError(
        "Destructive workflow downgrade disabled; preserve records and correction history"
    )
