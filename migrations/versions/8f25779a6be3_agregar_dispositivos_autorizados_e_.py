"""agregar dispositivos autorizados e historial de licencia

Revision ID: 8f25779a6be3
Revises: 8971e4613657
Create Date: 2026-07-30 16:01:14.652932
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '8f25779a6be3'
down_revision: str | None = '8971e4613657'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('licenses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('company_name', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('company_nit', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('allowed_users', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('allowed_branches', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('allowed_registers', sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column('max_devices', sa.Integer(), nullable=False, server_default='1')
        )

    op.create_table(
        'authorized_devices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('license_id', sa.Integer(), nullable=False),
        sa.Column('hardware_fingerprint', sa.String(length=128), nullable=False),
        sa.Column('device_name', sa.String(length=150), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            'status', sa.Enum('ACTIVE', 'REVOKED', name='devicestatus', native_enum=False),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['license_id'], ['licenses.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'license_id', 'hardware_fingerprint', name='uq_authorized_device_license_fingerprint'
        ),
    )

    # Toda licencia activada ANTES de este cambio solo tenía
    # `licenses.hardware_fingerprint` (un único equipo, sin fila en
    # `authorized_devices`) — sin este respaldo, `LicenseService.verify()`
    # reportaría `HARDWARE_MISMATCH` para cualquier licencia ya activada
    # apenas se actualice el sistema, porque ahora el chequeo de hardware
    # busca una fila en `authorized_devices`, no la columna vieja. Se
    # convierte ese equipo ya activado en su primer dispositivo autorizado,
    # sin que el usuario tenga que reactivar nada.
    op.execute(
        """
        INSERT INTO authorized_devices
            (license_id, hardware_fingerprint, device_name, ip_address,
             first_seen_at, last_seen_at, status)
        SELECT id, hardware_fingerprint, NULL, NULL, issued_at, issued_at, 'ACTIVE'
        FROM licenses
        """
    )

    op.create_table(
        'license_history_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('license_id', sa.Integer(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('device_name', sa.String(length=150), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column(
            'status_at_time',
            sa.Enum(
                'ACTIVE', 'EXPIRED', 'REVOKED', 'SUSPENDED', 'BLOCKED',
                name='licensestatus', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            'action',
            sa.Enum(
                'ACTIVATED', 'RENEWED', 'SUSPENDED', 'REACTIVATED', 'BLOCKED',
                'DEVICE_REGISTERED', 'DEVICE_REVOKED',
                name='licensehistoryaction', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('details', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['license_id'], ['licenses.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('license_history_entries')
    op.drop_table('authorized_devices')
    with op.batch_alter_table('licenses', schema=None) as batch_op:
        batch_op.drop_column('max_devices')
        batch_op.drop_column('allowed_registers')
        batch_op.drop_column('allowed_branches')
        batch_op.drop_column('allowed_users')
        batch_op.drop_column('company_nit')
        batch_op.drop_column('company_name')
