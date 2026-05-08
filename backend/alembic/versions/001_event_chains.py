"""Complete initial schema

Revision ID: 001_event_chains
Revises:
Create Date: 2026-01-25 20:50:00

Self-contained initial schema migration.
Creates all base tables (users, sessions, events) and TRD v2.0 tables
(event_chains, chain_seals) with append-only enforcement.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001_event_chains"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ------------------------------------------------------------------ #
    # Base tables (previously in 850ff1605e54_initial_complete_schema.py) #
    # ------------------------------------------------------------------ #

    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_users_username", "users", ["username"], unique=True)
    op.create_index("idx_users_email", "users", ["email"])

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("agent_name", sa.String(100), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("sealed_at", sa.DateTime, nullable=True),
        sa.Column("session_id_str", sa.String(36), nullable=False, unique=True),
        sa.Column("chain_authority", sa.String(50), nullable=True),
        sa.Column("total_drops", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ingestion_service_id", sa.String(100), nullable=True),
        sa.Column("evidence_class", sa.String(50), nullable=True),
    )
    op.create_index("idx_sessions_user_id", "sessions", ["user_id"])
    op.create_index("idx_sessions_status", "sessions", ["status"])
    op.create_index("idx_sessions_started_at", "sessions", ["started_at"])
    op.create_index(
        "idx_sessions_session_id_str", "sessions", ["session_id_str"], unique=True
    )
    op.create_index("idx_sessions_authority", "sessions", ["chain_authority"])

    op.create_table(
        "events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer,
            sa.ForeignKey("sessions.id"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("tool_name", sa.String(50), nullable=True),
        sa.Column("flags", postgresql.ARRAY(sa.String), nullable=True),
        sa.Column("sequence_number", sa.Integer, nullable=True),
    )
    op.create_index("idx_events_session_id", "events", ["session_id"])
    op.create_index("idx_events_event_type", "events", ["event_type"])
    op.create_index("idx_events_timestamp", "events", ["timestamp"])

    # ------------------------------------------------------------------ #
    # TRD v2.0 tables                                                      #
    # ------------------------------------------------------------------ #

    op.create_table(
        "event_chains",
        sa.Column("event_id", sa.String, primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("sessions.session_id_str"),
            nullable=False,
        ),
        sa.Column("sequence_number", sa.Integer, nullable=False),
        sa.Column("timestamp_wall", sa.DateTime, nullable=False),
        sa.Column("timestamp_monotonic", sa.Float, nullable=True),
        sa.Column("event_type", sa.String, nullable=False),
        sa.Column("source_sdk_ver", sa.String, nullable=True),
        sa.Column("schema_ver", sa.String, nullable=True),
        sa.Column("payload_canonical", sa.Text, nullable=False),
        sa.Column("payload_hash", sa.String, nullable=False),
        sa.Column("prev_event_hash", sa.String, nullable=True),
        sa.Column("event_hash", sa.String, nullable=False),
        sa.Column("chain_authority", sa.String, nullable=False),
    )
    op.create_index("idx_event_chains_session", "event_chains", ["session_id"])
    op.create_index(
        "idx_event_chains_sequence", "event_chains", ["sequence_number"]
    )
    op.create_index("idx_event_chains_type", "event_chains", ["event_type"])
    op.create_index("idx_event_chains_hash", "event_chains", ["event_hash"])
    op.create_index(
        "idx_event_chains_timestamp", "event_chains", ["timestamp_wall"]
    )

    # Append-only enforcement trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_event_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Events are immutable. Operation % is forbidden on event_chains.', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER prevent_event_mutation
        BEFORE UPDATE OR DELETE ON event_chains
        FOR EACH ROW EXECUTE FUNCTION reject_event_mutation();
    """)

    op.create_table(
        "chain_seals",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer,
            sa.ForeignKey("sessions.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("ingestion_service_id", sa.String, nullable=False),
        sa.Column("seal_timestamp", sa.DateTime, nullable=False),
        sa.Column("session_digest", sa.String, nullable=False),
        sa.Column("final_event_hash", sa.String, nullable=False),
        sa.Column("event_count", sa.Integer, nullable=False),
        sa.CheckConstraint("event_count > 0", name="seal_event_count_positive"),
    )
    op.create_index(
        "idx_chain_seals_session", "chain_seals", ["session_id"], unique=True
    )


def downgrade():
    op.drop_table("chain_seals")

    op.execute("DROP TRIGGER IF EXISTS prevent_event_mutation ON event_chains")
    op.execute("DROP FUNCTION IF EXISTS reject_event_mutation()")
    op.drop_table("event_chains")

    op.drop_table("events")
    op.drop_table("sessions")
    op.drop_table("users")
