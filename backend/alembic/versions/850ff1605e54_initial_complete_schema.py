"""Initial complete schema

Revision ID: 850ff1605e54
Revises:
Create Date: 2025-08-10 10:07:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "850ff1605e54"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(100), nullable=True),
        sa.Column("api_key", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=True, default=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("api_key"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # Create sessions table
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(100), nullable=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=True),
        sa.Column("agent_version", sa.String(50), nullable=True),
        sa.Column(
            "agent_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("environment", sa.String(50), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("total_cost_usd", sa.Float(), nullable=True),
        sa.Column("average_latency_ms", sa.Float(), nullable=True),
        sa.Column("event_count", sa.Integer(), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=True),
        sa.Column("tool_call_count", sa.Integer(), nullable=True),
        sa.Column("success_rate", sa.Float(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("compliance_status", sa.String(20), nullable=True),
        sa.Column(
            "policy_violations", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("risk_level", sa.String(20), nullable=True),
        sa.Column("is_replay", sa.Boolean(), nullable=False),
        sa.Column("original_session_id", sa.Integer(), nullable=True),
        sa.Column(
            "replay_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("extra_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create events table
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("tool_name", sa.String(50), nullable=True),
        sa.Column("flags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create event_templates table
    op.create_table(
        "event_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("event_templates")
    op.drop_table("events")
    op.drop_table("sessions")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
