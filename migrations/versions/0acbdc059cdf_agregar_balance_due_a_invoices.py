"""agregar balance_due a invoices

Revision ID: 0acbdc059cdf
Revises: 198d9ca3018a
Create Date: 2026-07-17 20:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0acbdc059cdf'
down_revision: str | None = '198d9ca3018a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Saldo pendiente de la factura — 0 para facturas de contado (todas las
    # existentes hasta ahora) y para ventas a crédito ya pagadas; > 0 solo
    # mientras una factura de venta a crédito sigue sin saldarse. Ver
    # `BillingService.pay_invoices`/`generate_invoice`.
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'balance_due', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'
            )
        )


def downgrade() -> None:
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_column('balance_due')
