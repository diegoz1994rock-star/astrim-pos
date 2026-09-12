"""cuentas por cobrar: due_date, credit_history_cleared_at, debt_payment_receipts

Revision ID: b71cf3e0a9d4
Revises: 0acbdc059cdf
Create Date: 2026-07-18 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b71cf3e0a9d4'
down_revision: str | None = '0acbdc059cdf'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('due_date', sa.Date(), nullable=True))

    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('credit_history_cleared_at', sa.DateTime(), nullable=True)
        )

    op.create_table(
        'debt_payment_receipts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('receipt_number', sa.String(length=50), nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            'payment_method',
            sa.Enum(
                'CASH', 'CARD', 'TRANSFER', 'NEQUI', 'DAVIPLATA', 'QR', 'BRE_B',
                'CUSTOMER_CREDIT', 'OTHER',
                name='paymentmethod', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('cash_session_id', sa.Integer(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('note', sa.String(length=255), nullable=True),
        sa.Column('workstation', sa.String(length=150), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id']),
        sa.ForeignKeyConstraint(['cash_session_id'], ['cash_sessions.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('receipt_number'),
    )


def downgrade() -> None:
    op.drop_table('debt_payment_receipts')

    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.drop_column('credit_history_cleared_at')

    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_column('due_date')
