"""Casos de uso de administración del catálogo de áreas y cargos."""

from __future__ import annotations

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.job_positions.application.dto import JobAreaDTO, JobPositionDTO
from pos.modules.job_positions.domain.permission_catalog import PERMISSION_CATALOG
from pos.modules.job_positions.application.system_bootstrap import (
    ensure_admin_position,
    ensure_default_job_catalog,
)
from pos.modules.job_positions.infrastructure.repository import JobPositionRepository


class JobPositionManagementService:
    """CRUD del catálogo de áreas y cargos: único modelo organizacional
    del sistema (Área → Cargo → Usuario). El cargo "Administrador
    General" (`grants_full_access=True`) reemplaza al antiguo sistema de
    Roles y Permisos — no hay permisos granulares, solo ese flag binario."""

    def ensure_system_defaults(self) -> None:
        """Siembra el catálogo por defecto si todavía no existe ninguna
        área, y garantiza que "Administrador General" exista sin importar
        el estado previo del catálogo (ver `system_bootstrap.py`). El
        catálogo queda totalmente editable desde la UI después de esto."""
        ensure_default_job_catalog()
        ensure_admin_position()

    def list_areas(self) -> list[JobAreaDTO]:
        with session_scope() as session:
            repo = JobPositionRepository(session)
            areas = repo.list_areas()
            positions_by_area: dict[int, list[JobPositionDTO]] = {area.id: [] for area in areas}
            for position, _area_name in repo.list_all_positions_with_area_name():
                positions_by_area[position.area_id].append(
                    JobPositionDTO(
                        id=position.id,
                        area_id=position.area_id,
                        name=position.name,
                        grants_full_access=position.grants_full_access,
                    )
                )
            return [
                JobAreaDTO(
                    id=area.id,
                    name=area.name,
                    description=area.description,
                    positions=tuple(positions_by_area[area.id]),
                )
                for area in areas
            ]

    def create_area(self, *, name: str, description: str | None = None) -> JobAreaDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre del área no puede estar vacío.")

        with session_scope() as session:
            repo = JobPositionRepository(session)
            if repo.get_area_by_name(name) is not None:
                raise ConflictError(f"Ya existe un área llamada '{name}'.")
            area = repo.create_area(name=name, description=description or None)
            return JobAreaDTO(id=area.id, name=area.name, description=area.description, positions=())

    def rename_area(self, area_id: int, name: str) -> JobAreaDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre del área no puede estar vacío.")

        with session_scope() as session:
            repo = JobPositionRepository(session)
            area = repo.get_area(area_id)
            if area is None:
                raise NotFoundError(f"No existe el área con id={area_id}.")
            existing = repo.get_area_by_name(name)
            if existing is not None and existing.id != area_id:
                raise ConflictError(f"Ya existe un área llamada '{name}'.")
            repo.rename_area(area, name)
            positions = tuple(
                JobPositionDTO(
                    id=p.id, area_id=p.area_id, name=p.name, grants_full_access=p.grants_full_access
                )
                for p in repo.list_positions_by_area(area_id)
            )
            return JobAreaDTO(id=area.id, name=area.name, description=area.description, positions=positions)

    def delete_area(self, area_id: int) -> None:
        with session_scope() as session:
            repo = JobPositionRepository(session)
            area = repo.get_area(area_id)
            if area is None:
                raise NotFoundError(f"No existe el área con id={area_id}.")
            if any(p.grants_full_access for p in repo.list_positions_by_area(area_id)):
                raise BusinessRuleViolationError(
                    "No se puede eliminar esta área: contiene el cargo "
                    "'Administrador General', que siempre debe existir."
                )
            repo.delete_area(area)

    def create_position(self, *, area_id: int, name: str) -> JobPositionDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre del cargo no puede estar vacío.")

        with session_scope() as session:
            repo = JobPositionRepository(session)
            area = repo.get_area(area_id)
            if area is None:
                raise NotFoundError(f"No existe el área con id={area_id}.")
            if repo.get_position_by_area_and_name(area_id, name) is not None:
                raise ConflictError(f"El área '{area.name}' ya tiene un cargo llamado '{name}'.")
            position = repo.create_position(area_id=area_id, name=name)
            return JobPositionDTO(
                id=position.id,
                area_id=position.area_id,
                name=position.name,
                grants_full_access=position.grants_full_access,
            )

    def rename_position(self, position_id: int, name: str) -> JobPositionDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre del cargo no puede estar vacío.")

        with session_scope() as session:
            repo = JobPositionRepository(session)
            position = repo.get_position(position_id)
            if position is None:
                raise NotFoundError(f"No existe el cargo con id={position_id}.")
            existing = repo.get_position_by_area_and_name(position.area_id, name)
            if existing is not None and existing.id != position_id:
                raise ConflictError("Ese cargo ya existe en la misma área.")
            repo.rename_position(position, name)
            return JobPositionDTO(
                id=position.id,
                area_id=position.area_id,
                name=position.name,
                grants_full_access=position.grants_full_access,
            )

    def delete_position(self, position_id: int) -> None:
        """Elimina el cargo. Si algún usuario lo tenía asignado,
        `users.job_position_id` se pone en `NULL` automáticamente
        (`ON DELETE SET NULL`) — el cargo es organizacional, no debe
        bloquear su borrado por haber sido usado alguna vez."""
        with session_scope() as session:
            repo = JobPositionRepository(session)
            position = repo.get_position(position_id)
            if position is None:
                raise NotFoundError(f"No existe el cargo con id={position_id}.")
            if position.grants_full_access:
                raise BusinessRuleViolationError(
                    "No se puede eliminar el cargo 'Administrador General': es el "
                    "cargo de mayor jerarquía y siempre debe existir."
                )
            repo.delete_position(position)

    def list_available_permissions(self) -> list[tuple[str, str]]:
        """Catálogo completo de permisos otorgables, para poblar el
        checklist de la UI sin que `presentation` importe
        `domain.permission_catalog` directamente."""
        return list(PERMISSION_CATALOG)

    def list_permission_codes(self, position_id: int) -> list[str]:
        with session_scope() as session:
            repo = JobPositionRepository(session)
            position = repo.get_position(position_id)
            if position is None:
                raise NotFoundError(f"No existe el cargo con id={position_id}.")
            return repo.list_permission_codes(position_id)

    def set_permissions(self, position_id: int, codes: list[str]) -> None:
        valid_codes = {code for code, _label in PERMISSION_CATALOG}
        unknown = set(codes) - valid_codes
        if unknown:
            raise BusinessRuleViolationError(
                f"Código(s) de permiso desconocido(s): {', '.join(sorted(unknown))}."
            )

        with session_scope() as session:
            repo = JobPositionRepository(session)
            position = repo.get_position(position_id)
            if position is None:
                raise NotFoundError(f"No existe el cargo con id={position_id}.")
            if position.grants_full_access:
                raise BusinessRuleViolationError(
                    "El cargo 'Administrador General' ya tiene acceso completo; no "
                    "se le pueden asignar ni restringir permisos individuales."
                )
            repo.replace_permissions(position_id, set(codes))
