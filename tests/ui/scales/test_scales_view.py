"""Pruebas de UI de `ScalesView` (backend `offscreen`): buscador y
columnas — no se ejercitan los diálogos modales (mismo motivo ya
documentado en `tests/ui/sales/test_sale_view.py`)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from pytestqt.qtbot import QtBot

from pos.modules.scales.application.dto import ScaleDeviceConfigDTO
from pos.modules.scales.domain.enums import ConnectionStatus, ConnectionType, UnitOfMeasure
from pos.modules.scales.presentation.scales_view import ScalesView


def _device(
    device_id: int,
    name: str = "Báscula 1",
    brand: str | None = "CAS",
    connection_status: ConnectionStatus = ConnectionStatus.DISCONNECTED,
) -> ScaleDeviceConfigDTO:
    return ScaleDeviceConfigDTO(
        id=device_id,
        name=name,
        kind="generic",
        is_active=True,
        is_default=False,
        brand=brand,
        model="AD-100",
        serial_number="SN123",
        description=None,
        location=None,
        cash_register_id=None,
        station_label=None,
        assigned_user_id=None,
        connection_type=ConnectionType.SERIAL,
        port="COM3",
        baud_rate=9600,
        data_bits=None,
        stop_bits=None,
        parity=None,
        ip_address=None,
        ip_port=None,
        bluetooth_address=None,
        unit_of_measure=UnitOfMeasure.KG,
        decimal_places=3,
        timeout_seconds=2,
        read_frequency_seconds=1,
        auto_read=False,
        stability_required=True,
        min_stable_seconds=Decimal("0.50"),
        auto_reconnect=True,
        current_tare=Decimal("0"),
        simulator_target_weight=None,
        connection_status=connection_status,
        last_successful_communication_at=None,
    )


def _make_view(qtbot: QtBot) -> ScalesView:
    view = ScalesView(Mock())
    qtbot.addWidget(view)
    return view


def test_devices_loaded_populates_table(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._on_devices_loaded([_device(1, "Báscula 1"), _device(2, "Báscula 2")])

    assert view._table.rowCount() == 2


def test_search_filters_by_name(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_devices_loaded([_device(1, "Báscula Mostrador"), _device(2, "Báscula Bodega")])

    view._search_edit.setText("Bodega")

    assert view._table.rowCount() == 1


def test_search_filters_by_brand(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_devices_loaded(
        [_device(1, brand="CAS"), _device(2, "Báscula 2", brand="Torrey")]
    )

    view._search_edit.setText("Torrey")

    assert view._table.rowCount() == 1


def test_cash_register_name_resolved_in_table(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_cash_registers_loaded([(5, "Caja Principal")])
    device = _device(1)
    device = ScaleDeviceConfigDTO(**{**device.__dict__, "cash_register_id": 5})

    view._on_devices_loaded([device])

    assert view._table.item(0, 3).text() == "Caja Principal"
