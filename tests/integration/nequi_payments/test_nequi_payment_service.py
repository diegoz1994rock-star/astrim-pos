"""Pruebas de integración de `NequiPaymentService` contra SQLite real."""

from __future__ import annotations

import pytest

from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.nequi_payments.application.nequi_payment_service import NequiPaymentService


def test_create_config_becomes_active_and_default_automatically(sqlite_engine: None) -> None:
    service = NequiPaymentService()

    config = service.create_config(number="3001234567")

    assert config.is_active is True
    assert config.is_default is True


def test_second_config_is_not_active_or_default_automatically(sqlite_engine: None) -> None:
    service = NequiPaymentService()
    service.create_config(number="3001234567")

    second = service.create_config(number="3009876543")

    assert second.is_active is False
    assert second.is_default is False


def test_create_config_with_duplicate_number_is_rejected(sqlite_engine: None) -> None:
    service = NequiPaymentService()
    service.create_config(number="3001234567")

    with pytest.raises(ConflictError):
        service.create_config(number="3001234567")


def test_create_config_requires_number(sqlite_engine: None) -> None:
    service = NequiPaymentService()

    with pytest.raises(BusinessRuleViolationError):
        service.create_config(number="   ")


def test_activating_a_number_deactivates_the_previous_active_number(sqlite_engine: None) -> None:
    service = NequiPaymentService()
    first = service.create_config(number="3001234567")
    second = service.create_config(number="3009876543")

    service.set_active(second.id, True)

    configs = {c.id: c for c in service.list_configs()}
    assert configs[first.id].is_active is False
    assert configs[second.id].is_active is True


def test_deactivating_the_active_number_clears_default_flag(sqlite_engine: None) -> None:
    service = NequiPaymentService()
    config = service.create_config(number="3001234567")

    service.set_active(config.id, False)

    assert service.get_default_config() is None
    configs = {c.id: c for c in service.list_configs()}
    assert configs[config.id].is_default is False


def test_set_default_rejects_inactive_config(sqlite_engine: None) -> None:
    service = NequiPaymentService()
    config = service.create_config(number="3001234567")
    service.set_active(config.id, False)

    with pytest.raises(BusinessRuleViolationError):
        service.set_default(config.id)


def test_update_nonexistent_config_raises_not_found(sqlite_engine: None) -> None:
    service = NequiPaymentService()

    with pytest.raises(NotFoundError):
        service.update_config(999, number="3001234567")


def test_delete_config_removes_it(sqlite_engine: None) -> None:
    service = NequiPaymentService()
    config = service.create_config(number="3001234567")

    service.delete_config(config.id)

    assert service.list_configs() == []
