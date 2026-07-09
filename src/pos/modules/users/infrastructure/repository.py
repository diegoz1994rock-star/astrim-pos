"""Acceso a datos de usuarios.

Consulta `roles.name` directamente (join) para resolver `UserDTO.role_name`
sin una segunda ida y vuelta a la base de datos — es la misma dependencia
intencional `users -> roles` ya documentada en MODULES.md, aplicada aquí
también a nivel de infraestructura, no solo de aplicación.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos.modules.roles.infrastructure.models import Role
from pos.modules.users.infrastructure.models import User


class UserRepository:
    """Operaciones sobre la tabla `users`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_active_users_with_role(self) -> list[tuple[User, str]]:
        rows = self._session.execute(
            select(User, Role.name)
            .join(Role, Role.id == User.role_id)
            .where(User.is_deleted.is_(False))
            .order_by(User.username)
        )
        return [(row[0], row[1]) for row in rows]

    def get_user(self, user_id: int) -> User | None:
        return self._session.get(User, user_id)

    def get_user_with_role_name(self, user_id: int) -> tuple[User, str] | None:
        row = self._session.execute(
            select(User, Role.name).join(Role, Role.id == User.role_id).where(User.id == user_id)
        ).first()
        return (row[0], row[1]) if row is not None else None

    def get_by_username(self, username: str) -> User | None:
        return self._session.scalar(select(User).where(User.username == username))

    def create_user(
        self,
        *,
        username: str,
        password_hash: str,
        full_name: str,
        role_id: int,
        email: str | None,
        phone: str | None,
    ) -> User:
        user = User(
            username=username,
            password_hash=password_hash,
            full_name=full_name,
            role_id=role_id,
            email=email,
            phone=phone,
            is_active=True,
        )
        self._session.add(user)
        self._session.flush()
        return user
