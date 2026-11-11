"""Terminal owned-event rejections and a fresh-generation uncertainty boundary."""

from pathlib import Path

from alembic import op

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    path = Path(__file__).resolve().parents[1] / 'sql' / '0008_rejected_context.sql'
    op.get_bind().exec_driver_sql(path.read_text(encoding='utf-8'),
                                 execution_options={'no_parameters':True})


def downgrade():
    raise RuntimeError('Destructive rejection-context downgrade is disabled')
