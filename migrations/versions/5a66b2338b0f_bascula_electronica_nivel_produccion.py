"""bascula electronica nivel produccion: tara por software, estabilidad,
reconexion automatica, simulador y registro centralizado de pesadas

Revision ID: 5a66b2338b0f
Revises: d4b8f1a6c2e7
Create Date: 2026-07-18 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '5a66b2338b0f'
down_revision: str | None = 'd4b8f1a6c2e7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('scale_device_configs', schema=None) as batch_op:
        batch_op.alter_column(
            'stop_bits', existing_type=sa.Integer(), type_=sa.Float(), nullable=True
        )
        batch_op.add_column(
            sa.Column('stability_required', sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(
            sa.Column(
                'min_stable_seconds', sa.Numeric(5, 2), nullable=False, server_default='0.50'
            )
        )
        batch_op.add_column(
            sa.Column('auto_reconnect', sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(
            sa.Column('current_tare', sa.Numeric(10, 3), nullable=False, server_default='0')
        )
        batch_op.add_column(sa.Column('simulator_target_weight', sa.Numeric(10, 3), nullable=True))

    op.create_table(
        'scale_weight_reads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scale_device_id', sa.Integer(), nullable=True),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('username', sa.String(length=150), nullable=True),
        sa.Column('cash_register_id', sa.Integer(), nullable=True),
        sa.Column('cash_register_name', sa.String(length=150), nullable=True),
        sa.Column('gross_weight', sa.Numeric(10, 3), nullable=True),
        sa.Column('net_weight', sa.Numeric(10, 3), nullable=True),
        sa.Column('tare', sa.Numeric(10, 3), nullable=False),
        sa.Column(
            'unit', sa.Enum('KG', 'G', 'LB', 'OZ', name='scaleunitofmeasure', native_enum=False),
            nullable=False,
        ),
        sa.Column(
            'status',
            sa.Enum(
                'STABLE', 'UNSTABLE', 'ZERO', 'NEGATIVE', 'INVALID', 'OUT_OF_RANGE',
                name='weightreadingstatus', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('is_stable', sa.Boolean(), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.String(length=500), nullable=True),
        sa.Column('reconnected', sa.Boolean(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['scale_device_id'], ['scale_device_configs.id'], ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('scale_weight_reads', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_scale_weight_reads_occurred_at'), ['occurred_at'], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table('scale_weight_reads', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_scale_weight_reads_occurred_at'))
    op.drop_table('scale_weight_reads')

    with op.batch_alter_table('scale_device_configs', schema=None) as batch_op:
        batch_op.drop_column('simulator_target_weight')
        batch_op.drop_column('current_tare')
        batch_op.drop_column('auto_reconnect')
        batch_op.drop_column('min_stable_seconds')
        batch_op.drop_column('stability_required')
        batch_op.alter_column(
            'stop_bits', existing_type=sa.Float(), type_=sa.Integer(), nullable=True
        )
