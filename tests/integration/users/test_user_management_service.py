"""Pruebas de integración de UserManagementService contra SQLite real."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.core.security.password import verify_password
from pos.modules.auth.infrastructure.models import UserSession
from pos.modules.job_positions.application.job_position_management_service import (
    JobPositionManagementService,
)
from pos.modules.users.application.user_management_service import UserManagementService
from pos.modules.users.domain.events import UserCreatedEvent, UserStatusChangedEvent
from pos.modules.users.infrastructure.repository import UserRepository


def test_create_user_hashes_password(sqlite_engine: None) -> None:
    service = UserManagementService(EventBus())

    user = service.create_user(
        username="mesero1", password="clave-valida-123", full_name="Mesero Uno"
    )

    assert user.username == "mesero1"
    assert user.is_active is True


def test_created_user_can_authenticate_with_hashed_password(sqlite_engine: None) -> None:
    service = UserManagementService(EventBus())
    service.create_user(
        username="mesero2", password="clave-valida-123", full_name="Mesero Dos"
    )

    with session_scope() as session:
        stored = UserRepository(session).get_by_username("mesero2")
        assert stored is not None
        assert verify_password("clave-valida-123", stored.password_hash)


def test_create_user_with_duplicate_username_raises_conflict(sqlite_engine: None) -> None:
    service = UserManagementService(EventBus())
    service.create_user(username="duplicado", password="clave-valida-123", full_name="A")

    with pytest.raises(ConflictError):
        service.create_user(username="duplicado", password="clave-valida-123", full_name="B")


def test_create_user_with_short_password_is_rejected(sqlite_engine: None) -> None:
    service = UserManagementService(EventBus())

    with pytest.raises(BusinessRuleViolationError):
        service.create_user(username="alguien", password="123", full_name="Alguien")


def test_create_user_with_unknown_job_position_raises_not_found(sqlite_engine: None) -> None:
    service = UserManagementService(EventBus())

    with pytest.raises(NotFoundError):
        service.create_user(
            username="huerfano",
            password="clave-valida-123",
            full_name="Sin cargo",
            job_position_id=9999,
        )


def test_create_user_publishes_user_created_event(sqlite_engine: None) -> None:
    bus = EventBus()
    received: list[UserCreatedEvent] = []
    bus.subscribe(UserCreatedEvent, received.append)
    service = UserManagementService(bus)

    user = service.create_user(
        username="evento1", password="clave-valida-123", full_name="Evento Uno"
    )

    assert len(received) == 1
    assert received[0].user_id == user.id


def test_set_active_false_deactivates_user_and_publishes_event(sqlite_engine: None) -> None:
    bus = EventBus()
    received: list[UserStatusChangedEvent] = []
    bus.subscribe(UserStatusChangedEvent, received.append)
    service = UserManagementService(bus)
    user = service.create_user(
        username="a_desactivar", password="clave-valida-123", full_name="A Desactivar"
    )

    updated = service.set_active(user.id, False)

    assert updated.is_active is False
    assert received[-1].is_active is False


def test_reset_password_changes_hash(sqlite_engine: None) -> None:
    service = UserManagementService(EventBus())
    user = service.create_user(
        username="cambia_clave", password="clave-vieja-123", full_name="Cambia Clave"
    )

    service.reset_password(user.id, "clave-nueva-456")

    with session_scope() as session:
        stored = UserRepository(session).get_user(user.id)
        assert stored is not None
        assert verify_password("clave-nueva-456", stored.password_hash)
        assert not verify_password("clave-vieja-123", stored.password_hash)


def test_list_users_excludes_soft_deleted(sqlite_engine: None) -> None:
    service = UserManagementService(EventBus())
    service.create_user(
        username="visible", password="clave-valida-123", full_name="Visible"
    )

    users = service.list_users()

    assert any(u.username == "visible" for u in users)


def test_count_users_is_zero_on_a_fresh_database(sqlite_engine: None) -> None:
    service = UserManagementService(EventBus())

    assert service.count_users() == 0


def test_count_users_reflects_created_users(sqlite_engine: None) -> None:
    service = UserManagementService(EventBus())
    service.create_user(
        username="contado", password="clave-valida-123", full_name="Contado"
    )

    assert service.count_users() == 1


def test_create_user_with_job_area_and_position_persists_and_round_trips(
    sqlite_engine: None,
) -> None:
    job_position_service = JobPositionManagementService()
    area = job_position_service.create_area(name="Ventas y Atención al Cliente")
    position = job_position_service.create_position(area_id=area.id, name="Cajero")
    service = UserManagementService(EventBus())

    user = service.create_user(
        username="con_cargo",
        password="clave-valida-123",
        full_name="Con Cargo",
        job_area_id=area.id,
        job_position_id=position.id,
    )

    assert user.job_area_id == area.id
    assert user.job_area_name == "Ventas y Atención al Cliente"
    assert user.job_position_id == position.id
    assert user.job_position_name == "Cajero"

    listed = next(u for u in service.list_users() if u.id == user.id)
    assert listed.job_area_name == "Ventas y Atención al Cliente"
    assert listed.job_position_name == "Cajero"


def test_create_user_with_mismatched_area_and_position_raises_business_rule_violation(
    sqlite_engine: None,
) -> None:
    job_position_service = JobPositionManagementService()
    sales_area = job_position_service.create_area(name="Ventas y Atención al Cliente")
    kitchen_area = job_position_service.create_area(name="Cocina y Alimentos")
    cook_position = job_position_service.create_position(area_id=kitchen_area.id, name="Cocinero")
    service = UserManagementService(EventBus())

    with pytest.raises(BusinessRuleViolationError):
        service.create_user(
            username="area_incorrecta",
            password="clave-valida-123",
            full_name="Área Incorrecta",
            job_area_id=sales_area.id,
            job_position_id=cook_position.id,
        )


def _create_admin_position(job_position_service: JobPositionManagementService):
    area = job_position_service.create_area(name="Administración")
    return area, job_position_service.create_position(
        area_id=area.id, name="Administrador General"
    )


def _force_grants_full_access(position_id: int) -> None:
    """Los tests no pueden pedirle a `JobPositionManagementService` que
    marque `grants_full_access` (no hay endpoint público para eso, solo lo
    hace el seed de "Administrador General") — se fuerza directo por ORM."""
    from pos.modules.job_positions.infrastructure.models import JobPosition

    with session_scope() as session:
        position = session.get(JobPosition, position_id)
        assert position is not None
        position.grants_full_access = True


def test_delete_user_removes_it(sqlite_engine: None) -> None:
    service = UserManagementService(EventBus())
    user = service.create_user(
        username="a_borrar", password="clave-valida-123", full_name="A Borrar"
    )

    service.delete_user(user.id)

    with session_scope() as session:
        assert UserRepository(session).get_user(user.id) is None


def test_delete_user_with_business_history_deactivates_instead_of_failing(
    sqlite_engine: None,
) -> None:
    """"Eliminar" nunca debe fallar: si hay historial real (acá, una fila
    en `user_sessions` con FK NOT NULL sin `ondelete`), en vez de lanzar
    se desactiva y se excluye de `list_users`, sin perder el historial."""
    service = UserManagementService(EventBus())
    user = service.create_user(
        username="con_historial", password="clave-valida-123", full_name="Con Historial"
    )
    with session_scope() as session:
        session.add(
            UserSession(
                user_id=user.id,
                token="tok-1",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )

    service.delete_user(user.id)

    with session_scope() as session:
        stored = UserRepository(session).get_user(user.id)
        assert stored is not None
        assert stored.is_active is False
        assert stored.is_deleted is True
    assert not any(u.username == "con_historial" for u in service.list_users())


def test_delete_sole_administrador_general_is_blocked(sqlite_engine: None) -> None:
    job_position_service = JobPositionManagementService()
    area, position = _create_admin_position(job_position_service)
    _force_grants_full_access(position.id)
    service = UserManagementService(EventBus())
    user = service.create_user(
        username="unico_admin",
        password="clave-valida-123",
        full_name="Único Admin",
        job_area_id=area.id,
        job_position_id=position.id,
    )

    with pytest.raises(BusinessRuleViolationError):
        service.delete_user(user.id)

    with session_scope() as session:
        assert UserRepository(session).get_user(user.id) is not None


def test_delete_administrador_general_succeeds_with_a_second_one(sqlite_engine: None) -> None:
    job_position_service = JobPositionManagementService()
    area, position = _create_admin_position(job_position_service)
    _force_grants_full_access(position.id)
    service = UserManagementService(EventBus())
    first_admin = service.create_user(
        username="admin_uno",
        password="clave-valida-123",
        full_name="Admin Uno",
        job_area_id=area.id,
        job_position_id=position.id,
    )
    service.create_user(
        username="admin_dos",
        password="clave-valida-123",
        full_name="Admin Dos",
        job_area_id=area.id,
        job_position_id=position.id,
    )

    service.delete_user(first_admin.id)

    with session_scope() as session:
        assert UserRepository(session).get_user(first_admin.id) is None


def test_create_user_persists_new_profile_fields(sqlite_engine: None) -> None:
    service = UserManagementService(EventBus())

    user = service.create_user(
        username="con_perfil",
        password="clave-valida-123",
        full_name="Con Perfil",
        emergency_phone="3000000000",
        blood_type="O+",
        address="Calle Falsa 123",
    )

    assert user.emergency_phone == "3000000000"
    assert user.blood_type == "O+"
    assert user.address == "Calle Falsa 123"


def test_update_user_changes_fields(sqlite_engine: None) -> None:
    service = UserManagementService(EventBus())
    user = service.create_user(
        username="editable", password="clave-valida-123", full_name="Nombre Original"
    )

    updated = service.update_user(
        user.id,
        username="editable",
        full_name="Nombre Actualizado",
        email="nuevo@correo.com",
        emergency_phone="3111111111",
        blood_type="A-",
        address="Nueva Dirección 456",
    )

    assert updated.full_name == "Nombre Actualizado"
    assert updated.email == "nuevo@correo.com"
    assert updated.emergency_phone == "3111111111"
    assert updated.blood_type == "A-"
    assert updated.address == "Nueva Dirección 456"


def test_update_user_with_duplicate_username_raises_conflict(sqlite_engine: None) -> None:
    service = UserManagementService(EventBus())
    service.create_user(username="ya_existe", password="clave-valida-123", full_name="Uno")
    user_b = service.create_user(username="otro", password="clave-valida-123", full_name="Dos")

    with pytest.raises(ConflictError):
        service.update_user(user_b.id, username="ya_existe", full_name="Dos")


def test_update_user_keeps_own_username(sqlite_engine: None) -> None:
    """Actualizar un usuario sin cambiar su propio username no debe
    disparar el chequeo de duplicado contra sí mismo."""
    service = UserManagementService(EventBus())
    user = service.create_user(
        username="mismo_nombre", password="clave-valida-123", full_name="Original"
    )

    updated = service.update_user(user.id, username="mismo_nombre", full_name="Actualizado")

    assert updated.full_name == "Actualizado"


def test_update_unknown_user_raises_not_found(sqlite_engine: None) -> None:
    service = UserManagementService(EventBus())

    with pytest.raises(NotFoundError):
        service.update_user(9999, username="x", full_name="X")


def test_add_list_and_delete_document(sqlite_engine: None, tmp_path) -> None:
    service = UserManagementService(EventBus())
    user = service.create_user(
        username="con_documentos", password="clave-valida-123", full_name="Con Documentos"
    )
    source_file = tmp_path / "hoja_de_vida.pdf"
    source_file.write_text("contenido de prueba")

    document = service.add_document(user.id, str(source_file))

    assert document.original_filename == "hoja_de_vida.pdf"
    documents = service.list_documents(user.id)
    assert len(documents) == 1
    assert documents[0].id == document.id

    service.delete_document(document.id)

    assert service.list_documents(user.id) == []


def test_add_document_to_unknown_user_raises_not_found(sqlite_engine: None, tmp_path) -> None:
    service = UserManagementService(EventBus())
    source_file = tmp_path / "archivo.txt"
    source_file.write_text("x")

    with pytest.raises(NotFoundError):
        service.add_document(9999, str(source_file))


def test_deleting_user_cascades_its_documents(sqlite_engine: None, tmp_path) -> None:
    service = UserManagementService(EventBus())
    user = service.create_user(
        username="a_borrar_con_docs", password="clave-valida-123", full_name="A Borrar"
    )
    source_file = tmp_path / "documento.txt"
    source_file.write_text("contenido")
    service.add_document(user.id, str(source_file))

    service.delete_user(user.id)

    with session_scope() as session:
        from pos.modules.users.infrastructure.models import UserDocument

        remaining = session.query(UserDocument).filter_by(user_id=user.id).count()
        assert remaining == 0
