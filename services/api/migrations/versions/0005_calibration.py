"""Add immutable calibration history and explicit short-lived human preview grants."""

from pathlib import Path

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    path = Path(__file__).resolve().parents[1] / "sql" / "0005_calibration.sql"
    op.get_bind().exec_driver_sql(path.read_text(encoding="utf-8"),
                                 execution_options={"no_parameters": True})


def downgrade() -> None:
    raise RuntimeError("Calibration downgrade is disabled to preserve history and grants")
