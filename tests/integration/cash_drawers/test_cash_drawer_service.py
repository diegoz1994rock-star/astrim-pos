"""Pruebas de integración de `CashDrawerService` contra SQLite real: CRUD,
un cajón por caja, apertura (automática y manual) exige usuario autenticado
y sesión de caja abierta, historial de auditoría completo, diagnóstico,
reconexión tras un fallo, y concurrencia entre cajas distintas."""

from __future__ import annotations

import threading
from decimal import Decimal

import pytest

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.cash_drawers.domain.enums import (
    CashDrawerEventType,
    CashDrawerOpeningKind,
    ConnectionStatus,
)
from tests.integration.cash_drawers.conftest import CashDrawerFixtures

_NO_HARDWARE_PORT = "/dev/tty.no-existe-nunca"


def _create_minimal_sale() -> int:
    """Fila mínima real de `Sale` — necesaria porque `cash_drawer_events.
    sale_id` es una FK real, no un número arbitrario."""
    from pos.modules.sales.infrastructure.models import Sale

    with session_scope() as session:
        sale = Sale()
        session.add(sale)
        session.flush()
        return sale.id


# -- CRUD / validaciones ---------------------------------------------------------


def test_create_device_rejects_empty_name(cash_drawer_env: CashDrawerFixtures) -> None:
    with pytest.raises(BusinessRuleViolationError):
        cash_drawer_env.service.create_device(name="  ", port="COM3")


def test_create_device_with_duplicate_name_raises_conflict(
    cash_drawer_env: CashDrawerFixtures,
) -> None:
    cash_drawer_env.service.create_device(name="Cajón 1", port="COM3")

    with pytest.raises(ConflictError):
        cash_drawer_env.service.create_device(name="Cajón 1", port="COM4")


def test_delete_unknown_device_raises_not_found(cash_drawer_env: CashDrawerFixtures) -> None:
    with pytest.raises(NotFoundError):
        cash_drawer_env.service.delete_device(9999)


def test_create_device_rejects_invalid_custom_command_hex(
    cash_drawer_env: CashDrawerFixtures,
) -> None:
    with pytest.raises(BusinessRuleViolationError):
        cash_drawer_env.service.create_device(
            name="Cajón 1", port="COM3", custom_command_hex="no-es-hex"
        )


def test_create_device_accepts_valid_custom_command_hex(
    cash_drawer_env: CashDrawerFixtures,
) -> None:
    drawer = cash_drawer_env.service.create_device(
        name="Cajón 1", port="COM3", custom_command_hex="1b70001964"
    )
    assert drawer.custom_command_hex == "1b70001964"


# -- Un cajón por caja ---------------------------------------------------------


def test_only_one_drawer_allowed_per_cash_register(cash_drawer_env: CashDrawerFixtures) -> None:
    cash_drawer_env.service.create_device(
        name="Cajón A", port="COM3", cash_register_id=cash_drawer_env.register_id
    )

    with pytest.raises(ConflictError, match="ya tiene un cajón asignado"):
        cash_drawer_env.service.create_device(
            name="Cajón B", port="COM4", cash_register_id=cash_drawer_env.register_id
        )


def test_two_unassigned_drawers_are_allowed(cash_drawer_env: CashDrawerFixtures) -> None:
    cash_drawer_env.service.create_device(name="Cajón A", port="COM3")
    cash_drawer_env.service.create_device(name="Cajón B", port="COM4")
    # No debe lanzar — ambos sin `cash_register_id` (NULL) son válidos.


def test_update_device_to_already_assigned_register_raises_conflict(
    cash_drawer_env: CashDrawerFixtures,
) -> None:
    cash_drawer_env.service.create_device(
        name="Cajón A", port="COM3", cash_register_id=cash_drawer_env.register_id
    )
    other = cash_drawer_env.service.create_device(name="Cajón B", port="COM4")

    with pytest.raises(ConflictError):
        cash_drawer_env.service.update_device(
            other.id, name="Cajón B", port="COM4", cash_register_id=cash_drawer_env.register_id
        )


