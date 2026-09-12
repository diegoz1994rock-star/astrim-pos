"""Pruebas de integración de JobPositionManagementService contra SQLite real."""

from __future__ import annotations

import pytest

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.job_positions.application.job_position_management_service import (
    JobPositionManagementService,
)
from pos.modules.job_positions.application.system_bootstrap import (
    ADMIN_AREA_NAME,
    ADMIN_POSITION_NAME,
    DEFAULT_JOB_CATALOG,
    ensure_admin_position,
    ensure_default_job_catalog,
)
from pos.modules.job_positions.infrastructure.repository import JobPositionRepository
from pos.modules.users.infrastructure.models import User


def test_create_area(sqlite_engine: None) -> None:
    service = JobPositionManagementService()

    area = service.create_area(name="Ventas y Atención al Cliente")

    assert area.name == "Ventas y Atención al Cliente"
    assert area.positions == ()


def test_create_area_with_empty_name_raises_business_rule_violation(sqlite_engine: None) -> None:
    service = JobPositionManagementService()

    with pytest.raises(BusinessRuleViolationError):
        service.create_area(name="   ")


def test_create_area_with_duplicate_name_raises_conflict(sqlite_engine: None) -> None:
    service = JobPositionManagementService()
    service.create_area(name="Cocina y Alimentos")

    with pytest.raises(ConflictError):
        service.create_area(name="Cocina y Alimentos")


def test_create_position_under_nonexistent_area_raises_not_found(sqlite_engine: None) -> None:
    service = JobPositionManagementService()

    with pytest.raises(NotFoundError):
        service.create_position(area_id=9999, name="Cajero")


def test_create_duplicate_position_in_same_area_raises_conflict(sqlite_engine: None) -> None:
    service = JobPositionManagementService()
    area = service.create_area(name="Ventas y Atención al Cliente")
    service.create_position(area_id=area.id, name="Cajero")

    with pytest.raises(ConflictError):
        service.create_position(area_id=area.id, name="Cajero")


def test_same_position_name_allowed_in_different_areas(sqlite_engine: None) -> None:
    """Regresión: "Cajero" y "Conductor" existen a propósito en más de un
    área en el catálogo por defecto — la unicidad es por área, no global."""
    service = JobPositionManagementService()
    sales_area = service.create_area(name="Ventas y Atención al Cliente")
    pharmacy_area = service.create_area(name="Farmacia")

    sales_cashier = service.create_position(area_id=sales_area.id, name="Cajero")
    pharmacy_cashier = service.create_position(area_id=pharmacy_area.id, name="Cajero")

    assert sales_cashier.id != pharmacy_cashier.id
    assert sales_cashier.name == pharmacy_cashier.name == "Cajero"


def test_delete_area_cascades_its_positions(sqlite_engine: None) -> None:
    service = JobPositionManagementService()
    area = service.create_area(name="Tecnología")
    position = service.create_position(area_id=area.id, name="Desarrollador")

    service.delete_area(area.id)

    with session_scope() as session:
        repo = JobPositionRepository(session)
        assert repo.get_area(area.id) is None
        assert repo.get_position(position.id) is None


def test_delete_position_used_by_a_user_sets_it_to_null(sqlite_engine: None) -> None:
    """Un cargo sin `grants_full_access` no debe bloquear su borrado por
    haber sido asignado a un usuario — ver DATABASE.md,
    `users.job_position_id` con `ON DELETE SET NULL`."""
    service = JobPositionManagementService()
    area = service.create_area(name="Ventas y Atención al Cliente")
    position = service.create_position(area_id=area.id, name="Cajero")

    with session_scope() as session:
        user = User(
            username="cajero_1",
            password_hash="hash-no-relevante",
            full_name="Cajero Uno",
            is_active=True,
            job_area_id=area.id,
            job_position_id=position.id,
        )
        session.add(user)
        session.flush()
        user_id = user.id

    service.delete_position(position.id)

    with session_scope() as session:
        refreshed_user = session.get(User, user_id)
        assert refreshed_user is not None
        assert refreshed_user.job_position_id is None


def test_ensure_default_job_catalog_creates_all_areas_and_positions(sqlite_engine: None) -> None:
    ensure_default_job_catalog()

    with session_scope() as session:
        repo = JobPositionRepository(session)
        areas = repo.list_areas()
        total_positions = sum(len(repo.list_positions_by_area(area.id)) for area in areas)

    assert len(areas) == len(DEFAULT_JOB_CATALOG)
    assert total_positions == sum(len(names) for _, names in DEFAULT_JOB_CATALOG)


def test_ensure_default_job_catalog_is_idempotent(sqlite_engine: None) -> None:
    ensure_default_job_catalog()
    ensure_default_job_catalog()

    with session_scope() as session:
        repo = JobPositionRepository(session)
        areas = repo.list_areas()

    assert len(areas) == len(DEFAULT_JOB_CATALOG)


def test_delete_position_with_grants_full_access_is_forbidden(sqlite_engine: None) -> None:
    service = JobPositionManagementService()
    area = service.create_area(name=ADMIN_AREA_NAME)
    position = service.create_position(area_id=area.id, name=ADMIN_POSITION_NAME)
    with session_scope() as session:
        from pos.modules.job_positions.infrastructure.models import JobPosition

        session.get(JobPosition, position.id).grants_full_access = True  # type: ignore[union-attr]

    with pytest.raises(BusinessRuleViolationError):
        service.delete_position(position.id)

    with session_scope() as session:
        assert JobPositionRepository(session).get_position(position.id) is not None


