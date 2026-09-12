"""agregar pdf_path a debt_payment_receipts

Revision ID: 209e19812449
Revises: 502149878ec9
Create Date: 2026-07-20 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '209e19812449'
down_revision: str | None = '502149878ec9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('debt_payment_receipts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pdf_path', sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('debt_payment_receipts', schema=None) as batch_op:
        batch_op.drop_column('pdf_path')
