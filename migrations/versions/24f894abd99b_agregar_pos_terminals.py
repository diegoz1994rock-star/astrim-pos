"""agregar pos_terminals

Revision ID: 24f894abd99b
Revises: a64535ddb49a
Create Date: 2026-07-14 13:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '24f894abd99b'
down_revision: str | None = 'a64535ddb49a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'pos_terminals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('kind', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('brand', sa.String(length=100), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('serial_number', sa.String(length=100), nullable=True),
        sa.Column('bank_or_provider', sa.String(length=100), nullable=True),
        sa.Column('terminal_type', sa.String(length=50), nullable=True),
        sa.Column('cash_register_id', sa.Integer(), nullable=True),
        sa.Column('station_label', sa.String(length=100), nullable=True),
        sa.Column('assigned_user_id', sa.Integer(), nullable=True),
        sa.Column(
            'connection_type',
            sa.Enum(
                'USB', 'SERIAL', 'BLUETOOTH', 'ETHERNET', 'WIFI',
                name='posterminalconnectiontype', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('port', sa.String(length=100), nullable=True),
        sa.Column('baud_rate', sa.Integer(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('ip_port', sa.Integer(), nullable=True),
        sa.Column('bluetooth_address', sa.String(length=50), nullable=True),
        sa.Column(
            'connection_status',
            sa.Enum(
                'DISCONNECTED', 'CONNECTED', 'ERROR',
                name='posterminalconnectionstatus', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('last_successful_communication_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['cash_register_id'], ['cash_registers.id']),
        sa.ForeignKeyConstraint(['assigned_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'pos_terminal_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pos_terminal_id', sa.Integer(), nullable=False),
        sa.Column(
            'event_type',
            sa.Enum(
                'CONNECTED', 'DISCONNECTED', 'ERROR',
                'TEST_CONNECTION_OK', 'TEST_CONNECTION_FAILED',
                'TEST_TRANSACTION_OK', 'TEST_TRANSACTION_FAILED',
                name='posterminaleventtype', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('message', sa.String(length=500), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['pos_terminal_id'], ['pos_terminals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('pos_terminal_events')
    op.drop_table('pos_terminals')
