"""
002_violations.py - Create violations table.

Violations are derived artifacts from policy evaluation.
Immutable once persisted. No update or delete operations.

Revision ID: 002_violations
Revises: 001_event_chains
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers
revision = "002_violations"
down_revision = "001_event_chains"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "violations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.session_id_str"),
            nullable=False,
        ),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("event_sequence_number", sa.Integer(), nullable=False),
        sa.Column("policy_name", sa.String(), nullable=False),
        sa.Column("policy_version", sa.String(), nullable=False),
        sa.Column("policy_hash", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # Indexes for common query patterns
    op.create_index("ix_violations_session_id", "violations", ["session_id"])
    op.create_index("ix_violations_severity", "violations", ["severity"])
    op.create_index("ix_violations_policy_name", "violations", ["policy_name"])
    op.create_index(
        "ix_violations_session_severity",
        "violations",
        ["session_id", "severity"],
    )


def downgrade() -> None:
    op.drop_index("ix_violations_session_severity")
    op.drop_index("ix_violations_policy_name")
    op.drop_index("ix_violations_severity")
    op.drop_index("ix_violations_session_id")
    op.drop_table("violations")
