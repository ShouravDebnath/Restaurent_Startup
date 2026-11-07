"""Expose only the authenticated human's effective deadline for local preview expiry."""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE FUNCTION security.session_deadline(digest_ text,idle_ integer) RETURNS timestamptz
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
        SELECT least(expires_at,last_seen_at+idle_*interval '1 second') FROM identity.sessions
        WHERE token_digest=digest_ AND user_id=security.actor() AND NOT revoked
    $$;
    REVOKE ALL ON FUNCTION security.session_deadline(text,integer) FROM PUBLIC;
    """)


def downgrade() -> None:
    raise RuntimeError("Preview deadline downgrade is disabled")
