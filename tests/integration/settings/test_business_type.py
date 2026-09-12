"""Pruebas de integración de `business_type` (tipo de negocio) contra SQLite real."""

from __future__ import annotations

from pos.core.events.bus import EventBus
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.modules.settings.domain.business_type import (
    DEFAULT_BUSINESS_TYPE,
    BusinessType,
    get_business_type,
    set_business_type,
)


def test_get_business_type_defaults_when_unset(sqlite_engine: None) -> None:
    service = BusinessSettingsService(EventBus())

    assert get_business_type(service) is DEFAULT_BUSINESS_TYPE


def test_set_and_get_business_type_round_trip(sqlite_engine: None) -> None:
    service = BusinessSettingsService(EventBus())

    set_business_type(service, BusinessType.RESTAURANTE)

    assert get_business_type(service) is BusinessType.RESTAURANTE


def test_get_business_type_falls_back_on_unknown_stored_value(sqlite_engine: None) -> None:
    from pos.modules.settings.domain.business_type import BUSINESS_TYPE_SETTING_KEY
    from pos.modules.settings.infrastructure.models import SettingValueType

    service = BusinessSettingsService(EventBus())
    service.set_value(BUSINESS_TYPE_SETTING_KEY, "no_existe_este_rubro", SettingValueType.STRING)

    assert get_business_type(service) is DEFAULT_BUSINESS_TYPE
