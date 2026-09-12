"""Acceso a datos de usuarios.

Consulta `job_areas`/`job_positions` directamente (LEFT JOIN, ambos
opcionales) para resolver `UserDTO.job_area_name`/`job_position_name` sin
una segunda ida y vuelta a la base de datos — dependencia intencional
`users -> job_positions` documentada en MODULES.md.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos.modules.job_positions.infrastructure.models import JobArea, JobPosition
from pos.modules.users.infrastructure.models import User, UserDocument

_UserRow = tuple[User, str | None, str | None]


def _select_users_with_names():
    return (
        select(User, JobArea.name, JobPosition.name)
        .outerjoin(JobArea, JobArea.id == User.job_area_id)
        .outerjoin(JobPosition, JobPosition.id == User.job_position_id)
    )


class UserRepository:
    """Operaciones sobre `users` y sus archivos adjuntos (`user_documents`)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_active_users_with_names(self) -> list[_UserRow]:
        rows = self._session.execute(
            _select_users_with_names()
            .where(User.is_deleted.is_(False))
            .order_by(User.username)
        )
        return [(row[0], row[1], row[2]) for row in rows]

    def get_user(self, user_id: int) -> User | None:
        return self._session.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        return self._session.scalar(
            select(User).where(
                User.username == username,
                User.is_deleted.is_(False),
            )
        )

    def count_users(self) -> int:
        return self._session.scalar(
            select(func.count()).select_from(User)
        ) or 0

    def count_users_with_full_access_position(self) -> int:
        """Cantidad de usuarios (no eliminados) con un cargo que tiene
        `grants_full_access=True` — usado para impedir borrar al único
        "Administrador General" del sistema.
        """
        count = self._session.scalar(
            select(func.count())
            .select_from(User)
            .join(JobPosition, JobPosition.id == User.job_position_id)
            .where(
                JobPosition.grants_full_access.is_(True),
                User.is_deleted.is_(False),
            )
        )

        return count or 0

    def get_deleted_by_username(self, username: str) -> User | None:
        return self._session.scalar(
            select(User).where(
                User.username == username,
                User.is_deleted.is_(True),
            )
        )

    def create_user(
                self,
        *,
        username: str,
        password_hash: str,
        full_name: str,
        email: str | None,
        phone: str | None,
        emergency_phone: str | None = None,
        blood_type: str | None = None,
        address: str | None = None,
        photo_path: str | None = None,
        job_area_id: int | None = None,
        job_position_id: int | None = None,
    ) -> User:
        user = User(
            username=username,
            password_hash=password_hash,
            full_name=full_name,
            email=email,
            phone=phone,
            emergency_phone=emergency_phone,
            blood_type=blood_type,
            address=address,
            photo_path=photo_path,
            is_active=True,
            job_area_id=job_area_id,
            job_position_id=job_position_id,
        )
        self._session.add(user)
        self._session.flush()
        return user

    def update_user(
        self,
        user: User,
        *,
        username: str,
        full_name: str,
        email: str | None,
        phone: str | None,
        emergency_phone: str | None,
        blood_type: str | None,
        address: str | None,
        photo_path: str | None,
        job_area_id: int | None,
        job_position_id: int | None,
    ) -> None:
        user.username = username
        user.full_name = full_name
        user.email = email
        user.phone = phone
        user.emergency_phone = emergency_phone
        user.blood_type = blood_type
        user.address = address

        if photo_path is not None:
            user.photo_path = photo_path

        user.job_area_id = job_area_id
        user.job_position_id = job_position_id

        self._session.flush()

    def list_documents(self, user_id: int) -> list[UserDocument]:
        return list(
            self._session.scalars(
                select(UserDocument)
                .where(UserDocument.user_id == user_id)
                .order_by(UserDocument.created_at)
            )
        )

    def get_document(self, document_id: int) -> UserDocument | None:
        return self._session.get(UserDocument, document_id)

    def add_document(
        self,
        user_id: int,
        *,
        original_filename: str,
        stored_path: str,
    ) -> UserDocument:
        document = UserDocument(
            user_id=user_id,
            original_filename=original_filename,
            stored_path=stored_path,
        )
        self._session.add(document)
        self._session.flush()
        return document

    def delete_document(self, document: UserDocument) -> None:
        self._session.delete(document)
        self._session.flush()
