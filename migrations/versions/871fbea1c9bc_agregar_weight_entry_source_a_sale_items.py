"""agregar weight_entry_source a sale_items

Revision ID: 871fbea1c9bc
Revises: ff98ad2f02e0
Create Date: 2026-08-01 14:22:17.074672
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '871fbea1c9bc'
down_revision: str | None = 'ff98ad2f02e0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('sale_items', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'weight_entry_source',
                sa.Enum('SCALE', 'MANUAL', name='weightentrysource', native_enum=False),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table('sale_items', schema=None) as batch_op:
        batch_op.drop_column('weight_entry_source')