def test_delete_area_containing_grants_full_access_position_is_forbidden(
    sqlite_engine: None,
) -> None:
    service = JobPositionManagementService()
    area = service.create_area(name=ADMIN_AREA_NAME)
    position = service.create_position(area_id=area.id, name=ADMIN_POSITION_NAME)
    with session_scope() as session:
        from pos.modules.job_positions.infrastructure.models import JobPosition

        session.get(JobPosition, position.id).grants_full_access = True  # type: ignore[union-attr]

    with pytest.raises(BusinessRuleViolationError):
        service.delete_area(area.id)

    with session_scope() as session:
        assert JobPositionRepository(session).get_area(area.id) is not None


def test_ensure_admin_position_on_empty_catalog(sqlite_engine: None) -> None:
    ensure_admin_position()

    with session_scope() as session:
        repo = JobPositionRepository(session)
        area = repo.get_area_by_name(ADMIN_AREA_NAME)
        assert area is not None
        position = repo.get_position_by_area_and_name(area.id, ADMIN_POSITION_NAME)
        assert position is not None
        assert position.grants_full_access is True


def test_ensure_admin_position_on_already_populated_catalog(sqlite_engine: None) -> None:
    service = JobPositionManagementService()
    service.create_area(name="Área Personalizada del Usuario")

    ensure_admin_position()

    with session_scope() as session:
        repo = JobPositionRepository(session)
        areas = {area.name for area in repo.list_areas()}
        assert "Área Personalizada del Usuario" in areas
        assert ADMIN_AREA_NAME in areas
        admin_area = repo.get_area_by_name(ADMIN_AREA_NAME)
        assert admin_area is not None
        admin_position = repo.get_position_by_area_and_name(admin_area.id, ADMIN_POSITION_NAME)
        assert admin_position is not None
        assert admin_position.grants_full_access is True
    # No se sembró todo el catálogo por defecto, solo el área personalizada
    # y "Administración" — `ensure_default_job_catalog` ya había decidido
    # no hacer nada porque el catálogo no estaba vacío.
    assert len(areas) == 2


def test_set_and_list_permissions_round_trip(sqlite_engine: None) -> None:
    service = JobPositionManagementService()
    area = service.create_area(name="Ventas y Atención al Cliente")
    position = service.create_position(area_id=area.id, name="Cajero")

    service.set_permissions(position.id, ["sales.create", "cash_register.manage"])

    codes = service.list_permission_codes(position.id)
    assert set(codes) == {"sales.create", "cash_register.manage"}


def test_set_permissions_replaces_previous_set(sqlite_engine: None) -> None:
    service = JobPositionManagementService()
    area = service.create_area(name="Ventas y Atención al Cliente")
    position = service.create_position(area_id=area.id, name="Cajero")
    service.set_permissions(position.id, ["sales.create", "cash_register.manage"])

    service.set_permissions(position.id, ["reports.view"])

    assert service.list_permission_codes(position.id) == ["reports.view"]


def test_set_permissions_with_unknown_code_raises_business_rule_violation(
    sqlite_engine: None,
) -> None:
    service = JobPositionManagementService()
    area = service.create_area(name="Ventas y Atención al Cliente")
    position = service.create_position(area_id=area.id, name="Cajero")

    with pytest.raises(BusinessRuleViolationError):
        service.set_permissions(position.id, ["codigo.inexistente"])


def test_set_permissions_on_nonexistent_position_raises_not_found(sqlite_engine: None) -> None:
    service = JobPositionManagementService()

    with pytest.raises(NotFoundError):
        service.set_permissions(9999, ["sales.create"])


def test_set_permissions_on_grants_full_access_position_is_forbidden(
    sqlite_engine: None,
) -> None:
    service = JobPositionManagementService()
    area = service.create_area(name=ADMIN_AREA_NAME)
    position = service.create_position(area_id=area.id, name=ADMIN_POSITION_NAME)
    with session_scope() as session:
        from pos.modules.job_positions.infrastructure.models import JobPosition

        session.get(JobPosition, position.id).grants_full_access = True  # type: ignore[union-attr]

    with pytest.raises(BusinessRuleViolationError):
        service.set_permissions(position.id, ["sales.create"])


def test_list_available_permissions_matches_catalog(sqlite_engine: None) -> None:
    from pos.modules.job_positions.domain.permission_catalog import PERMISSION_CATALOG

    service = JobPositionManagementService()

    assert service.list_available_permissions() == PERMISSION_CATALOG


def test_deleting_position_cascades_its_permissions(sqlite_engine: None) -> None:
    service = JobPositionManagementService()
    area = service.create_area(name="Ventas y Atención al Cliente")
    position = service.create_position(area_id=area.id, name="Cajero")
    service.set_permissions(position.id, ["sales.create"])

    service.delete_position(position.id)

    with session_scope() as session:
        from pos.modules.job_positions.infrastructure.models import JobPositionPermission

        remaining = session.query(JobPositionPermission).filter_by(
            job_position_id=position.id
        ).count()
        assert remaining == 0