# -- Apertura: usuario autenticado + sesión de caja abierta ---------------------


def test_open_drawer_without_user_raises(cash_drawer_env: CashDrawerFixtures) -> None:
    device = cash_drawer_env.service.create_device(name="Cajón 1", port=_NO_HARDWARE_PORT)

    with pytest.raises(BusinessRuleViolationError, match="usuario autenticado"):
        cash_drawer_env.service.open_drawer(device.id, user_id=None)


def test_open_drawer_fails_without_real_hardware(cash_drawer_env: CashDrawerFixtures) -> None:
    device = cash_drawer_env.service.create_device(name="Cajón 1", port=_NO_HARDWARE_PORT)

    with pytest.raises(BusinessRuleViolationError):
        cash_drawer_env.service.open_drawer(device.id, user_id=cash_drawer_env.user_id)


def test_open_drawer_blocked_when_cash_session_closed(
    cash_drawer_env: CashDrawerFixtures,
) -> None:
    device = cash_drawer_env.service.create_device(
        name="Cajón 1", port="COM3", cash_register_id=cash_drawer_env.register_id,
    )
    cash_drawer_env.cash_register_service.close_session(
        cash_session_id=cash_drawer_env.cash_session_id,
        closed_by_user_id=cash_drawer_env.user_id,
        counted_amount=Decimal("50000"),
    )

    with pytest.raises(BusinessRuleViolationError, match="turno de caja abierto"):
        cash_drawer_env.service.open_drawer(device.id, user_id=cash_drawer_env.user_id)


def test_open_drawer_without_assigned_register_skips_session_check(
    cash_drawer_env: CashDrawerFixtures,
) -> None:
    """Un cajón sin caja asignada (uso administrativo/pruebas) no tiene
    sesión que verificar — falla por falta de hardware, no por sesión."""
    device = cash_drawer_env.service.create_device(name="Cajón 1", port=_NO_HARDWARE_PORT)

    with pytest.raises(BusinessRuleViolationError, match="No se pudo abrir"):
        cash_drawer_env.service.open_drawer(device.id, user_id=cash_drawer_env.user_id)


def test_open_drawer_on_inactive_device_raises(cash_drawer_env: CashDrawerFixtures) -> None:
    device = cash_drawer_env.service.create_device(name="Cajón 1", port="COM3")
    cash_drawer_env.service.set_device_active(device.id, False)

    with pytest.raises(BusinessRuleViolationError, match="desactivado"):
        cash_drawer_env.service.open_drawer(device.id, user_id=cash_drawer_env.user_id)


# -- Conexión / diagnóstico --------------------------------------------------------


def test_connect_without_hardware_sets_error_status(cash_drawer_env: CashDrawerFixtures) -> None:
    device = cash_drawer_env.service.create_device(name="Cajón 1", port=_NO_HARDWARE_PORT)

    with pytest.raises(BusinessRuleViolationError):
        cash_drawer_env.service.connect(device.id)

    reloaded = next(d for d in cash_drawer_env.service.list_devices() if d.id == device.id)
    assert reloaded.connection_status is ConnectionStatus.ERROR


def test_reset_stale_connections_forces_disconnected(cash_drawer_env: CashDrawerFixtures) -> None:
    device = cash_drawer_env.service.create_device(name="Cajón 1", port="COM3")
    cash_drawer_env.service.disconnect(device.id)

    cash_drawer_env.service.reset_stale_connections()

    reloaded = next(d for d in cash_drawer_env.service.list_devices() if d.id == device.id)
    assert reloaded.connection_status is ConnectionStatus.DISCONNECTED


