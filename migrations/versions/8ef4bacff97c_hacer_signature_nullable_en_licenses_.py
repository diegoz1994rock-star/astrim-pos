"""hacer signature nullable en licenses para pool de codigos

Revision ID: 8ef4bacff97c
Revises: 8f25779a6be3
Create Date: 2026-07-31 08:16:43.080751
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '8ef4bacff97c'
down_revision: str | None = '8f25779a6be3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('licenses', schema=None) as batch_op:
        batch_op.alter_column('signature', existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('licenses', schema=None) as batch_op:
        batch_op.alter_column('signature', existing_type=sa.Text(), nullable=False)
