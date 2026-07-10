"""Casos de uso de administración de usuarios."""

from __future__ import annotations

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.core.security.password import hash_password
from pos.modules.roles.infrastructure.repository import RoleRepository
from pos.modules.users.application.dto import UserDTO
from pos.modules.users.domain.events import UserCreatedEvent, UserStatusChangedEvent
from pos.modules.users.infrastructure.models import User
from pos.modules.users.infrastructure.repository import UserRepository

_MIN_PASSWORD_LENGTH = 8


def _to_dto(user: User, role_name: str) -> UserDTO:
    return UserDTO(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        role_id=user.role_id,
        role_name=role_name,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
    )


class UserManagementService:
    """Alta, edición y activación/desactivación de usuarios del sistema.

    No expone un `delete_user`: los usuarios con historial de negocio
    (ventas, movimientos de caja) nunca se borran físicamente (soft delete
    vía `is_active`/`is_deleted`, ver DATABASE.md, convenciones globales).
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def list_users(self) -> list[UserDTO]:
        with session_scope() as session:
            repo = UserRepository(session)
            return [
                _to_dto(user, role_name) for user, role_name in repo.list_active_users_with_role()
            ]

    def count_users(self) -> int:
        """Usado por `main.py` para decidir si mostrar la pantalla de
        configuración inicial (base de datos recién creada, cero usuarios)
        en vez del login normal."""
        with session_scope() as session:
            return UserRepository(session).count_users()

    def create_user(
        self,
        *,
        username: str,
        password: str,
        full_name: str,
        role_id: int,
        email: str | None = None,
        phone: str | None = None,
    ) -> UserDTO:
        username = username.strip()
        full_name = full_name.strip()
        if not username or not full_name:
            raise BusinessRuleViolationError("El usuario y el nombre completo son obligatorios.")
        if len(password) < _MIN_PASSWORD_LENGTH:
            raise BusinessRuleViolationError(
                f"La contraseña debe tener al menos {_MIN_PASSWORD_LENGTH} caracteres."
            )

        with session_scope() as session:
            user_repo = UserRepository(session)
            role_repo = RoleRepository(session)

            if user_repo.get_by_username(username) is not None:
                raise ConflictError(f"Ya existe un usuario con el nombre de usuario '{username}'.")
            if role_repo.get_role(role_id) is None:
                raise NotFoundError(f"No existe el rol con id={role_id}.")

            user = user_repo.create_user(
                username=username,
                password_hash=hash_password(password),
                full_name=full_name,
                role_id=role_id,
                email=email,
                phone=phone,
            )
            role_name = role_repo.get_role(role_id).name  # type: ignore[union-attr]
            dto = _to_dto(user, role_name)

        self._event_bus.publish(UserCreatedEvent(user_id=dto.id, username=dto.username))
        return dto

    def set_active(self, user_id: int, is_active: bool) -> UserDTO:
        """Activa o desactiva un usuario. Un usuario inactivo no puede
        iniciar sesión (ver `AuthRepository.find_active_user_by_username`)."""
        with session_scope() as session:
            user_repo = UserRepository(session)
            role_repo = RoleRepository(session)

            user = user_repo.get_user(user_id)
            if user is None:
                raise NotFoundError(f"No existe el usuario con id={user_id}.")

            user.is_active = is_active
            role_name = role_repo.get_role(user.role_id).name  # type: ignore[union-attr]
            dto = _to_dto(user, role_name)

        self._event_bus.publish(UserStatusChangedEvent(user_id=dto.id, is_active=is_active))
        return dto

    def reset_password(self, user_id: int, new_password: str) -> None:
        if len(new_password) < _MIN_PASSWORD_LENGTH:
            raise BusinessRuleViolationError(
                f"La contraseña debe tener al menos {_MIN_PASSWORD_LENGTH} caracteres."
            )
        with session_scope() as session:
            user_repo = UserRepository(session)
            user = user_repo.get_user(user_id)
            if user is None:
                raise NotFoundError(f"No existe el usuario con id={user_id}.")
            user.password_hash = hash_password(new_password)
