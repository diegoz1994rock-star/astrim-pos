"""Casos de uso de administración de usuarios."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.exc import IntegrityError

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.core.security.password import hash_password
from pos.modules.job_positions.infrastructure.repository import JobPositionRepository
from pos.modules.users.application.dto import UserDocumentDTO, UserDTO
from pos.modules.users.domain.events import UserCreatedEvent, UserStatusChangedEvent
from pos.modules.users.infrastructure.document_storage import save_user_document
from pos.modules.users.infrastructure.models import User, UserDocument
from pos.modules.users.infrastructure.photo_storage import save_user_photo
from pos.modules.users.infrastructure.repository import UserRepository

_MIN_PASSWORD_LENGTH = 8


def _to_dto(
    user: User,
    job_area_name: str | None = None,
    job_position_name: str | None = None,
) -> UserDTO:
    return UserDTO(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        emergency_phone=user.emergency_phone,
        blood_type=user.blood_type,
        address=user.address,
        photo_path=user.photo_path,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        job_area_id=user.job_area_id,
        job_area_name=job_area_name,
        job_position_id=user.job_position_id,
        job_position_name=job_position_name,
    )


def _to_document_dto(document: UserDocument) -> UserDocumentDTO:
    return UserDocumentDTO(
        id=document.id,
        original_filename=document.original_filename,
        stored_path=document.stored_path,
        uploaded_at=document.created_at,
    )


def _resolve_job_area_and_position(
    job_position_repo: JobPositionRepository,
    job_area_id: int | None,
    job_position_id: int | None,
) -> tuple[int | None, str | None, str | None]:
    """Valida y resuelve el área/cargo elegidos, devolviendo
    `(job_area_id, job_area_name, job_position_name)`. Si se eligió un
    cargo, el área se deriva de él (y debe coincidir con la elegida, si
    se eligió una)."""
    job_area_name = None
    job_position_name = None
    if job_position_id is not None:
        position = job_position_repo.get_position(job_position_id)
        if position is None:
            raise NotFoundError(f"No existe el cargo con id={job_position_id}.")
        if job_area_id is not None and position.area_id != job_area_id:
            raise BusinessRuleViolationError(
                "El cargo elegido no pertenece al área seleccionada."
            )
        job_area_id = position.area_id
        job_position_name = position.name
    if job_area_id is not None:
        area = job_position_repo.get_area(job_area_id)
        if area is None:
            raise NotFoundError(f"No existe el área con id={job_area_id}.")
        job_area_name = area.name
    return job_area_id, job_area_name, job_position_name


class UserManagementService:
    """Alta, edición, eliminación y activación/desactivación de usuarios
    del sistema. No hay Roles/Permisos: la clasificación (Área/Cargo) y el
    nivel de acceso conviven en el mismo cargo (ver `JobPosition`).

    `delete_user` intenta un borrado físico real. Si el usuario tiene
    historial de negocio (ventas, caja, pedidos, etc.), cualquier FK hacia
    `users.id` bloquea el borrado con `IntegrityError` — en vez de fallar,
    el usuario se desactiva y se marca como eliminado lógicamente
    (`is_active=False`, `is_deleted=True`), que lo excluye igual de
    `list_users`: "Eliminar" nunca falla desde la UI, y el historial de
    negocio nunca pierde a qué usuario hace referencia."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def list_users(self) -> list[UserDTO]:
        with session_scope() as session:
            repo = UserRepository(session)
            return [
                _to_dto(user, job_area_name, job_position_name)
                for user, job_area_name, job_position_name in repo.list_active_users_with_names()
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
        email: str | None = None,
        phone: str | None = None,
        emergency_phone: str | None = None,
        blood_type: str | None = None,
        address: str | None = None,
        photo_source_path: str | None = None,
        job_area_id: int | None = None,
        job_position_id: int | None = None,
    ) -> UserDTO:
        username = username.strip()
        full_name = full_name.strip()
        if not username or not full_name:
            raise BusinessRuleViolationError("El usuario y el nombre completo son obligatorios.")
        if len(password) < _MIN_PASSWORD_LENGTH:
            raise BusinessRuleViolationError(
                f"La contraseña debe tener al menos {_MIN_PASSWORD_LENGTH} caracteres."
            )

        photo_path = save_user_photo(Path(photo_source_path)) if photo_source_path else None

        with session_scope() as session:
            user_repo = UserRepository(session)
            job_position_repo = JobPositionRepository(session)

            existing_user = user_repo.get_by_username(username)

            if existing_user is not None:
                raise ConflictError(
                    f"Ya existe un usuario con el nombre de usuario '{username}'."
                )

            deleted_user = user_repo.get_deleted_by_username(username)

            if deleted_user is not None:
                job_area_id, job_area_name, job_position_name = _resolve_job_area_and_position(
                    job_position_repo,
                    job_area_id,
                    job_position_id,
                )

                deleted_user.password_hash = hash_password(password)
                deleted_user.full_name = full_name
                deleted_user.email = email
                deleted_user.phone = phone
                deleted_user.emergency_phone = emergency_phone
                deleted_user.blood_type = blood_type
                deleted_user.address = address
                deleted_user.photo_path = photo_path
                deleted_user.job_area_id = job_area_id
                deleted_user.job_position_id = job_position_id
                deleted_user.is_active = True
                deleted_user.is_deleted = False
                deleted_user.deleted_at = None

                session.flush()

                dto = _to_dto(
                    deleted_user,
                    job_area_name,
                    job_position_name,
                )

                self._event_bus.publish(
                    UserCreatedEvent(
                        user_id=dto.id,
                        username=dto.username,
                    )
                )

                return dto

            job_area_id, job_area_name, job_position_name = _resolve_job_area_and_position(
                job_position_repo, job_area_id, job_position_id
            )

            user = user_repo.create_user(
                username=username,
                password_hash=hash_password(password),
                full_name=full_name,
                email=email,
                phone=phone,
                emergency_phone=emergency_phone,
                blood_type=blood_type,
                address=address,
                photo_path=photo_path,
                job_area_id=job_area_id,
                job_position_id=job_position_id,
            )
            dto = _to_dto(user, job_area_name, job_position_name)

        self._event_bus.publish(UserCreatedEvent(user_id=dto.id, username=dto.username))
        return dto

    def update_user(
        self,
        user_id: int,
        *,
        username: str,
        full_name: str,
        email: str | None = None,
        phone: str | None = None,
        emergency_phone: str | None = None,
        blood_type: str | None = None,
        address: str | None = None,
        photo_source_path: str | None = None,
        job_area_id: int | None = None,
        job_position_id: int | None = None,
    ) -> UserDTO:
        username = username.strip()
        full_name = full_name.strip()
        if not username or not full_name:
            raise BusinessRuleViolationError("El usuario y el nombre completo son obligatorios.")

        photo_path = save_user_photo(Path(photo_source_path)) if photo_source_path else None

        with session_scope() as session:
            user_repo = UserRepository(session)
            job_position_repo = JobPositionRepository(session)

            user = user_repo.get_user(user_id)
            if user is None:
                raise NotFoundError(f"No existe el usuario con id={user_id}.")

            existing = user_repo.get_by_username(username)
            if existing is not None and existing.id != user_id:
                raise ConflictError(f"Ya existe un usuario con el nombre de usuario '{username}'.")

            job_area_id, job_area_name, job_position_name = _resolve_job_area_and_position(
                job_position_repo, job_area_id, job_position_id
            )

            user_repo.update_user(
                user,
                username=username,
                full_name=full_name,
                email=email,
                phone=phone,
                emergency_phone=emergency_phone,
                blood_type=blood_type,
                address=address,
                photo_path=photo_path,
                job_area_id=job_area_id,
                job_position_id=job_position_id,
            )
            dto = _to_dto(user, job_area_name, job_position_name)

        return dto

    def set_active(self, user_id: int, is_active: bool) -> UserDTO:
        """Activa o desactiva un usuario. Un usuario inactivo no puede
        iniciar sesión (ver `AuthRepository.find_active_user_by_username`)."""
        with session_scope() as session:
            user_repo = UserRepository(session)

            user = user_repo.get_user(user_id)
            if user is None:
                raise NotFoundError(f"No existe el usuario con id={user_id}.")

            user.is_active = is_active
            dto = _to_dto(user)

        self._event_bus.publish(UserStatusChangedEvent(user_id=dto.id, is_active=is_active))
        return dto

    def delete_user(self, user_id: int) -> None:
        """Elimina físicamente al usuario cuando es posible. Bloquea el
        borrado (con `BusinessRuleViolationError`) solo si es el único
        "Administrador General" del sistema — esa sí es una regla de
        negocio real. Si tiene historial de negocio asociado (bloqueo por
        FK/`IntegrityError`), en vez de fallar lo desactiva y lo marca
        como eliminado lógicamente, con el mismo efecto visible."""
        with session_scope() as session:
            user_repo = UserRepository(session)
            job_position_repo = JobPositionRepository(session)

            user = user_repo.get_user(user_id)
            if user is None:
                raise NotFoundError(f"No existe el usuario con id={user_id}.")

            if user.job_position_id is not None:
                position = job_position_repo.get_position(user.job_position_id)
                if (
                    position is not None
                    and position.grants_full_access
                    and user_repo.count_users_with_full_access_position() <= 1
                ):
                    raise BusinessRuleViolationError(
                        "No se puede eliminar: es el único usuario con el cargo "
                        "'Administrador General'. Crea o asciende a otro usuario a "
                        "ese cargo antes de eliminar este."
                    )

        try:
            with session_scope() as session:
                user = UserRepository(session).get_user(user_id)
                assert user is not None
                session.delete(user)
                session.flush()
            return
        except IntegrityError:
            pass

        with session_scope() as session:
            user = UserRepository(session).get_user(user_id)
            assert user is not None
            user.is_active = False
            user.is_deleted = True

    def list_documents(self, user_id: int) -> list[UserDocumentDTO]:
        with session_scope() as session:
            repo = UserRepository(session)
            if repo.get_user(user_id) is None:
                raise NotFoundError(f"No existe el usuario con id={user_id}.")
            return [_to_document_dto(doc) for doc in repo.list_documents(user_id)]

    def add_document(self, user_id: int, source_path: str) -> UserDocumentDTO:
        with session_scope() as session:
            repo = UserRepository(session)
            if repo.get_user(user_id) is None:
                raise NotFoundError(f"No existe el usuario con id={user_id}.")

            path = Path(source_path)
            stored_path = save_user_document(path)
            document = repo.add_document(
                user_id, original_filename=path.name, stored_path=stored_path
            )
            return _to_document_dto(document)

    def delete_document(self, document_id: int) -> None:
        with session_scope() as session:
            repo = UserRepository(session)
            document = repo.get_document(document_id)
            if document is None:
                raise NotFoundError(f"No existe el documento con id={document_id}.")
            repo.delete_document(document)

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
