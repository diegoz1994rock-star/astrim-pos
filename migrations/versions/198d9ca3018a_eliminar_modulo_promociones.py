"""eliminar modulo promociones

Revision ID: 198d9ca3018a
Revises: f3a8c1d9e4b7
Create Date: 2026-07-17 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '198d9ca3018a'
down_revision: str | None = 'f3a8c1d9e4b7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Orden seguro por llaves foráneas: primero las tablas que referencian
    # a `promotions`, al final `promotions` misma — mismo orden que ya
    # usaba el downgrade() de la migración inicial (7d3d00ef46d1).
    op.drop_table('discounts_applied')
    op.drop_table('promotion_rules')
    op.drop_table('promotions')


def downgrade() -> None:
    op.create_table(
        'promotions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column(
            'discount_type',
            sa.Enum(
                'PERCENTAGE',
                'FIXED_AMOUNT',
                'SPECIAL_PRICE',
                'BUY_X_PAY_Y',
                name='discounttype',
                native_enum=False,
                length=30,
            ),
            nullable=False,
        ),
        sa.Column('discount_value', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('buy_quantity', sa.Integer(), nullable=True),
        sa.Column('pay_quantity', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'promotion_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('promotion_id', sa.Integer(), nullable=False),
        sa.Column(
            'rule_type',
            sa.Enum(
                'PRODUCT',
                'CATEGORY',
                'COMBO',
                'MIN_QUANTITY',
                'DAY_OF_WEEK',
                'TIME_RANGE',
                name='promotionruletype',
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('rule_value', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['promotion_id'], ['promotions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'discounts_applied',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sale_id', sa.Integer(), nullable=False),
        sa.Column('promotion_id', sa.Integer(), nullable=True),
        sa.Column('sale_item_id', sa.Integer(), nullable=True),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('applied_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['promotion_id'], ['promotions.id']),
        sa.ForeignKeyConstraint(['sale_id'], ['sales.id']),
        sa.ForeignKeyConstraint(['sale_item_id'], ['sale_items.id']),
        sa.PrimaryKeyConstraint('id'),
    )
