"""agregar invoice_settings

Revision ID: e1068900f3f2
Revises: 0a0e0dd1c582
Create Date: 2026-07-13 09:17:13.029180
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'e1068900f3f2'
down_revision: str | None = '0a0e0dd1c582'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'invoice_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=150), nullable=False),
        sa.Column('company_nit', sa.String(length=50), nullable=True),
        sa.Column('company_address', sa.String(length=255), nullable=True),
        sa.Column('company_city', sa.String(length=100), nullable=True),
        sa.Column('company_phone', sa.String(length=50), nullable=True),
        sa.Column('company_email', sa.String(length=150), nullable=True),
        sa.Column('company_website', sa.String(length=200), nullable=True),
        sa.Column('logo_path', sa.String(length=500), nullable=True),
        sa.Column('paper_size', sa.String(length=20), nullable=False),
        sa.Column('printer_name', sa.String(length=100), nullable=True),
        sa.Column('show_logo', sa.Boolean(), nullable=False),
        sa.Column('show_customer', sa.Boolean(), nullable=False),
        sa.Column('show_cashier', sa.Boolean(), nullable=False),
        sa.Column('show_register', sa.Boolean(), nullable=False),
        sa.Column('show_date', sa.Boolean(), nullable=False),
        sa.Column('show_time', sa.Boolean(), nullable=False),
        sa.Column('show_discounts', sa.Boolean(), nullable=False),
        sa.Column('show_taxes', sa.Boolean(), nullable=False),
        sa.Column('show_total', sa.Boolean(), nullable=False),
        sa.Column('show_qr', sa.Boolean(), nullable=False),
        sa.Column('show_barcode', sa.Boolean(), nullable=False),
        sa.Column('show_closing_message', sa.Boolean(), nullable=False),
        sa.Column('show_social_media', sa.Boolean(), nullable=False),
        sa.Column('show_return_policy', sa.Boolean(), nullable=False),
        sa.Column('content_order', sa.String(length=500), nullable=False),
        sa.Column('closing_message', sa.Text(), nullable=True),
        sa.Column('social_media', sa.Text(), nullable=True),
        sa.Column('return_policy', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('invoice_settings')
