"""Pruebas de `LicenseDashboardView` (backend `offscreen`) — alimenta DTOs
sintéticos directamente a los manejadores privados, mismo patrón que
`tests/ui/sync/test_sync_view.py`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from pytestqt.qtbot import QtBot

from pos.modules.licensing.application.dto import (
    AuthorizedDeviceDTO,
    LicenseDTO,
    LicenseHistoryEntryDTO,
    LicenseUsageDTO,
    LicenseVerificationDTO,
)
from pos.modules.licensing.domain.enums import (
    DeviceStatus,
    LicenseHistoryAction,
    LicenseStatus,
    LicenseType,
    LicenseVerificationResult,
)
from pos.modules.licensing.presentation.license_dashboard_view import LicenseDashboardView
from pos.modules.licensing.presentation.license_dashboard_view_model import (
    LicenseDashboardViewModel,
)

_NOW = datetime.now(UTC)


def _license_dto(**overrides) -> LicenseDTO:
    base = dict(
        id=1,
        license_type=LicenseType.ANNUAL,
        issued_at=_NOW - timedelta(days=300),
        expires_at=_NOW + timedelta(days=65),
        status=LicenseStatus.ACTIVE,
        hardware_fingerprint="abc123",
        company_name="Ferretería El Tornillo",
        company_nit="900123456",
        allowed_users=5,
        allowed_branches=2,
        allowed_registers=3,
        max_devices=2,
    )
    base.update(overrides)
    return LicenseDTO(**base)


def _device_dto(**overrides) -> AuthorizedDeviceDTO:
    base = dict(
        id=1,
        hardware_fingerprint="abc123",
        device_name="PC-Tienda",
        ip_address="192.168.1.5",
        first_seen_at=_NOW - timedelta(days=300),
        last_seen_at=_NOW,
        status=DeviceStatus.ACTIVE,
        is_current_device=True,
    )
    base.update(overrides)
    return AuthorizedDeviceDTO(**base)


def _usage_dto(**overrides) -> LicenseUsageDTO:
    base = dict(
        users_used=3,
        users_allowed=5,
        branches_used=1,
        branches_allowed=2,
        registers_used=2,
        registers_allowed=3,
        devices_used=1,
        devices_allowed=2,
        days_remaining=65,
        period_total_days=365,
        period_elapsed_pct=18.0,
    )
    base.update(overrides)
    return LicenseUsageDTO(**base)


def _make_view(qtbot: QtBot) -> tuple[LicenseDashboardView, Mock]:
    vm = Mock(spec=LicenseDashboardViewModel)
    vm.hardware_fingerprint = "abc123"
    view = LicenseDashboardView(vm)
    qtbot.addWidget(view)
    return view, vm


def test_verification_changed_updates_status_badge_and_info_panel(qtbot: QtBot) -> None:
    view, _vm = _make_view(qtbot)

    view._on_verification_changed(
        LicenseVerificationDTO(
            result=LicenseVerificationResult.VALID, license=_license_dto(), details=None
        )
    )

    assert view._status_badge._label.text() == "● Activa"
    assert view._company_label.text() == "Ferretería El Tornillo"
    assert view._nit_label.text() == "900123456"


@pytest.mark.parametrize(
    ("result", "expected_role"),
    [
        (LicenseVerificationResult.EXPIRED, "danger"),
        (LicenseVerificationResult.SUSPENDED, "warning"),
        (LicenseVerificationResult.BLOCKED, "danger"),
        (LicenseVerificationResult.HARDWARE_MISMATCH, "danger"),
    ],
)
def test_verification_changed_maps_result_to_badge_role(
    qtbot: QtBot, result: LicenseVerificationResult, expected_role: str
) -> None:
    view, _vm = _make_view(qtbot)

    view._on_verification_changed(
        LicenseVerificationDTO(result=result, license=_license_dto(), details=None)
    )

    assert view._status_badge._label.property("role") == expected_role


def test_devices_loaded_populates_current_device_panel(qtbot: QtBot) -> None:
    view, _vm = _make_view(qtbot)

    view._on_devices_loaded([_device_dto(), _device_dto(id=2, hardware_fingerprint="def456", is_current_device=False)])

    assert view._device_name_label.text() == "PC-Tienda"
    assert view._device_fingerprint_label.text() == "abc123"
    assert view._view_devices_button.text() == "Ver dispositivos autorizados (2)"


def test_history_loaded_populates_table(qtbot: QtBot) -> None:
    view, _vm = _make_view(qtbot)
    entry = LicenseHistoryEntryDTO(
        id=1,
        occurred_at=_NOW,
        device_name="PC-Tienda",
        ip_address="192.168.1.5",
        status_at_time=LicenseStatus.ACTIVE,
        action=LicenseHistoryAction.ACTIVATED,
        details=None,
    )

    view._on_history_loaded([entry])

    assert view._history_table.rowCount() == 1
    assert view._history_table.item(0, 1).text() == "Activación"


def test_usage_loaded_updates_kpi_cards(qtbot: QtBot) -> None:
    view, _vm = _make_view(qtbot)

    view._on_usage_loaded(_usage_dto())

    assert view._users_card._value_label.text() == "3/5"
    assert view._branches_card._value_label.text() == "1/2"
    assert view._registers_card._value_label.text() == "2/3"
    assert view._devices_card._value_label.text() == "1/2"


def test_usage_loaded_shows_expiry_warning_within_threshold(qtbot: QtBot) -> None:
    view, _vm = _make_view(qtbot)

    view._on_usage_loaded(_usage_dto(days_remaining=10, period_elapsed_pct=97.0))

    assert not view._expiry_warning_label.isHidden()
    assert view._expiry_warning_label.text() == "Tu licencia vence en 10 días."


def test_usage_loaded_hides_expiry_warning_when_far_from_expiring(qtbot: QtBot) -> None:
    view, _vm = _make_view(qtbot)

    view._on_usage_loaded(_usage_dto(days_remaining=65, period_elapsed_pct=18.0))

    assert view._expiry_warning_label.isHidden()


def test_usage_loaded_hides_percentage_bar_for_permanent_license(qtbot: QtBot) -> None:
    view, _vm = _make_view(qtbot)

    view._on_usage_loaded(
        _usage_dto(days_remaining=None, period_total_days=None, period_elapsed_pct=None)
    )

    assert view._percentage_bar.isHidden()
    assert "permanente" in view._period_label.text().lower()


def test_suspended_license_shows_reactivate_button(qtbot: QtBot) -> None:
    view, _vm = _make_view(qtbot)

    view._on_verification_changed(
        LicenseVerificationDTO(
            result=LicenseVerificationResult.SUSPENDED,
            license=_license_dto(status=LicenseStatus.SUSPENDED),
            details=None,
        )
    )

    assert view._suspend_reactivate_button.text() == "Reactivar licencia"
    assert view._suspend_reactivate_button.isEnabled()


def test_blocked_license_disables_block_button(qtbot: QtBot) -> None:
    view, _vm = _make_view(qtbot)

    view._on_verification_changed(
        LicenseVerificationDTO(
            result=LicenseVerificationResult.BLOCKED,
            license=_license_dto(status=LicenseStatus.BLOCKED),
            details=None,
        )
    )

    assert not view._block_button.isEnabled()


def test_connectivity_changed_updates_online_badge(qtbot: QtBot) -> None:
    view, _vm = _make_view(qtbot)

    view._on_connectivity_changed(False)

    assert view._online_badge._label.property("role") == "danger"

    view._on_connectivity_changed(True)

    assert view._online_badge._label.property("role") == "success"


def test_refresh_button_calls_refresh_now(qtbot: QtBot) -> None:
    view, vm = _make_view(qtbot)

    view._refresh_button.click()

    vm.refresh_now.assert_called_once()
