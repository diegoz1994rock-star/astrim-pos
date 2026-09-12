"""ampliar scale_device_configs y agregar scale_device_events

Revision ID: a64535ddb49a
Revises: 726c6eb1cb16
Create Date: 2026-07-14 11:20:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'a64535ddb49a'
down_revision: str | None = '726c6eb1cb16'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('scale_device_configs', schema=None) as batch_op:
        batch_op.alter_column('port', existing_type=sa.String(length=100), nullable=True)
        batch_op.alter_column('baud_rate', existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column('brand', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('model', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('serial_number', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('description', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('location', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('cash_register_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('station_label', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('assigned_user_id', sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                'connection_type',
                sa.Enum(
                    'USB', 'SERIAL', 'BLUETOOTH', 'ETHERNET', 'WIFI',
                    name='scaleconnectiontype', native_enum=False,
                ),
                nullable=False,
                server_default='SERIAL',
            )
        )
        batch_op.add_column(sa.Column('data_bits', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('stop_bits', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('parity', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('ip_address', sa.String(length=45), nullable=True))
        batch_op.add_column(sa.Column('ip_port', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('bluetooth_address', sa.String(length=50), nullable=True))
        batch_op.add_column(
            sa.Column(
                'unit_of_measure',
                sa.Enum('KG', 'G', 'LB', name='scaleunitofmeasure', native_enum=False),
                nullable=False,
                server_default='KG',
            )
        )
        batch_op.add_column(
            sa.Column('decimal_places', sa.Integer(), nullable=False, server_default='3')
        )
        batch_op.add_column(
            sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='2')
        )
        batch_op.add_column(
            sa.Column('read_frequency_seconds', sa.Integer(), nullable=False, server_default='1')
        )
        batch_op.add_column(
            sa.Column('auto_read', sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column(
                'connection_status',
                sa.Enum(
                    'DISCONNECTED', 'CONNECTED', 'ERROR',
                    name='deviceconnectionstatus', native_enum=False,
                ),
                nullable=False,
                server_default='DISCONNECTED',
            )
        )
        batch_op.add_column(
            sa.Column('last_successful_communication_at', sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_foreign_key(
            'fk_scale_device_configs_cash_register_id_cash_registers',
            'cash_registers', ['cash_register_id'], ['id'],
        )
        batch_op.create_foreign_key(
            'fk_scale_device_configs_assigned_user_id_users',
            'users', ['assigned_user_id'], ['id'],
        )

    op.create_table(
        'scale_device_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scale_device_id', sa.Integer(), nullable=False),
        sa.Column(
            'event_type',
            sa.Enum(
                'CONNECTED', 'DISCONNECTED', 'ERROR', 'READ_SUCCESS', 'READ_FAILED',
                'TARE', 'CALIBRATION', 'TEST_CONNECTION_OK', 'TEST_CONNECTION_FAILED',
                name='scaledeviceeventtype', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('message', sa.String(length=500), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['scale_device_id'], ['scale_device_configs.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('scale_device_events')

    with op.batch_alter_table('scale_device_configs', schema=None) as batch_op:
        batch_op.drop_constraint(
            'fk_scale_device_configs_assigned_user_id_users', type_='foreignkey'
        )
        batch_op.drop_constraint(
            'fk_scale_device_configs_cash_register_id_cash_registers', type_='foreignkey'
        )
        batch_op.drop_column('last_successful_communication_at')
        batch_op.drop_column('connection_status')
        batch_op.drop_column('auto_read')
        batch_op.drop_column('read_frequency_seconds')
        batch_op.drop_column('timeout_seconds')
        batch_op.drop_column('decimal_places')
        batch_op.drop_column('unit_of_measure')
        batch_op.drop_column('bluetooth_address')
        batch_op.drop_column('ip_port')
        batch_op.drop_column('ip_address')
        batch_op.drop_column('parity')
        batch_op.drop_column('stop_bits')
        batch_op.drop_column('data_bits')
        batch_op.drop_column('connection_type')
        batch_op.drop_column('assigned_user_id')
        batch_op.drop_column('station_label')
        batch_op.drop_column('cash_register_id')
        batch_op.drop_column('location')
        batch_op.drop_column('description')
        batch_op.drop_column('serial_number')
        batch_op.drop_column('model')
        batch_op.drop_column('brand')
        batch_op.alter_column('baud_rate', existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column('port', existing_type=sa.String(length=100), nullable=False)
