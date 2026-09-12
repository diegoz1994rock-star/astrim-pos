"""agregar margenes orientacion fuente y tamano personalizado a invoice_settings

Revision ID: 56a2d91b223d
Revises: ee4b16fa4f54
Create Date: 2026-07-13 14:38:52.181530
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '56a2d91b223d'
down_revision: str | None = 'ee4b16fa4f54'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('invoice_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('custom_width_mm', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('custom_height_mm', sa.Float(), nullable=True))
        # `server_default` de una columna Enum(native_enum=False) debe ser el
        # NOMBRE del miembro en mayúsculas ("PORTRAIT"), no su `.value`
        # ("portrait") — SQLAlchemy compara por nombre al leer de vuelta (ver
        # el bug ya corregido una vez para `products.sale_unit`).
        batch_op.add_column(
            sa.Column(
                'orientation', sa.String(length=20), nullable=False, server_default='PORTRAIT'
            )
        )
        batch_op.add_column(
            sa.Column('margin_top_mm', sa.Float(), nullable=False, server_default='8.0')
        )
        batch_op.add_column(
            sa.Column('margin_right_mm', sa.Float(), nullable=False, server_default='8.0')
        )
        batch_op.add_column(
            sa.Column('margin_bottom_mm', sa.Float(), nullable=False, server_default='8.0')
        )
        batch_op.add_column(
            sa.Column('margin_left_mm', sa.Float(), nullable=False, server_default='8.0')
        )
        batch_op.add_column(
            sa.Column('base_font_size_pt', sa.Integer(), nullable=False, server_default='10')
        )


def downgrade() -> None:
    with op.batch_alter_table('invoice_settings', schema=None) as batch_op:
        batch_op.drop_column('base_font_size_pt')
        batch_op.drop_column('margin_left_mm')
        batch_op.drop_column('margin_bottom_mm')
        batch_op.drop_column('margin_right_mm')
        batch_op.drop_column('margin_top_mm')
        batch_op.drop_column('orientation')
        batch_op.drop_column('custom_height_mm')
        batch_op.drop_column('custom_width_mm')
