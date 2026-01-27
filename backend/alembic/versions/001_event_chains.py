"""add event_chains and seals

Revision ID: 001_event_chains
Revises: 
Create Date: 2026-01-25 20:50:00

Constitutional database migration for Day 4 backend.
Adds event_chains, chain_seals tables with append-only enforcement.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '001_event_chains'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create chain_authority enum
    op.execute("CREATE TYPE chain_authority_enum AS ENUM ('server', 'sdk')")
    
    # Create session_status enum
    op.execute("CREATE TYPE session_status_enum AS ENUM ('active', 'sealed', 'failed')")
    
    # Create event_chains table with constitutional guarantees
    op.create_table(
        'event_chains',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('session_id', sa.Integer, sa.ForeignKey('sessions.id'), nullable=False),
        sa.Column('session_id_str', sa.String(36), nullable=False),  # Denormalized for queries
        sa.Column('sequence_number', sa.BigInteger(), nullable=False),
        sa.Column('timestamp_wall', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('timestamp_monotonic', sa.BigInteger(), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('source_sdk_ver', sa.String(20), nullable=True),
        sa.Column('schema_ver', sa.String(10), nullable=False, server_default='v0.6'),
        sa.Column('payload_canonical', sa.Text(), nullable=False),
        sa.Column('payload_hash', sa.String(64), nullable=False),
        sa.Column('payload_jsonb', postgresql.JSONB(), nullable=True),
        sa.Column('prev_event_hash', sa.String(64), nullable=True),
        sa.Column('event_hash', sa.String(64), nullable=False),
        sa.Column('chain_authority', sa.String(20), nullable=False),
    )
    
    # Create indexes
    op.create_index('idx_event_chains_session', 'event_chains', ['session_id'])
    op.create_index('idx_event_chains_sequence', 'event_chains', ['sequence_number'])
    op.create_index('idx_event_chains_type', 'event_chains', ['event_type'])
    op.create_index('idx_event_chains_hash', 'event_chains', ['event_hash'])
    op.create_index('idx_event_chains_timestamp', 'event_chains', ['timestamp_wall'])
    op.create_index('idx_session_sequence_unique', 'event_chains', ['session_id', 'sequence_number'], unique=True)
    op.create_index('idx_event_type_timestamp', 'event_chains', ['event_type', 'timestamp_wall'])
    
    # CONSTITUTIONAL ENFORCEMENT: Append-only trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_event_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Events are immutable per CONSTITUTION.md. Operation % is forbidden on event_chains.', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER prevent_event_mutation
        BEFORE UPDATE OR DELETE ON event_chains
        FOR EACH ROW EXECUTE FUNCTION reject_event_mutation();
    """)
    
    # Create chain_seals table
    op.create_table(
        'chain_seals',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.Integer, sa.ForeignKey('sessions.id'), nullable=False, unique=True),
        sa.Column('ingestion_service_id', sa.String(100), nullable=False),
        sa.Column('seal_timestamp', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('session_digest', sa.String(64), nullable=False),
        sa.Column('final_event_hash', sa.String(64), nullable=False),
        sa.Column('event_count', sa.Integer, nullable=False),
        sa.CheckConstraint('event_count > 0', name='seal_event_count_positive')
    )
    
    op.create_index('idx_chain_seals_session', 'chain_seals', ['session_id'], unique=True)
    
    # Alter sessions table
    op.add_column('sessions', sa.Column('session_id_str', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('sessions', sa.Column('chain_authority', sa.Enum('server', 'sdk', name='chain_authority_enum'), nullable=True))
    # Migrate existing status column to enum type
    op.execute("ALTER TABLE sessions ALTER COLUMN status TYPE session_status_enum USING status::session_status_enum")
    op.add_column('sessions', sa.Column('evidence_class', sa.String(50), nullable=True))
    op.add_column('sessions', sa.Column('sealed_at', postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('sessions', sa.Column('total_drops', sa.Integer, nullable=False, server_default='0'))
    op.add_column('sessions', sa.Column('ingestion_service_id', sa.String(100), nullable=True))
    
    # Add constraints
    op.create_check_constraint('valid_chain_authority', 'sessions', "chain_authority IN ('server', 'sdk')")
    op.create_check_constraint('non_negative_drops', 'sessions', 'total_drops >= 0')
    
    # Create unique index on session_id_str
    op.create_index('idx_sessions_session_id_str', 'sessions', ['session_id_str'], unique=True)
    op.create_index('idx_sessions_authority', 'sessions', ['chain_authority'])
    op.create_index('idx_sessions_evidence_class', 'sessions', ['evidence_class'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_sessions_evidence_class')
    op.drop_index('idx_sessions_authority')
    op.drop_index('idx_sessions_session_id_str')
    
    # Drop constraints
    op.drop_constraint('non_negative_drops', 'sessions')
    op.drop_constraint('valid_chain_authority', 'sessions')
    
    # Revert session status column type
    op.execute("ALTER TABLE sessions ALTER COLUMN status TYPE VARCHAR(50) USING status::text")
    
    # Drop columns from sessions
    op.drop_column('sessions', 'ingestion_service_id')
    op.drop_column('sessions', 'total_drops')
    op.drop_column('sessions', 'sealed_at')
    op.drop_column('sessions', 'evidence_class')
    op.drop_column('sessions', 'chain_authority')
    op.drop_column('sessions', 'session_id_str')
    
    # Drop chain_seals table
    op.drop_index('idx_chain_seals_session')
    op.drop_table('chain_seals')
    
    # Drop event_chains table and trigger
    op.execute("DROP TRIGGER IF EXISTS prevent_event_mutation ON event_chains")
    op.execute("DROP FUNCTION IF EXISTS reject_event_mutation()")
    
    op.drop_index('idx_event_type_timestamp')
    op.drop_index('idx_session_sequence_unique')
    op.drop_index('idx_event_chains_timestamp')
    op.drop_index('idx_event_chains_hash')
    op.drop_index('idx_event_chains_type')
    op.drop_index('idx_event_chains_sequence')
    op.drop_index('idx_event_chains_session')
    op.drop_table('event_chains')
    
    # Drop enums
    op.execute("DROP TYPE session_status_enum")
    op.execute("DROP TYPE chain_authority_enum")
