"""Pruebas de integración de BusinessSettingsService contra SQLite real."""

from __future__ import annotations

from pos.core.events.bus import EventBus
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.modules.settings.domain.events import BusinessSettingChangedEvent
from pos.modules.settings.infrastructure.models import SettingValueType


def test_set_and_get_value_round_trip(sqlite_engine: None) -> None:
    service = BusinessSettingsService(EventBus())

    service.set_value("business_name", "Mi Tienda", SettingValueType.STRING)

    assert service.get_str("business_name") == "Mi Tienda"


def test_get_str_returns_default_when_missing(sqlite_engine: None) -> None:
    service = BusinessSettingsService(EventBus())

    assert service.get_str("no_existe", default="valor_por_defecto") == "valor_por_defecto"


def test_get_bool_parses_stored_string(sqlite_engine: None) -> None:
    service = BusinessSettingsService(EventBus())

    service.set_value("tips_enabled", "true", SettingValueType.BOOLEAN)

    assert service.get_bool("tips_enabled") is True


def test_set_value_persists_across_service_instances(sqlite_engine: None) -> None:
    EventBus()
    BusinessSettingsService(EventBus()).set_value("currency", "COP", SettingValueType.STRING)

    fresh_service = BusinessSettingsService(EventBus())

    assert fresh_service.get_str("currency") == "COP"


def test_set_value_publishes_business_setting_changed_event(sqlite_engine: None) -> None:
    bus = EventBus()
    received: list[BusinessSettingChangedEvent] = []
    bus.subscribe(BusinessSettingChangedEvent, received.append)
    service = BusinessSettingsService(bus)

    service.set_value("business_name", "Mi Tienda", SettingValueType.STRING)

    assert len(received) == 1
    assert received[0].key == "business_name"
    assert received[0].value == "Mi Tienda"
