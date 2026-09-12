"""agregar template_config_json a invoice_settings

Revision ID: 2a6ab026be1f
Revises: a433e972ed91
Create Date: 2026-07-16 14:30:24.517620
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '2a6ab026be1f'
down_revision: str | None = 'a433e972ed91'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('invoice_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('template_config_json', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('invoice_settings', schema=None) as batch_op:
        batch_op.drop_column('template_config_json')