def test_open_drawer_for_cash_register_returns_none_without_auto_open_drawer(
    cash_drawer_env: CashDrawerFixtures,
) -> None:
    cash_drawer_env.service.create_device(
        name="Cajón 1", port="COM3", cash_register_id=cash_drawer_env.register_id,
        auto_open_after_sale=False,
    )

    result = cash_drawer_env.service.open_drawer_for_cash_register(
        cash_drawer_env.register_id, user_id=cash_drawer_env.user_id
    )

    assert result is None


def test_open_drawer_for_cash_register_raises_when_no_hardware(
    cash_drawer_env: CashDrawerFixtures,
) -> None:
    """Con un cajón configurado para apertura automática pero sin
    hardware real (siempre el caso en este entorno), el intento de
    apertura falla honesto — nunca se finge éxito."""
    cash_drawer_env.service.create_device(
        name="Cajón 1", port=_NO_HARDWARE_PORT, cash_register_id=cash_drawer_env.register_id,
        auto_open_after_sale=True,
    )
    sale_id = _create_minimal_sale()

    with pytest.raises(BusinessRuleViolationError):
        cash_drawer_env.service.open_drawer_for_cash_register(
            cash_drawer_env.register_id, user_id=cash_drawer_env.user_id, sale_id=sale_id,
        )


def test_get_diagnostics_reflects_configuration(cash_drawer_env: CashDrawerFixtures) -> None:
    device = cash_drawer_env.service.create_device(
        name="Cajón 1", port="COM3", brand="Star", model="SMD2-1211",
    )

    diagnostics = cash_drawer_env.service.get_diagnostics(device.id)

    assert diagnostics.connected is False
    assert diagnostics.port == "COM3"
    assert diagnostics.brand == "Star"
    assert diagnostics.model == "SMD2-1211"
    assert diagnostics.total_opens == 0
    assert diagnostics.error_count == 0


def test_get_diagnostics_counts_opens_and_errors(cash_drawer_env: CashDrawerFixtures) -> None:
    device = cash_drawer_env.service.create_device(name="Cajón 1", port=_NO_HARDWARE_PORT)
    with pytest.raises(BusinessRuleViolationError):
        cash_drawer_env.service.open_drawer(device.id, user_id=cash_drawer_env.user_id)
    with pytest.raises(BusinessRuleViolationError):
        cash_drawer_env.service.open_drawer(device.id, user_id=cash_drawer_env.user_id)

    diagnostics = cash_drawer_env.service.get_diagnostics(device.id)

    assert diagnostics.total_opens == 0
    assert diagnostics.error_count == 2
    assert diagnostics.last_error is not None


# -- Historial de auditoría --------------------------------------------------------


def test_list_events_records_open_failure(cash_drawer_env: CashDrawerFixtures) -> None:
    device = cash_drawer_env.service.create_device(name="Cajón 1", port=_NO_HARDWARE_PORT)

    with pytest.raises(BusinessRuleViolationError):
        cash_drawer_env.service.open_drawer(device.id, user_id=cash_drawer_env.user_id)

    events = cash_drawer_env.service.list_events(device.id)
    assert len(events) == 1
    assert events[0].event_type is CashDrawerEventType.OPEN_FAILED


def test_open_drawer_event_records_full_audit_context(
    cash_drawer_env: CashDrawerFixtures,
) -> None:
    device = cash_drawer_env.service.create_device(
        name="Cajón 1", port=_NO_HARDWARE_PORT, cash_register_id=cash_drawer_env.register_id,
    )
    sale_id = _create_minimal_sale()

    with pytest.raises(BusinessRuleViolationError):
        cash_drawer_env.service.open_drawer(
            device.id, user_id=cash_drawer_env.user_id, username="cajero_cajon",
            opening_kind=CashDrawerOpeningKind.AUTOMATIC, sale_id=sale_id,
            reason="Venta en efectivo",
        )

    event = cash_drawer_env.service.list_events(device.id)[0]
    assert event.user_id == cash_drawer_env.user_id
    assert event.username == "cajero_cajon"
    assert event.cash_register_id == cash_drawer_env.register_id
    assert event.cash_register_name is not None
    assert event.workstation is not None
    assert event.opening_kind is CashDrawerOpeningKind.AUTOMATIC
    assert event.sale_id == sale_id
    assert event.reason == "Venta en efectivo"
    assert event.port_used == _NO_HARDWARE_PORT
    assert event.response_time_ms is not None


