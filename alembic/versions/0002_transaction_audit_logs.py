"""transaction audit logs

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'transaction_audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('transaction_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(80), nullable=False),
        sa.Column('status', sa.String(40), nullable=True),
        sa.Column('tx_hash', sa.String(66), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_transaction_audit_logs_transaction_id',
        'transaction_audit_logs',
        ['transaction_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_transaction_audit_logs_transaction_id', table_name='transaction_audit_logs')
    op.drop_table('transaction_audit_logs')
