"""cajon monedero nivel produccion: comando configurable, un cajon por
caja, y registro de auditoria completo de aperturas

Revision ID: f346ee9e8aef
Revises: 72fe990ddc94
Create Date: 2026-07-19 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f346ee9e8aef'
down_revision: str | None = '72fe990ddc94'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('cash_drawers', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='2')
        )
        batch_op.add_column(
            sa.Column('pulse_count', sa.Integer(), nullable=False, server_default='1')
        )
        batch_op.add_column(
            sa.Column('pulse_duration_ms', sa.Integer(), nullable=False, server_default='50')
        )
        batch_op.add_column(sa.Column('custom_command_hex', sa.String(length=200), nullable=True))
        batch_op.create_unique_constraint(
            'uq_cash_drawers_cash_register_id', ['cash_register_id']
        )

    with op.batch_alter_table('cash_drawer_events', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'opening_kind',
                sa.Enum('AUTOMATIC', 'MANUAL', name='cashdraweropeningkind', native_enum=False),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('username', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('cash_register_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('cash_register_name', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('workstation', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('branch_location', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('sale_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('invoice_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('debt_payment_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('reason', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('response_time_ms', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('port_used', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('ip_address_used', sa.String(length=45), nullable=True))
        batch_op.add_column(sa.Column('ip_port_used', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('model_snapshot', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('brand_snapshot', sa.String(length=100), nullable=True))
        batch_op.create_foreign_key(
            'fk_cash_drawer_events_sale_id_sales', 'sales', ['sale_id'], ['id'], ondelete='SET NULL'
        )
        batch_op.create_foreign_key(
            'fk_cash_drawer_events_invoice_id_invoices',
            'invoices', ['invoice_id'], ['id'], ondelete='SET NULL',
        )
        batch_op.create_foreign_key(
            'fk_cash_drawer_events_debt_payment_id_debt_payment_receipts',
            'debt_payment_receipts', ['debt_payment_id'], ['id'], ondelete='SET NULL',
        )


def downgrade() -> None:
    with op.batch_alter_table('cash_drawer_events', schema=None) as batch_op:
        batch_op.drop_constraint(
            'fk_cash_drawer_events_debt_payment_id_debt_payment_receipts', type_='foreignkey'
        )
        batch_op.drop_constraint(
            'fk_cash_drawer_events_invoice_id_invoices', type_='foreignkey'
        )
        batch_op.drop_constraint('fk_cash_drawer_events_sale_id_sales', type_='foreignkey')
        batch_op.drop_column('brand_snapshot')
        batch_op.drop_column('model_snapshot')
        batch_op.drop_column('ip_port_used')
        batch_op.drop_column('ip_address_used')
        batch_op.drop_column('port_used')
        batch_op.drop_column('response_time_ms')
        batch_op.drop_column('reason')
        batch_op.drop_column('debt_payment_id')
        batch_op.drop_column('invoice_id')
        batch_op.drop_column('sale_id')
        batch_op.drop_column('branch_location')
        batch_op.drop_column('workstation')
        batch_op.drop_column('cash_register_name')
        batch_op.drop_column('cash_register_id')
        batch_op.drop_column('username')
        batch_op.drop_column('user_id')
        batch_op.drop_column('opening_kind')

    with op.batch_alter_table('cash_drawers', schema=None) as batch_op:
        batch_op.drop_constraint('uq_cash_drawers_cash_register_id', type_='unique')
        batch_op.drop_column('custom_command_hex')
        batch_op.drop_column('pulse_duration_ms')
        batch_op.drop_column('pulse_count')
        batch_op.drop_column('timeout_seconds')
        batch_op.drop_column('is_default')
