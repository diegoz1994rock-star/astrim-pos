"""reemplazar qr_scanners por barcode_scanners

Revision ID: ba4b1f1da138
Revises: 2a6ab026be1f
Create Date: 2026-07-16 17:38:48.963788
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'ba4b1f1da138'
down_revision: str | None = '2a6ab026be1f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CONNECTION_TYPES = (
    'USB_HID', 'USB_SERIAL', 'BLUETOOTH_HID', 'BLUETOOTH_SERIAL', 'RS232', 'TCP_IP', 'WIFI',
)
_CONNECTION_STATUSES = ('DISCONNECTED', 'CONNECTED', 'ERROR')
_CASE_CONVERSIONS = ('NONE', 'UPPER', 'LOWER')
_EVENT_TYPES = (
    'CONNECTED', 'DISCONNECTED', 'ERROR',
    'TEST_CONNECTION_OK', 'TEST_CONNECTION_FAILED',
    'READ_SUCCESS', 'READ_FAILED',
)
_SYMBOLOGIES = (
    'EAN13', 'EAN8', 'UPC_A', 'UPC_E', 'CODE39', 'CODE93', 'CODE128', 'CODABAR', 'ITF',
    'MSI', 'GS1_128', 'DATAMATRIX', 'PDF417', 'QR', 'AZTEC', 'UNKNOWN',
)
_SCAN_RESULTS = ('SUCCESS', 'FAILED')


def upgrade() -> None:
    op.drop_table('qr_scanner_events')
    op.drop_table('qr_scanners')

    op.create_table(
        'barcode_scanners',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('kind', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('brand', sa.String(length=100), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('serial_number', sa.String(length=100), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('firmware_version', sa.String(length=50), nullable=True),
        sa.Column('battery_level_percent', sa.Integer(), nullable=True),
        sa.Column('cash_register_id', sa.Integer(), nullable=True),
        sa.Column(
            'connection_type',
            sa.Enum(*_CONNECTION_TYPES, name='barcodescannerconnectiontype', native_enum=False),
            nullable=False,
        ),
        sa.Column('port', sa.String(length=100), nullable=True),
        sa.Column('baud_rate', sa.Integer(), nullable=True),
        sa.Column('data_bits', sa.Integer(), nullable=False),
        sa.Column('stop_bits', sa.Float(), nullable=False),
        sa.Column('parity', sa.String(length=1), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('ip_port', sa.Integer(), nullable=True),
        sa.Column('bluetooth_address', sa.String(length=50), nullable=True),
        sa.Column(
            'connection_status',
            sa.Enum(
                *_CONNECTION_STATUSES, name='barcodescannerconnectionstatus', native_enum=False
            ),
            nullable=False,
        ),
        sa.Column('last_read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_successful_communication_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scan_count', sa.Integer(), nullable=False),
        sa.Column('connected_since', sa.DateTime(timezone=True), nullable=True),
        sa.Column('prefix', sa.String(length=20), nullable=False),
        sa.Column('suffix', sa.String(length=20), nullable=False),
        sa.Column('auto_enter', sa.Boolean(), nullable=False),
        sa.Column('auto_tab', sa.Boolean(), nullable=False),
        sa.Column('min_length', sa.Integer(), nullable=True),
        sa.Column('max_length', sa.Integer(), nullable=True),
        sa.Column('validate_checksum', sa.Boolean(), nullable=False),
        sa.Column('strip_special_chars', sa.Boolean(), nullable=False),
        sa.Column(
            'convert_case',
            sa.Enum(*_CASE_CONVERSIONS, name='barcodescannercaseconversion', native_enum=False),
            nullable=False,
        ),
        sa.Column('ignore_spaces', sa.Boolean(), nullable=False),
        sa.Column('inter_char_timeout_ms', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['cash_register_id'], ['cash_registers.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'barcode_scanner_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scanner_id', sa.Integer(), nullable=False),
        sa.Column(
            'event_type',
            sa.Enum(*_EVENT_TYPES, name='barcodescannereventtype', native_enum=False),
            nullable=False,
        ),
        sa.Column('message', sa.String(length=500), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['scanner_id'], ['barcode_scanners.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'barcode_scan_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scanner_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=500), nullable=False),
        sa.Column(
            'symbology',
            sa.Enum(*_SYMBOLOGIES, name='barcodescannersymbology', native_enum=False),
            nullable=False,
        ),
        sa.Column('cash_register_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column(
            'result',
            sa.Enum(*_SCAN_RESULTS, name='barcodescannerscanresult', native_enum=False),
            nullable=False,
        ),
        sa.Column('read_duration_ms', sa.Integer(), nullable=True),
        sa.Column('is_simulated', sa.Boolean(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['scanner_id'], ['barcode_scanners.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cash_register_id'], ['cash_registers.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('barcode_scan_history')
    op.drop_table('barcode_scanner_events')
    op.drop_table('barcode_scanners')

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
