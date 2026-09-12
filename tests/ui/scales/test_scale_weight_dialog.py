"""Pruebas de `ScaleWeightDialog` con `ScaleReadService` simulado (`Mock`).

La lectura continua corre en un `ScaleContinuousReadWorker` (hilo real en
background) — para mantener las pruebas deterministas, se detiene el hilo
apenas se crea el diálogo (`_stop_worker`) y se ejercitan directamente los
manejadores privados (`_on_reading`, `_fall_back_to_manual`) con datos
construidos a mano, mismo patrón que `tests/ui/scales/test_scales_view.py`
usa para `_on_devices_loaded`."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.scales.application.dto import WeightReadingDTO
from pos.modules.scales.domain.enums import UnitOfMeasure, WeightEntrySource, WeightReadingStatus
from pos.modules.scales.presentation.scale_weight_dialog import ScaleWeightDialog


def _device_stub(*, auto_read: bool = False, read_frequency_seconds: float = 0.05):
    return SimpleNamespace(
        id=1, auto_read=auto_read, read_frequency_seconds=read_frequency_seconds
    )


def _reading(
    *,
    is_stable: bool = True,
    status: WeightReadingStatus = WeightReadingStatus.STABLE,
    gross: Decimal = Decimal("2.350"),
    net: Decimal = Decimal("2.350"),
    tare: Decimal = Decimal("0"),
) -> WeightReadingDTO:
    return WeightReadingDTO(
        device_id=1,
        device_name="Báscula Simulador",
        gross_weight=gross,
        net_weight=net,
        tare=tare,
        unit=UnitOfMeasure.KG,
        status=status,
        is_stable=is_stable,
        duration_ms=10,
        reconnected=False,
        read_at=datetime.now(UTC),
    )


def _make_dialog(qtbot: QtBot, *, scale_read_service: Mock) -> ScaleWeightDialog:
    dialog = ScaleWeightDialog(
        product_name="Carne molida",
        unit_price=Decimal("20000"),
        unit_of_measure="kg",
        scale_read_service=scale_read_service,
        parent=None,
    )
    qtbot.addWidget(dialog)
    dialog._stop_worker()  # evita que el hilo real siga corriendo durante la prueba
    return dialog


def test_no_scale_configured_falls_back_to_manual_entry(qtbot: QtBot) -> None:
    scale_read_service = Mock()
    scale_read_service.get_active_device.side_effect = BusinessRuleViolationError(
        "No hay ninguna báscula configurada como predeterminada."
    )

    dialog = ScaleWeightDialog(
        product_name="Carne molida",
        unit_price=Decimal("20000"),
        unit_of_measure="kg",
        scale_read_service=scale_read_service,
        parent=None,
    )
    qtbot.addWidget(dialog)

    assert "no disponible" in dialog._status_label.text().lower()
    assert dialog._apply_tare_button.isEnabled() is False
    assert dialog._clear_tare_button.isEnabled() is False


def test_scale_available_enables_tare_buttons(qtbot: QtBot) -> None:
    scale_read_service = Mock()
    scale_read_service.get_active_device.return_value = _device_stub()
    scale_read_service.read.return_value = _reading(is_stable=False)

    dialog = _make_dialog(qtbot, scale_read_service=scale_read_service)

    assert dialog._apply_tare_button.isEnabled() is True
    assert dialog._clear_tare_button.isEnabled() is True


def test_on_reading_stable_populates_weight_field(qtbot: QtBot) -> None:
    scale_read_service = Mock()
    scale_read_service.get_active_device.return_value = _device_stub()
    dialog = _make_dialog(qtbot, scale_read_service=scale_read_service)

    dialog._on_reading(_reading(is_stable=True, net=Decimal("2.350")))

    assert dialog._weight_edit.text() == "2.350"
    assert "estable" in dialog._status_label.text().lower()


def test_on_reading_auto_read_focuses_ok_button_without_closing(qtbot: QtBot) -> None:
    scale_read_service = Mock()
    scale_read_service.get_active_device.return_value = _device_stub(auto_read=True)
    dialog = _make_dialog(qtbot, scale_read_service=scale_read_service)

    dialog._on_reading(_reading(is_stable=True, net=Decimal("1.000")))

    assert dialog._weight_edit.text() == "1.000"
    assert dialog.result() == 0  # el diálogo sigue abierto, no se auto-acepta


def test_on_reading_shows_out_of_range_status(qtbot: QtBot) -> None:
    scale_read_service = Mock()
    scale_read_service.get_active_device.return_value = _device_stub()
    dialog = _make_dialog(qtbot, scale_read_service=scale_read_service)

    dialog._on_reading(
        _reading(is_stable=False, status=WeightReadingStatus.OUT_OF_RANGE)
    )

    assert "rango" in dialog._status_label.text().lower()


def test_apply_tare_updates_labels(qtbot: QtBot) -> None:
    scale_read_service = Mock()
    scale_read_service.get_active_device.return_value = _device_stub()
    scale_read_service.apply_tare.return_value = _reading(
        gross=Decimal("1.200"), net=Decimal("0"), tare=Decimal("1.200")
    )
    dialog = _make_dialog(qtbot, scale_read_service=scale_read_service)

    dialog._on_apply_tare_clicked()

    scale_read_service.apply_tare.assert_called_once_with(1)
    assert dialog._net_label.text() == "Neto: 0 kg"
    dialog._stop_worker()


def test_accept_rejects_zero_weight(qtbot: QtBot, monkeypatch) -> None:
    """Bug preexistente y ajeno a esta entrega: `_on_accept` muestra un
    `QMessageBox.warning` real (modal) para peso cero, que sin mockear
    bloquea la prueba indefinidamente en un entorno sin interacción — se
    mockea acá, mismo patrón que `test_sale_view.py` usa para
    `QMessageBox.question`."""
    monkeypatch.setattr(QMessageBox, "warning", Mock())
    scale_read_service = Mock()
    scale_read_service.get_active_device.return_value = _device_stub()
    dialog = _make_dialog(qtbot, scale_read_service=scale_read_service)
    dialog._weight_edit.setText("0")

    dialog._on_accept()

    assert dialog.result() == 0


def test_accept_accepts_valid_manual_weight(qtbot: QtBot) -> None:
    scale_read_service = Mock()
    scale_read_service.get_active_device.side_effect = BusinessRuleViolationError("sin báscula")
    dialog = ScaleWeightDialog(
        product_name="Carne molida",
        unit_price=Decimal("20000"),
        unit_of_measure="kg",
        scale_read_service=scale_read_service,
        parent=None,
    )
    qtbot.addWidget(dialog)
    dialog._weight_edit.setText("1.750")

    dialog._on_accept()

    assert dialog.weight() == Decimal("1.750")


def test_no_scale_configured_reports_manual_entry_source(qtbot: QtBot) -> None:
    scale_read_service = Mock()
    scale_read_service.get_active_device.side_effect = BusinessRuleViolationError(
        "No hay ninguna báscula configurada como predeterminada."
    )

    dialog = ScaleWeightDialog(
        product_name="Carne molida",
        unit_price=Decimal("20000"),
        unit_of_measure="kg",
        scale_read_service=scale_read_service,
        parent=None,
    )
    qtbot.addWidget(dialog)

    assert dialog.weight_entry_source() is WeightEntrySource.MANUAL


def test_on_reading_stable_reports_scale_entry_source(qtbot: QtBot) -> None:
    scale_read_service = Mock()
    scale_read_service.get_active_device.return_value = _device_stub()
    dialog = _make_dialog(qtbot, scale_read_service=scale_read_service)

    dialog._on_reading(_reading(is_stable=True, net=Decimal("2.350")))

    assert dialog.weight_entry_source() is WeightEntrySource.SCALE


def test_hand_editing_weight_after_stable_reading_reverts_to_manual_source(
    qtbot: QtBot,
) -> None:
    """Si el cajero corrige a mano el peso que la báscula acaba de leer, el
    origen deja de ser `SCALE` — solo `setText` programático (la propia
    lectura) cuenta como automático, nunca una edición real del cajero."""
    scale_read_service = Mock()
    scale_read_service.get_active_device.return_value = _device_stub()
    dialog = _make_dialog(qtbot, scale_read_service=scale_read_service)
    dialog._on_reading(_reading(is_stable=True, net=Decimal("2.350")))
    assert dialog.weight_entry_source() is WeightEntrySource.SCALE

    dialog._weight_edit.setText("2.350")  # setText: no dispara textEdited
    assert dialog.weight_entry_source() is WeightEntrySource.SCALE

    dialog._on_weight_edited_by_hand()  # simula lo que sí dispara textEdited

    assert dialog.weight_entry_source() is WeightEntrySource.MANUAL
