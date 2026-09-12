"""agregar cash_drawers

Revision ID: 856f142b56c0
Revises: 24f894abd99b
Create Date: 2026-07-14 14:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '856f142b56c0'
down_revision: str | None = '24f894abd99b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'cash_drawers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('kind', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('brand', sa.String(length=100), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('serial_number', sa.String(length=100), nullable=True),
        sa.Column('location', sa.String(length=150), nullable=True),
        sa.Column(
            'opening_type',
            sa.Enum(
                'PRINTER_KICKOUT', 'DIRECT_USB', 'DIRECT_SERIAL', 'DIRECT_ETHERNET',
                name='cashdraweropeningtype', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            'opening_device_kind',
            sa.Enum('DIRECT', 'LINKED_TERMINAL', name='cashdraweropeningdevicekind', native_enum=False),
            nullable=False,
        ),
        sa.Column('linked_terminal_id', sa.Integer(), nullable=True),
        sa.Column('linked_printer_name', sa.String(length=150), nullable=True),
        sa.Column(
            'connection_type',
            sa.Enum(
                'USB', 'SERIAL', 'BLUETOOTH', 'ETHERNET', 'WIFI',
                name='cashdrawerconnectiontype', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('port', sa.String(length=100), nullable=True),
        sa.Column('baud_rate', sa.Integer(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('ip_port', sa.Integer(), nullable=True),
        sa.Column('cash_register_id', sa.Integer(), nullable=True),
        sa.Column('auto_open_after_sale', sa.Boolean(), nullable=False),
        sa.Column(
            'connection_status',
            sa.Enum(
                'DISCONNECTED', 'CONNECTED', 'ERROR',
                name='cashdrawerconnectionstatus', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('last_successful_communication_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['linked_terminal_id'], ['pos_terminals.id']),
        sa.ForeignKeyConstraint(['cash_register_id'], ['cash_registers.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'cash_drawer_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cash_drawer_id', sa.Integer(), nullable=False),
        sa.Column(
            'event_type',
            sa.Enum(
                'CONNECTED', 'DISCONNECTED', 'ERROR',
                'TEST_CONNECTION_OK', 'TEST_CONNECTION_FAILED', 'OPENED', 'OPEN_FAILED',
                name='cashdrawereventtype', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('message', sa.String(length=500), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['cash_drawer_id'], ['cash_drawers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('cash_drawer_events')
    op.drop_table('cash_drawers')
