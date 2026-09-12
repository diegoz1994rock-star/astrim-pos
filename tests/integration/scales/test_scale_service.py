"""Pruebas de integración de ScaleService contra SQLite real: CRUD,
predeterminada, y que `read_weight`/`test_connection` fallen con un error
de dominio claro cuando no hay báscula real conectada (siempre el caso en
este entorno) — es justamente ese error el que `ScaleWeightDialog` usa
para caer a ingreso manual del peso."""

from __future__ import annotations

from decimal import Decimal

import pytest

from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.scales.application.scale_service import ScaleService
from pos.modules.scales.domain.enums import ConnectionStatus, ConnectionType, ScaleDeviceEventType


def _make_service() -> ScaleService:
    return ScaleService(EventBus())


def test_create_device_becomes_default_automatically(sqlite_engine: None) -> None:
    service = _make_service()

    device = service.create_device(name="Báscula 1", kind="generic", port="COM3", baud_rate=9600)

    assert device.is_default is True
    assert device.is_active is True


def test_create_device_rejects_empty_name(sqlite_engine: None) -> None:
    service = _make_service()
    with pytest.raises(BusinessRuleViolationError):
        service.create_device(name="  ", kind="generic", port="COM3", baud_rate=9600)


def test_create_device_rejects_empty_port(sqlite_engine: None) -> None:
    service = _make_service()
    with pytest.raises(BusinessRuleViolationError):
        service.create_device(name="Báscula 1", kind="generic", port=" ", baud_rate=9600)


def test_create_device_with_duplicate_name_raises_conflict(sqlite_engine: None) -> None:
    service = _make_service()
    service.create_device(name="Báscula 1", kind="generic", port="COM3", baud_rate=9600)

    with pytest.raises(ConflictError):
        service.create_device(name="Báscula 1", kind="generic", port="COM4", baud_rate=9600)


