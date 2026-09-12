"""Pruebas de integración de `BreBPaymentService` contra SQLite real."""

from __future__ import annotations

import pytest

from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.bre_b_payments.application.breb_payment_service import BreBPaymentService


def test_create_config_becomes_default_automatically(sqlite_engine: None) -> None:
    service = BreBPaymentService()

    config = service.create_config(key="3001234567")

    assert config.is_default is True
    assert config.is_active is True


def test_second_config_is_not_default_automatically(sqlite_engine: None) -> None:
    service = BreBPaymentService()
    service.create_config(key="3001234567")

    second = service.create_config(key="cliente@correo.com")

    assert second.is_default is False


def test_create_config_with_duplicate_key_is_rejected(sqlite_engine: None) -> None:
    service = BreBPaymentService()
    service.create_config(key="3001234567")

    with pytest.raises(ConflictError):
        service.create_config(key="3001234567")


def test_create_config_requires_key(sqlite_engine: None) -> None:
    service = BreBPaymentService()

    with pytest.raises(BusinessRuleViolationError):
        service.create_config(key="   ")


def test_set_default_config_unsets_previous_default(sqlite_engine: None) -> None:
    service = BreBPaymentService()
    first = service.create_config(key="3001234567")
    second = service.create_config(key="cliente@correo.com")

    service.set_default(second.id)

    configs = {c.id: c for c in service.list_configs()}
    assert configs[first.id].is_default is False
    assert configs[second.id].is_default is True
    assert service.get_default_config().id == second.id


def test_set_default_config_rejects_inactive_config(sqlite_engine: None) -> None:
    service = BreBPaymentService()
    first = service.create_config(key="3001234567")
    second = service.create_config(key="cliente@correo.com")
    service.set_active(second.id, False)

    with pytest.raises(BusinessRuleViolationError):
        service.set_default(second.id)

    assert service.get_default_config().id == first.id


def test_deactivating_the_default_config_clears_default_flag(sqlite_engine: None) -> None:
    service = BreBPaymentService()
    config = service.create_config(key="3001234567")

    service.set_active(config.id, False)

    assert service.get_default_config() is None
    configs = {c.id: c for c in service.list_configs()}
    assert configs[config.id].is_default is False


def test_update_nonexistent_config_raises_not_found(sqlite_engine: None) -> None:
    service = BreBPaymentService()

    with pytest.raises(NotFoundError):
        service.update_config(999, key="3001234567")


def test_delete_config_removes_it(sqlite_engine: None) -> None:
    service = BreBPaymentService()
    config = service.create_config(key="3001234567")

    service.delete_config(config.id)

    assert service.list_configs() == []
