"""agregar barcode_reads (registro centralizado de lecturas)

Revision ID: d4b8f1a6c2e7
Revises: c19a2f7e5b3d
Create Date: 2026-07-18 17:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd4b8f1a6c2e7'
down_revision: str | None = 'c19a2f7e5b3d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SYMBOLOGY_VALUES = (
    'EAN13', 'EAN8', 'UPC_A', 'UPC_E', 'CODE39', 'CODE93', 'CODE128', 'CODABAR',
    'ITF', 'MSI', 'GS1_128', 'DATAMATRIX', 'PDF417', 'QR', 'AZTEC', 'UNKNOWN',
)


def upgrade() -> None:
    op.create_table(
        'barcode_reads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column(
            'symbology',
            sa.Enum(*_SYMBOLOGY_VALUES, name='barcodesymbology', native_enum=False),
            nullable=False,
        ),
        sa.Column('found', sa.Boolean(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column(
            'source',
            sa.Enum(
                'SALE', 'PRODUCT_FORM', 'TEST_PANEL',
                name='barcodereadsource', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('username', sa.String(length=150), nullable=True),
        sa.Column('cash_register_id', sa.Integer(), nullable=True),
        sa.Column('cash_register_name', sa.String(length=150), nullable=True),
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_barcode_reads_occurred_at'), 'barcode_reads', ['occurred_at'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_barcode_reads_occurred_at'), table_name='barcode_reads')
    op.drop_table('barcode_reads')
