"""Explicit reset-task kind and nullable event confidence; no inferred accuracy."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("staff_tasks", sa.Column("type", sa.String(24), nullable=False, server_default="RESET"))
    op.create_check_constraint("reset_task_type", "staff_tasks", "type = 'RESET'")
    op.add_column("table_events", sa.Column("confidence", sa.Float(), server_default=sa.text("NULL")))
    op.create_check_constraint("event_confidence", "table_events",
                               "confidence IS NULL OR confidence BETWEEN 0 AND 1")


def downgrade() -> None:
    raise RuntimeError("Task/event downgrade is disabled to preserve history")