def test_manual_open_records_manual_opening_kind_and_reason(
    cash_drawer_env: CashDrawerFixtures,
) -> None:
    device = cash_drawer_env.service.create_device(name="Cajón 1", port=_NO_HARDWARE_PORT)

    with pytest.raises(BusinessRuleViolationError):
        cash_drawer_env.service.open_drawer(
            device.id, user_id=cash_drawer_env.user_id,
            opening_kind=CashDrawerOpeningKind.MANUAL, reason="Vuelto para cliente",
        )

    event = cash_drawer_env.service.list_events(device.id)[0]
    assert event.opening_kind is CashDrawerOpeningKind.MANUAL
    assert event.reason == "Vuelto para cliente"


# -- Recuperación tras un fallo / reintentos ----------------------------------------


def test_retry_after_failed_open_is_allowed_and_recorded_separately(
    cash_drawer_env: CashDrawerFixtures,
) -> None:
    device = cash_drawer_env.service.create_device(name="Cajón 1", port=_NO_HARDWARE_PORT)

    with pytest.raises(BusinessRuleViolationError):
        cash_drawer_env.service.open_drawer(device.id, user_id=cash_drawer_env.user_id)
    with pytest.raises(BusinessRuleViolationError):
        cash_drawer_env.service.open_drawer(device.id, user_id=cash_drawer_env.user_id)

    events = cash_drawer_env.service.list_events(device.id)
    assert len(events) == 2
    assert all(e.event_type is CashDrawerEventType.OPEN_FAILED for e in events)


# -- Concurrencia -----------------------------------------------------------------


def test_concurrent_opens_for_different_registers_do_not_interfere(
    cash_drawer_env: CashDrawerFixtures,
) -> None:
    """Dos cajas distintas, cada una con su propio cajón — abrir ambas al
    mismo tiempo (hilos distintos, cada uno con su propia sesión de BD vía
    `session_scope`) no debe mezclar ni perder eventos."""
    second_register = cash_drawer_env.cash_register_service.create_register(name="Caja 2")
    second_session = cash_drawer_env.cash_register_service.open_session(
        cash_register_id=second_register.id, opened_by_user_id=cash_drawer_env.user_id,
        opening_amount=Decimal("20000"),
    )
    assert second_session.id != cash_drawer_env.cash_session_id

    device_a = cash_drawer_env.service.create_device(
        name="Cajón A", port=_NO_HARDWARE_PORT, cash_register_id=cash_drawer_env.register_id,
    )
    device_b = cash_drawer_env.service.create_device(
        name="Cajón B", port=_NO_HARDWARE_PORT, cash_register_id=second_register.id,
    )

    errors: list[Exception] = []

    def _open(device_id: int) -> None:
        for _ in range(5):
            try:
                cash_drawer_env.service.open_drawer(device_id, user_id=cash_drawer_env.user_id)
            except BusinessRuleViolationError:
                pass
            except Exception as error:  # pragma: no cover - solo para diagnóstico de fallas
                errors.append(error)

    thread_a = threading.Thread(target=_open, args=(device_a.id,))
    thread_b = threading.Thread(target=_open, args=(device_b.id,))
    thread_a.start()
    thread_b.start()
    thread_a.join()
    thread_b.join()

    assert not errors
    assert len(cash_drawer_env.service.list_events(device_a.id)) == 5
    assert len(cash_drawer_env.service.list_events(device_b.id)) == 5
