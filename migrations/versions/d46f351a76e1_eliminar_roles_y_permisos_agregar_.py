"""eliminar roles y permisos, agregar grants_full_access y photo_path

Revision ID: d46f351a76e1
Revises: f976ce673f36
Create Date: 2026-07-11 10:52:46.717698
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'd46f351a76e1'
down_revision: str | None = 'f976ce673f36'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # `users.role_id` (y su FK a `roles.id`) se elimina ANTES de borrar la
    # tabla `roles`: el modo batch de SQLite reconstruye `users` reflejando
    # su estado actual, y esa reflexión falla si `roles` ya no existe pero
    # `users` todavía referencia esa FK. Reordenado a mano respecto al
    # output de `--autogenerate` (que lo generó al revés).
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('photo_path', sa.String(length=500), nullable=True))
        batch_op.drop_column('role_id')

    with op.batch_alter_table('job_positions', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'grants_full_access', sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )

    op.drop_table('role_permissions')
    op.drop_table('permissions')
    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_roles_uuid'))
    op.drop_table('roles')


def downgrade() -> None:
    """Downgrade solo de esquema, no de datos: las asignaciones de rol
    reales se perdieron al hacer upgrade (no hay forma de reconstruirlas).
    `roles`/`permissions`/`role_permissions` quedan vacías y
    `users.role_id` vuelve nullable (sin dato real que backfillear) — el
    orden se invirtió a mano respecto al output de `--autogenerate` por la
    misma razón que en `upgrade()`: `roles` debe existir antes de poder
    recrear la FK `users.role_id -> roles.id`."""
    op.create_table('roles',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('name', sa.VARCHAR(length=80), nullable=False),
    sa.Column('description', sa.VARCHAR(length=255), nullable=True),
    sa.Column('is_system_role', sa.BOOLEAN(), nullable=False),
    sa.Column('uuid', sa.VARCHAR(length=36), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=False),
    sa.Column('updated_at', sa.DATETIME(), nullable=False),
    sa.Column('created_by_user_id', sa.INTEGER(), nullable=True),
    sa.Column('updated_by_user_id', sa.INTEGER(), nullable=True),
    sa.Column('is_deleted', sa.BOOLEAN(), nullable=False),
    sa.Column('deleted_at', sa.DATETIME(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_roles_uuid'), ['uuid'], unique=1)

    op.create_table('permissions',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('code', sa.VARCHAR(length=100), nullable=False),
    sa.Column('description', sa.VARCHAR(length=255), nullable=True),
    sa.Column('created_at', sa.DATETIME(), nullable=False),
    sa.Column('updated_at', sa.DATETIME(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_table('role_permissions',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('role_id', sa.INTEGER(), nullable=False),
    sa.Column('permission_id', sa.INTEGER(), nullable=False),
    sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('role_id', 'permission_id', name=op.f('uq_role_permission'))
    )

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role_id', sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key('fk_users_role_id_roles', 'roles', ['role_id'], ['id'])
        batch_op.drop_column('photo_path')

    with op.batch_alter_table('job_positions', schema=None) as batch_op:
        batch_op.drop_column('grants_full_access')
    # ### end Alembic commands ###
