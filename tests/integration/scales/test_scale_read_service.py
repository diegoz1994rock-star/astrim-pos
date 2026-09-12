"""Pruebas de integración de `ScaleReadService` contra SQLite real: lectura
vía el adaptador Simulador (rampa → estable), tara universal por software,
diagnóstico agregado, historial de pesadas, clasificación de rango de
producto, y reconexión automática/errores de comunicación con el
adaptador genérico (sin hardware real)."""

from __future__ import annotations

import time
from decimal import Decimal

import pytest

from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.products.domain.enums import ProductType
from pos.modules.scales.application.scale_read_service import ScaleReadService
from pos.modules.scales.application.scale_service import ScaleService
from pos.modules.scales.domain.enums import WeightReadingStatus

_SETTLE_SLEEP_SECONDS = 0.06


def _make_services() -> tuple[ScaleService, ScaleReadService]:
    event_bus = EventBus()
    scale_service = ScaleService(event_bus)
    product_service = ProductManagementService(event_bus)
    return scale_service, ScaleReadService(scale_service, product_service)


def _make_simulator_device(scale_service: ScaleService, *, target: Decimal = Decimal("2.500")):
    device = scale_service.create_device(
        name="Báscula Simulador",
        kind="simulator",
        min_stable_seconds=Decimal("0.05"),
        decimal_places=3,
    )
    scale_service.set_simulator_target_weight(device.id, target)
    return device


def test_read_via_simulator_eventually_becomes_stable(sqlite_engine: None) -> None:
    scale_service, read_service = _make_services()
    device = _make_simulator_device(scale_service, target=Decimal("2.500"))

    stable_reading = None
    saw_unstable = False
    for _ in range(15):
        reading = read_service.read(device_id=device.id)
        if not reading.is_stable:
            saw_unstable = True
        else:
            stable_reading = reading
            break
        time.sleep(_SETTLE_SLEEP_SECONDS)

    assert saw_unstable, "el simulador debería emitir al menos una lectura inestable (la rampa)"
    assert stable_reading is not None, "la lectura debería estabilizarse dentro de 15 intentos"
    assert stable_reading.net_weight == Decimal("2.500")
    assert stable_reading.status is WeightReadingStatus.STABLE


def test_read_without_any_device_configured_raises(sqlite_engine: None) -> None:
    _, read_service = _make_services()
    with pytest.raises(BusinessRuleViolationError):
        read_service.read()


def test_stability_required_false_skips_stability_wait(sqlite_engine: None) -> None:
    scale_service, read_service = _make_services()
    device = scale_service.create_device(
        name="Báscula Simulador", kind="simulator", stability_required=False,
    )
    scale_service.set_simulator_target_weight(device.id, Decimal("1.000"))

    reading = read_service.read(device_id=device.id)

    assert reading.is_stable is True
    assert reading.status is WeightReadingStatus.STABLE


def test_zero_target_reads_as_zero_status(sqlite_engine: None) -> None:
    scale_service, read_service = _make_services()
    device = scale_service.create_device(name="Báscula Simulador", kind="simulator")

    reading = read_service.read(device_id=device.id)

    assert reading.status is WeightReadingStatus.ZERO


def test_out_of_range_below_product_minimum(sqlite_engine: None) -> None:
    scale_service, read_service = _make_services()
    device = scale_service.create_device(
        name="Báscula Simulador", kind="simulator", stability_required=False,
    )
    scale_service.set_simulator_target_weight(device.id, Decimal("0.050"))

    reading = read_service.read(device_id=device.id, product_min_weight=Decimal("0.100"))

    assert reading.status is WeightReadingStatus.OUT_OF_RANGE


def test_out_of_range_above_product_maximum(sqlite_engine: None) -> None:
    scale_service, read_service = _make_services()
    device = scale_service.create_device(
        name="Báscula Simulador", kind="simulator", stability_required=False,
    )
    scale_service.set_simulator_target_weight(device.id, Decimal("15.000"))

    reading = read_service.read(device_id=device.id, product_max_weight=Decimal("10.000"))

    assert reading.status is WeightReadingStatus.OUT_OF_RANGE


def test_apply_tare_zeroes_net_weight(sqlite_engine: None) -> None:
    scale_service, read_service = _make_services()
    device = _make_simulator_device(scale_service, target=Decimal("1.200"))
    # Deja que el simulador termine la rampa y llegue al peso objetivo exacto.
    for _ in range(6):
        read_service.read(device_id=device.id)
        time.sleep(_SETTLE_SLEEP_SECONDS)

    tare_reading = read_service.apply_tare(device.id)
    assert tare_reading.net_weight == Decimal("0")

    after = read_service.read(device_id=device.id)
    assert after.net_weight == Decimal("0")
    assert after.gross_weight == Decimal("1.200")


def test_clear_tare_restores_gross_as_net(sqlite_engine: None) -> None:
    scale_service, read_service = _make_services()
    device = _make_simulator_device(scale_service, target=Decimal("1.200"))
    for _ in range(6):
        read_service.read(device_id=device.id)
        time.sleep(_SETTLE_SLEEP_SECONDS)
    read_service.apply_tare(device.id)

    read_service.clear_tare(device.id)

    after = read_service.read(device_id=device.id)
    assert after.net_weight == Decimal("1.200")


def test_read_failure_with_generic_adapter_records_history_and_raises(sqlite_engine: None) -> None:
    scale_service, read_service = _make_services()
    device = scale_service.create_device(
        name="Báscula 1", kind="generic", port="/dev/tty.no-existe-nunca", baud_rate=9600,
        auto_reconnect=True,
    )

    with pytest.raises(BusinessRuleViolationError):
        read_service.read(device_id=device.id)

    diagnostics = read_service.get_diagnostics(device.id)
    assert diagnostics.total_reads == 1
    assert diagnostics.error_count == 1
    assert diagnostics.last_error is not None


def test_diagnostics_aggregate_counts_across_reads(sqlite_engine: None) -> None:
    scale_service, read_service = _make_services()
    device = _make_simulator_device(scale_service, target=Decimal("0.500"))
    for _ in range(3):
        read_service.read(device_id=device.id)

    diagnostics = read_service.get_diagnostics(device.id)
    assert diagnostics.total_reads == 3
    assert diagnostics.last_weight is not None


def test_list_recent_reads_includes_product_name(sqlite_engine: None) -> None:
    event_bus = EventBus()
    scale_service = ScaleService(event_bus)
    product_service = ProductManagementService(event_bus)
    read_service = ScaleReadService(scale_service, product_service)
    device = _make_simulator_device(scale_service, target=Decimal("0.750"))
    product = product_service.create_product(
        sku="PESO-1",
        name="Queso Campesino",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("15000"),
        cost_price=Decimal("8000"),
        unit_of_measure="kg",
        track_inventory=False,
    )

    read_service.read(device_id=device.id, product_id=product.id)

    entries = read_service.list_recent_reads(device.id)
    assert len(entries) == 1
    assert entries[0].product_name == "Queso Campesino"


def test_list_recent_reads_without_product_shows_none(sqlite_engine: None) -> None:
    scale_service, read_service = _make_services()
    device = _make_simulator_device(scale_service, target=Decimal("0.750"))

    read_service.read(device_id=device.id)

    entries = read_service.list_recent_reads(device.id)
    assert entries[0].product_name is None
