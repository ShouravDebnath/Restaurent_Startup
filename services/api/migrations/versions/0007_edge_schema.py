"""Add Phase 6 metadata tables without rewriting business records."""

from pathlib import Path

from alembic import op

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    for name in ('0007_edge_schema.sql', '0007_edge_security.sql'):
        path = Path(__file__).resolve().parents[1] / 'sql' / name
        op.get_bind().exec_driver_sql(path.read_text(encoding='utf-8'),
                                     execution_options={'no_parameters': True})


def downgrade():
    raise RuntimeError('Destructive edge downgrade is disabled; preserve queued records and receipts')
