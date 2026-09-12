"""Pruebas de `AuthorizedDevicesDialog` (backend `offscreen`)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

from pytestqt.qtbot import QtBot

from pos.modules.licensing.application.dto import AuthorizedDeviceDTO
from pos.modules.licensing.domain.enums import DeviceStatus
from pos.modules.licensing.presentation.authorized_devices_dialog import AuthorizedDevicesDialog

_NOW = datetime.now(UTC)


def _device(**overrides) -> AuthorizedDeviceDTO:
    base = dict(
        id=1,
        hardware_fingerprint="abc123",
        device_name="PC-Tienda",
        ip_address="192.168.1.5",
        first_seen_at=_NOW - timedelta(days=10),
        last_seen_at=_NOW,
        status=DeviceStatus.ACTIVE,
        is_current_device=False,
    )
    base.update(overrides)
    return AuthorizedDeviceDTO(**base)


def test_populates_one_row_per_device(qtbot: QtBot) -> None:
    devices = [_device(), _device(id=2, hardware_fingerprint="def456", device_name="PC-Bodega")]
    dialog = AuthorizedDevicesDialog(devices, Mock())
    qtbot.addWidget(dialog)

    assert dialog._table.rowCount() == 2


def test_current_device_row_marks_revoke_button_disabled(qtbot: QtBot) -> None:
    devices = [_device(is_current_device=True)]
    dialog = AuthorizedDevicesDialog(devices, Mock())
    qtbot.addWidget(dialog)

    revoke_button = dialog._table.cellWidget(0, 6)
    assert not revoke_button.isEnabled()
    assert "este equipo" in dialog._table.item(0, 0).text().lower()


def test_other_device_row_allows_revoke(qtbot: QtBot) -> None:
    devices = [_device(is_current_device=False)]
    dialog = AuthorizedDevicesDialog(devices, Mock())
    qtbot.addWidget(dialog)

    revoke_button = dialog._table.cellWidget(0, 6)
    assert revoke_button.isEnabled()


def test_revoked_device_disables_revoke_button(qtbot: QtBot) -> None:
    devices = [_device(status=DeviceStatus.REVOKED, is_current_device=False)]
    dialog = AuthorizedDevicesDialog(devices, Mock())
    qtbot.addWidget(dialog)

    revoke_button = dialog._table.cellWidget(0, 6)
    assert not revoke_button.isEnabled()


def test_clicking_revoke_calls_callback_with_fingerprint_and_closes(qtbot: QtBot) -> None:
    on_revoke = Mock()
    devices = [_device(is_current_device=False)]
    dialog = AuthorizedDevicesDialog(devices, on_revoke)
    qtbot.addWidget(dialog)

    revoke_button = dialog._table.cellWidget(0, 6)
    revoke_button.click()

    on_revoke.assert_called_once_with("abc123")
