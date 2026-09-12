"""agregar empresa nit codigo tipo al historial de licencias

Revision ID: ff98ad2f02e0
Revises: 8ef4bacff97c
Create Date: 2026-07-31 08:56:18.335272
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'ff98ad2f02e0'
down_revision: str | None = '8ef4bacff97c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('license_history_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('company_name', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('company_nit', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('license_key', sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column(
                'license_type',
                sa.Enum(
                    'TRIAL', 'MONTHLY', 'SEMIANNUAL', 'ANNUAL', 'PERMANENT',
                    name='licensetype', native_enum=False,
                ),
                nullable=True,
            )
        )

    # Las filas de historial ya existentes (de licencias activadas antes
    # de este cambio) quedan con estos 4 campos completados a partir de la
    # licencia a la que pertenecen — sin esto, todo el historial previo a
    # esta migración se vería vacío en esas columnas para siempre.
    op.execute(
        """
        UPDATE license_history_entries
        SET company_name = (
                SELECT licenses.company_name FROM licenses
                WHERE licenses.id = license_history_entries.license_id
            ),
            company_nit = (
                SELECT licenses.company_nit FROM licenses
                WHERE licenses.id = license_history_entries.license_id
            ),
            license_key = (
                SELECT licenses.license_key FROM licenses
                WHERE licenses.id = license_history_entries.license_id
            ),
            license_type = (
                SELECT licenses.license_type FROM licenses
                WHERE licenses.id = license_history_entries.license_id
            )
        """
    )


def downgrade() -> None:
    with op.batch_alter_table('license_history_entries', schema=None) as batch_op:
        batch_op.drop_column('license_type')
        batch_op.drop_column('license_key')
        batch_op.drop_column('company_nit')
        batch_op.drop_column('company_name')