def test_update_device_changes_fields(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(name="Báscula 1", kind="generic", port="COM3", baud_rate=9600)

    updated = service.update_device(
        device.id, name="Báscula Principal", kind="generic", port="COM4", baud_rate=19200
    )

    assert updated.name == "Báscula Principal"
    assert updated.port == "COM4"
    assert updated.baud_rate == 19200


def test_set_default_device_rejects_inactive(sqlite_engine: None) -> None:
    service = _make_service()
    first = service.create_device(name="Báscula 1", kind="generic", port="COM3", baud_rate=9600)
    second = service.create_device(name="Báscula 2", kind="generic", port="COM4", baud_rate=9600)
    service.set_device_active(second.id, False)

    with pytest.raises(BusinessRuleViolationError):
        service.set_default_device(second.id)

    assert first.is_default is True


def test_set_default_device_clears_previous_default(sqlite_engine: None) -> None:
    service = _make_service()
    first = service.create_device(name="Báscula 1", kind="generic", port="COM3", baud_rate=9600)
    second = service.create_device(name="Báscula 2", kind="generic", port="COM4", baud_rate=9600)

    service.set_default_device(second.id)

    devices = {d.id: d for d in service.list_devices()}
    assert devices[first.id].is_default is False
    assert devices[second.id].is_default is True


def test_delete_device(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(name="Báscula 1", kind="generic", port="COM3", baud_rate=9600)

    service.delete_device(device.id)

    assert service.list_devices() == []


def test_delete_unknown_device_raises_not_found(sqlite_engine: None) -> None:
    service = _make_service()
    with pytest.raises(NotFoundError):
        service.delete_device(9999)


def test_read_weight_without_any_device_raises_business_rule_error(sqlite_engine: None) -> None:
    service = _make_service()
    with pytest.raises(BusinessRuleViolationError):
        service.read_weight()


def test_read_weight_falls_back_when_no_real_scale_connected(sqlite_engine: None) -> None:
    """Sin hardware real conectado (el caso normal en este entorno), leer
    el puerto configurado debe fallar con un error de dominio claro — es
    justamente lo que `ScaleWeightDialog` usa para caer a ingreso manual."""
    service = _make_service()
    service.create_device(
        name="Báscula 1", kind="generic", port="/dev/tty.no-existe-nunca", baud_rate=9600
    )

    with pytest.raises(BusinessRuleViolationError):
        service.read_weight()


def test_test_connection_fails_without_real_hardware(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(
        name="Báscula 1", kind="generic", port="/dev/tty.no-existe-nunca", baud_rate=9600
    )

    with pytest.raises(BusinessRuleViolationError):
        service.test_connection(device.id)


def test_create_device_with_bluetooth_connection_type_is_allowed(sqlite_engine: None) -> None:
    """Se puede registrar el dispositivo con `connection_type=BLUETOOTH`
    (no hay validación de puerto/IP para ese tipo) — lo que no funciona es
    intentar `test_connection`/`read_weight`/tara/calibración contra él,
    ver el siguiente test."""
    service = _make_service()

    device = service.create_device(
        name="Báscula BT", kind="generic", connection_type=ConnectionType.BLUETOOTH
    )

    assert device.connection_type is ConnectionType.BLUETOOTH


def test_test_connection_on_bluetooth_device_raises_explicit_error(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(
        name="Báscula BT", kind="generic", connection_type=ConnectionType.BLUETOOTH
    )

    with pytest.raises(BusinessRuleViolationError, match="adaptador específico del fabricante"):
        service.test_connection(device.id)


def test_create_device_requires_ip_for_ethernet(sqlite_engine: None) -> None:
    service = _make_service()
    with pytest.raises(BusinessRuleViolationError):
        service.create_device(
            name="Báscula ETH", kind="generic", connection_type=ConnectionType.ETHERNET
        )


def test_create_device_with_ethernet_and_ip_succeeds(sqlite_engine: None) -> None:
    service = _make_service()

    device = service.create_device(
        name="Báscula ETH",
        kind="generic",
        connection_type=ConnectionType.ETHERNET,
        ip_address="192.168.1.50",
        ip_port=9100,
    )

    assert device.ip_address == "192.168.1.50"
    assert device.ip_port == 9100


def test_connect_without_real_hardware_sets_error_status(sqlite_engine: None) -> None:
    """No hay báscula real en este entorno — `connect` debe fallar honesto
    y dejar el estado en `ERROR`, nunca simular `CONNECTED`."""
    service = _make_service()
    device = service.create_device(
        name="Báscula 1", kind="generic", port="/dev/tty.no-existe-nunca", baud_rate=9600
    )

    with pytest.raises(BusinessRuleViolationError):
        service.connect(device.id)

    reloaded = next(d for d in service.list_devices() if d.id == device.id)
    assert reloaded.connection_status is ConnectionStatus.ERROR


def test_disconnect_sets_disconnected_status(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(name="Báscula 1", kind="generic", port="COM3", baud_rate=9600)

    updated = service.disconnect(device.id)

    assert updated.connection_status is ConnectionStatus.DISCONNECTED


def test_reset_stale_connections_forces_disconnected(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(name="Báscula 1", kind="generic", port="COM3", baud_rate=9600)
    service.disconnect(device.id)  # deja un evento y estado conocido

    service.reset_stale_connections()

    reloaded = next(d for d in service.list_devices() if d.id == device.id)
    assert reloaded.connection_status is ConnectionStatus.DISCONNECTED


def test_get_capabilities_reflects_generic_adapter_limits(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(name="Báscula 1", kind="generic", port="COM3", baud_rate=9600)

    capabilities = service.get_capabilities(device.id)

    assert capabilities.supports_tare is False
    assert capabilities.supports_calibration is False


def test_tare_raises_when_not_supported_by_adapter(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(name="Báscula 1", kind="generic", port="COM3", baud_rate=9600)

    with pytest.raises(BusinessRuleViolationError, match="no soporta tara"):
        service.tare(device.id)


def test_calibrate_raises_when_not_supported_by_adapter(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(name="Báscula 1", kind="generic", port="COM3", baud_rate=9600)

    with pytest.raises(BusinessRuleViolationError, match="no soporta calibración"):
        service.calibrate(device.id)


def test_list_events_records_test_connection_failures(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(
        name="Báscula 1", kind="generic", port="/dev/tty.no-existe-nunca", baud_rate=9600
    )

    with pytest.raises(BusinessRuleViolationError):
        service.test_connection(device.id)

    events = service.list_events(device.id)
    assert len(events) == 1
    assert events[0].event_type is ScaleDeviceEventType.TEST_CONNECTION_FAILED


def test_list_events_records_disconnect(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(name="Báscula 1", kind="generic", port="COM3", baud_rate=9600)

    service.disconnect(device.id)

    events = service.list_events(device.id)
    assert events[0].event_type is ScaleDeviceEventType.DISCONNECTED


# -- Simulador (modo de pruebas sin hardware) -----------------------------------


def test_create_simulator_device_does_not_require_port(sqlite_engine: None) -> None:
    """A diferencia de USB/Serial, el simulador no exige puerto — se le
    asigna uno interno autogenerado (`SIM-<uuid>`), nunca visible al
    usuario."""
    service = _make_service()

    device = service.create_device(name="Báscula Simulador", kind="simulator")

    assert device.port is not None and device.port.startswith("SIM-")


def test_simulator_device_test_connection_always_succeeds(sqlite_engine: None) -> None:
    """El simulador nunca falla al conectar — no hay hardware real que
    pueda no responder."""
    service = _make_service()
    device = service.create_device(name="Báscula Simulador", kind="simulator")

    assert service.test_connection(device.id) is True


def test_simulator_device_read_weight_returns_configured_target(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(name="Báscula Simulador", kind="simulator")
    service.set_simulator_target_weight(device.id, Decimal("3.000"))

    # La rampa inicial puede traer ruido — leer varias veces converge al
    # peso objetivo exacto (ver `SimulatorScaleProvider`).
    weight = None
    for _ in range(6):
        weight = service.read_weight_for_device(device.id)
    assert weight == Decimal("3.000")


def test_set_simulator_target_weight_rejects_negative(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(name="Báscula Simulador", kind="simulator")

    with pytest.raises(BusinessRuleViolationError):
        service.set_simulator_target_weight(device.id, Decimal("-1"))


def test_set_simulator_target_weight_rejects_non_simulator_device(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(name="Báscula 1", kind="generic", port="COM3", baud_rate=9600)

    with pytest.raises(BusinessRuleViolationError):
        service.set_simulator_target_weight(device.id, Decimal("1.000"))


def test_generic_device_port_still_required_when_kind_changed_via_update(
    sqlite_engine: None,
) -> None:
    """Defensa en profundidad a nivel de servicio (no solo UI): elegir un
    tipo de conexión USB/Serial sigue exigiendo puerto, incluso si el
    dispositivo antes era un simulador."""
    service = _make_service()
    device = service.create_device(name="Báscula Simulador", kind="simulator")

    with pytest.raises(BusinessRuleViolationError):
        service.update_device(
            device.id, name="Báscula Simulador", kind="generic",
            connection_type=ConnectionType.SERIAL, port=None,
        )
