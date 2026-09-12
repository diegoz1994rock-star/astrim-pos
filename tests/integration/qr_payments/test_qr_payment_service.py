"""Pruebas de integración de `QrPaymentService` contra SQLite real."""

from __future__ import annotations

import pytest

from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.qr_payments.application.qr_payment_service import QrPaymentService


def test_create_config_becomes_default_automatically(sqlite_engine: None) -> None:
    service = QrPaymentService()

    config = service.create_config(name="QR Principal", image_path="/tmp/qr.png")

    assert config.is_default is True
    assert config.is_active is True
    assert config.image_path == "/tmp/qr.png"


def test_second_config_is_not_default_automatically(sqlite_engine: None) -> None:
    service = QrPaymentService()
    service.create_config(name="QR Principal", image_path=None)

    second = service.create_config(name="QR Secundario", image_path=None)

    assert second.is_default is False


def test_create_config_with_duplicate_name_is_rejected(sqlite_engine: None) -> None:
    service = QrPaymentService()
    service.create_config(name="QR Principal", image_path=None)

    with pytest.raises(ConflictError):
        service.create_config(name="QR Principal", image_path=None)


def test_create_config_requires_name(sqlite_engine: None) -> None:
    service = QrPaymentService()

    with pytest.raises(BusinessRuleViolationError):
        service.create_config(name="   ", image_path=None)


def test_update_config_persists_new_image(sqlite_engine: None) -> None:
    service = QrPaymentService()
    config = service.create_config(name="QR Principal", image_path=None)

    updated = service.update_config(config.id, name="QR Principal", image_path="/tmp/new.png")

    assert updated.image_path == "/tmp/new.png"


def test_update_nonexistent_config_raises_not_found(sqlite_engine: None) -> None:
    service = QrPaymentService()

    with pytest.raises(NotFoundError):
        service.update_config(999, name="X", image_path=None)


def test_set_default_config_unsets_previous_default(sqlite_engine: None) -> None:
    service = QrPaymentService()
    first = service.create_config(name="QR Principal", image_path=None)
    second = service.create_config(name="QR Secundario", image_path=None)

    service.set_default(second.id)

    configs = {c.id: c for c in service.list_configs()}
    assert configs[first.id].is_default is False
    assert configs[second.id].is_default is True
    assert service.get_default_config().id == second.id


def test_set_default_config_rejects_inactive_config(sqlite_engine: None) -> None:
    service = QrPaymentService()
    first = service.create_config(name="QR Principal", image_path=None)
    second = service.create_config(name="QR Secundario", image_path=None)
    service.set_active(second.id, False)

    with pytest.raises(BusinessRuleViolationError):
        service.set_default(second.id)

    assert service.get_default_config().id == first.id


def test_deactivating_the_default_config_clears_default_flag(sqlite_engine: None) -> None:
    service = QrPaymentService()
    config = service.create_config(name="QR Principal", image_path=None)

    service.set_active(config.id, False)

    assert service.get_default_config() is None
    configs = {c.id: c for c in service.list_configs()}
    assert configs[config.id].is_default is False
    assert configs[config.id].is_active is False


def test_delete_config_removes_it(sqlite_engine: None) -> None:
    service = QrPaymentService()
    config = service.create_config(name="QR Principal", image_path=None)

    service.delete_config(config.id)

    assert service.list_configs() == []
