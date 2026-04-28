"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ledgers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('balance', sa.Numeric(36, 18), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ledger_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('to_address', sa.String(42), nullable=False),
        sa.Column('amount', sa.Numeric(36, 18), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'SIGNED', 'BROADCAST', 'SETTLED', 'FAILED', 'PENDING_REVIEW', name='transactionstatus'), nullable=True),
        sa.Column('policy_decision', sa.Enum('ALLOW', 'CHALLENGE', 'BLOCK', name='policydecision'), nullable=True),
        sa.Column('tx_hash', sa.String(66), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('settled_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['ledger_id'], ['ledgers.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'whitelist',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('address', sa.String(42), nullable=False),
        sa.Column('label', sa.String(120), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('address'),
    )


def downgrade() -> None:
    op.drop_table('whitelist')
    op.drop_table('transactions')
    op.drop_table('ledgers')
    sa.Enum(name='transactionstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='policydecision').drop(op.get_bind(), checkfirst=True)
