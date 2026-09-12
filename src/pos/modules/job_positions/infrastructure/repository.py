"""Acceso a datos del catálogo de áreas y cargos."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos.modules.job_positions.infrastructure.models import (
    JobArea,
    JobPosition,
    JobPositionPermission,
)


class JobPositionRepository:
    """Operaciones sobre `job_areas` y `job_positions`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_areas(self) -> list[JobArea]:
        return list(self._session.scalars(select(JobArea).order_by(JobArea.name)))

    def list_positions_by_area(self, area_id: int) -> list[JobPosition]:
        return list(
            self._session.scalars(
                select(JobPosition)
                .where(JobPosition.area_id == area_id)
                .order_by(JobPosition.name)
            )
        )

    def list_all_positions_with_area_name(self) -> list[tuple[JobPosition, str]]:
        rows = self._session.execute(
            select(JobPosition, JobArea.name)
            .join(JobArea, JobArea.id == JobPosition.area_id)
            .order_by(JobArea.name, JobPosition.name)
        )
        return [(row[0], row[1]) for row in rows]

    def get_area(self, area_id: int) -> JobArea | None:
        return self._session.get(JobArea, area_id)

    def get_area_by_name(self, name: str) -> JobArea | None:
        return self._session.scalar(select(JobArea).where(JobArea.name == name))

    def get_position(self, position_id: int) -> JobPosition | None:
        return self._session.get(JobPosition, position_id)

    def get_position_by_area_and_name(self, area_id: int, name: str) -> JobPosition | None:
        return self._session.scalar(
            select(JobPosition).where(
                JobPosition.area_id == area_id, JobPosition.name == name
            )
        )

    def create_area(self, *, name: str, description: str | None) -> JobArea:
        area = JobArea(name=name, description=description)
        self._session.add(area)
        self._session.flush()
        return area

    def create_position(
        self, *, area_id: int, name: str, grants_full_access: bool = False
    ) -> JobPosition:
        position = JobPosition(
            area_id=area_id, name=name, grants_full_access=grants_full_access
        )
        self._session.add(position)
        self._session.flush()
        return position

    def rename_area(self, area: JobArea, name: str) -> None:
        area.name = name
        self._session.flush()

    def rename_position(self, position: JobPosition, name: str) -> None:
        position.name = name
        self._session.flush()

    def set_grants_full_access(self, position: JobPosition, value: bool) -> None:
        position.grants_full_access = value
        self._session.flush()

    def delete_area(self, area: JobArea) -> None:
        """Elimina el área. Sus cargos se eliminan en cascada
        (`job_positions.area_id` con `ON DELETE CASCADE`); si alguno de
        esos cargos está asignado a un usuario, `users.job_position_id`
        se pone en `NULL` automáticamente (`ON DELETE SET NULL`), así que
        este borrado nunca falla por integridad referencial."""
        self._session.delete(area)
        self._session.flush()

    def delete_position(self, position: JobPosition) -> None:
        self._session.delete(position)
        self._session.flush()

    def list_permission_codes(self, position_id: int) -> list[str]:
        return list(
            self._session.scalars(
                select(JobPositionPermission.permission_code).where(
                    JobPositionPermission.job_position_id == position_id
                )
            )
        )

    def replace_permissions(self, position_id: int, codes: set[str]) -> None:
        """Reemplaza el conjunto completo de permisos del cargo por
        `codes`: la pantalla siempre envía el estado completo del
        checklist ("Guardar permisos"), no altas/bajas individuales."""
        self._session.query(JobPositionPermission).filter(
            JobPositionPermission.job_position_id == position_id
        ).delete(synchronize_session=False)
        for code in codes:
            self._session.add(
                JobPositionPermission(job_position_id=position_id, permission_code=code)
            )
        self._session.flush()
