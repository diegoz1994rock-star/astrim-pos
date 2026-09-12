"""agregar qr_scanners

Revision ID: 5d080eef58cb
Revises: 856f142b56c0
Create Date: 2026-07-14 14:40:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '5d080eef58cb'
down_revision: str | None = '856f142b56c0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'qr_scanners',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('kind', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('brand', sa.String(length=100), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('serial_number', sa.String(length=100), nullable=True),
        sa.Column('scanner_type', sa.String(length=50), nullable=True),
        sa.Column(
            'connection_type',
            sa.Enum(
                'USB', 'SERIAL', 'BLUETOOTH', 'ETHERNET', 'WIFI',
                name='qrscannerconnectiontype', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('port', sa.String(length=100), nullable=True),
        sa.Column('baud_rate', sa.Integer(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('ip_port', sa.Integer(), nullable=True),
        sa.Column('bluetooth_address', sa.String(length=50), nullable=True),
        sa.Column(
            'read_mode',
            sa.Enum('CONTINUOUS', 'MANUAL', name='qrscannerreadmode', native_enum=False),
            nullable=False,
        ),
        sa.Column('cash_register_id', sa.Integer(), nullable=True),
        sa.Column('station_label', sa.String(length=100), nullable=True),
        sa.Column(
            'connection_status',
            sa.Enum(
                'DISCONNECTED', 'CONNECTED', 'ERROR',
                name='qrscannerconnectionstatus', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('last_code_read', sa.String(length=500), nullable=True),
        sa.Column('last_successful_communication_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['cash_register_id'], ['cash_registers.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'qr_scanner_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('qr_scanner_id', sa.Integer(), nullable=False),
        sa.Column(
            'event_type',
            sa.Enum(
                'CONNECTED', 'DISCONNECTED', 'ERROR',
                'TEST_CONNECTION_OK', 'TEST_CONNECTION_FAILED',
                'READ_SUCCESS', 'READ_FAILED',
                name='qrscannereventtype', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('message', sa.String(length=500), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['qr_scanner_id'], ['qr_scanners.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('qr_scanner_events')
    op.drop_table('qr_scanners')
