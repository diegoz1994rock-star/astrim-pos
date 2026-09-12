"""Pruebas unitarias de `domain_error_to_http` (Fase 5) — sin DB, sin Qt.
El caso crítico es el orden de `_STATUS_BY_EXCEPTION_TYPE`:
`AccountLockedError` hereda de `AuthenticationError`, así que debe
resolverse a 423, no al 401 genérico de su clase base."""

from __future__ import annotations

from pos.core.exceptions import (
    AccountLockedError,
    AuthenticationError,
    BusinessRuleViolationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from pos.modules.sync.server.api.errors import domain_error_to_http


def test_not_found_error_maps_to_404() -> None:
    assert domain_error_to_http(NotFoundError("x")).status_code == 404


def test_permission_denied_error_maps_to_403() -> None:
    assert domain_error_to_http(PermissionDeniedError("x")).status_code == 403


def test_conflict_error_maps_to_409() -> None:
    assert domain_error_to_http(ConflictError("x")).status_code == 409


def test_account_locked_error_maps_to_423_not_401() -> None:
    """El caso que justifica el orden explícito del mapeo: sin él,
    `isinstance(exc, AuthenticationError)` calzaría primero (es su clase
    base) y una cuenta bloqueada se reportaría como 401 genérico."""
    assert domain_error_to_http(AccountLockedError("x")).status_code == 423


def test_authentication_error_maps_to_401() -> None:
    assert domain_error_to_http(AuthenticationError("x")).status_code == 401


def test_validation_error_maps_to_422() -> None:
    assert domain_error_to_http(ValidationError("x")).status_code == 422


def test_business_rule_violation_error_maps_to_422() -> None:
    assert domain_error_to_http(BusinessRuleViolationError("x")).status_code == 422


def test_unknown_domain_error_falls_back_to_400() -> None:
    class _CustomDomainError(DomainError):
        pass

    assert domain_error_to_http(_CustomDomainError("x")).status_code == 400


def test_detail_message_is_preserved() -> None:
    exc = NotFoundError("No existe el producto con id=1.")
    assert domain_error_to_http(exc).detail == "No existe el producto con id=1."
