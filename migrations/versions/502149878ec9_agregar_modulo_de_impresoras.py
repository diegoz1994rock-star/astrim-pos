"""agregar modulo de impresoras: printers y printer_events

Revision ID: 502149878ec9
Revises: f346ee9e8aef
Create Date: 2026-07-19 21:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '502149878ec9'
down_revision: str | None = 'f346ee9e8aef'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'printers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('alias', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('brand', sa.String(length=100), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('serial_number', sa.String(length=100), nullable=True),
        sa.Column(
            'printer_type',
            sa.Enum(
                'THERMAL_58', 'THERMAL_80', 'RECEIPT', 'POS', 'LASER', 'INKJET', 'MATRIX',
                'A4', 'LABEL', 'OTHER', name='printertype', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            'print_method',
            sa.Enum('SYSTEM_DRIVER', 'RAW_ESCPOS', name='printmethod', native_enum=False),
            nullable=False,
        ),
        sa.Column('system_printer_name', sa.String(length=200), nullable=True),
        sa.Column(
            'connection_type',
            sa.Enum(
                'USB', 'SERIAL', 'BLUETOOTH', 'ETHERNET', 'WIFI', 'SHARED_NETWORK',
                name='printerconnectiontype', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('port', sa.String(length=100), nullable=True),
        sa.Column('baud_rate', sa.Integer(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('ip_port', sa.Integer(), nullable=True),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False),
        sa.Column('cash_register_id', sa.Integer(), nullable=True),
        sa.Column('area', sa.String(length=100), nullable=True),
        sa.Column('copies', sa.Integer(), nullable=False),
        sa.Column(
            'orientation',
            sa.Enum('PORTRAIT', 'LANDSCAPE', name='printerorientation', native_enum=False),
            nullable=False,
        ),
        sa.Column('margin_top_mm', sa.Numeric(5, 2), nullable=False),
        sa.Column('margin_right_mm', sa.Numeric(5, 2), nullable=False),
        sa.Column('margin_bottom_mm', sa.Numeric(5, 2), nullable=False),
        sa.Column('margin_left_mm', sa.Numeric(5, 2), nullable=False),
        sa.Column('resolution_dpi', sa.Integer(), nullable=False),
        sa.Column('paper_width_mm', sa.Numeric(6, 2), nullable=False),
        sa.Column('paper_length_mm', sa.Numeric(6, 2), nullable=True),
        sa.Column('auto_cut', sa.Boolean(), nullable=False),
        sa.Column('open_drawer_after_print', sa.Boolean(), nullable=False),
        sa.Column('show_dialog', sa.Boolean(), nullable=False),
        sa.Column(
            'connection_status',
            sa.Enum(
                'DISCONNECTED', 'CONNECTED', 'ERROR',
                name='printerdeviceconnectionstatus', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('last_successful_communication_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['cash_register_id'], ['cash_registers.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'printer_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('printer_id', sa.Integer(), nullable=True),
        sa.Column(
            'event_type',
            sa.Enum(
                'CONNECTED', 'DISCONNECTED', 'ERROR', 'TEST_CONNECTION_OK',
                'TEST_CONNECTION_FAILED', 'TEST_PAGE_PRINTED', 'TEST_PAGE_FAILED',
                'PRINT_SUCCESS', 'PRINT_FAILED', name='printereventtype', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('message', sa.String(length=500), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('username', sa.String(length=150), nullable=True),
        sa.Column('cash_register_id', sa.Integer(), nullable=True),
        sa.Column('cash_register_name', sa.String(length=150), nullable=True),
        sa.Column(
            'document_type',
            sa.Enum(
                'INVOICE', 'DEBT_RECEIPT', 'TEST_PAGE',
                name='printdocumenttype', native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column('document_reference', sa.String(length=100), nullable=True),
        sa.Column('sale_id', sa.Integer(), nullable=True),
        sa.Column('invoice_id', sa.Integer(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('printer_name_snapshot', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['printer_id'], ['printers.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['sale_id'], ['sales.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('printer_events', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_printer_events_occurred_at'), ['occurred_at'], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table('printer_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_printer_events_occurred_at'))
    op.drop_table('printer_events')
    op.drop_table('printers')
