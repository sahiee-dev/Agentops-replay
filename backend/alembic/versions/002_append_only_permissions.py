"""
002_append_only_permissions

Revision ID: 002
Revises: 001_event_chains
Create Date: 2026-05-06
"""

revision = '002'
down_revision = '001_event_chains'
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    # Create restricted application user
    # Note: In Docker, the superuser runs this during setup.
    # This migration is idempotent — CREATE USER IF NOT EXISTS.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'agentops_app') THEN
                CREATE USER agentops_app WITH PASSWORD 'CHANGE_ME_IN_PRODUCTION';
            END IF;
        END
        $$;
    """)

    # Grant schema access
    op.execute("GRANT USAGE ON SCHEMA public TO agentops_app;")

    # Events: INSERT and SELECT only. No UPDATE. No DELETE. EVER.
    op.execute("GRANT SELECT, INSERT ON events TO agentops_app;")

    # Sessions: INSERT, SELECT, UPDATE allowed (status field changes).
    op.execute("GRANT SELECT, INSERT, UPDATE ON sessions TO agentops_app;")

    # Sequences for UUID generation
    op.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO agentops_app;")


def downgrade() -> None:
    op.execute("REVOKE ALL ON events FROM agentops_app;")
    op.execute("REVOKE ALL ON sessions FROM agentops_app;")
