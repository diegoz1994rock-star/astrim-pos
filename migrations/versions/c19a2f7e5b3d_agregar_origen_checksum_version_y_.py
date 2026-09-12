"""agregar origen, checksum, version y usuario a backup_history

Revision ID: c19a2f7e5b3d
Revises: b71cf3e0a9d4
Create Date: 2026-07-18 16:42:30.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c19a2f7e5b3d'
down_revision: str | None = 'b71cf3e0a9d4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('backup_history', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'origin',
                sa.Enum('MANUAL', 'SCHEDULED', 'IMPORTED', name='backuporigin', native_enum=False),
                nullable=False,
                server_default='MANUAL',
            )
        )
        batch_op.add_column(sa.Column('checksum_sha256', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('app_version', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('created_by_user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('created_by_username', sa.String(length=150), nullable=True))

    op.execute(
        "UPDATE backup_history SET origin = 'SCHEDULED' WHERE backup_job_id IS NOT NULL"
    )


def downgrade() -> None:
    with op.batch_alter_table('backup_history', schema=None) as batch_op:
        batch_op.drop_column('created_by_username')
        batch_op.drop_column('created_by_user_id')
        batch_op.drop_column('app_version')
        batch_op.drop_column('checksum_sha256')
        batch_op.drop_column('origin')
