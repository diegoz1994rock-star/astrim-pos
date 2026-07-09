"""Jerarquía de excepciones de negocio compartida por todos los módulos.

Ninguna capa `application` debe dejar escapar una excepción de
infraestructura (`sqlalchemy.exc.*`, `PySide6.*`) hacia `presentation`;
siempre debe traducirla a una de estas excepciones de dominio explícitas.
"""

from __future__ import annotations


class DomainError(Exception):
    """Raíz de toda excepción de negocio del sistema."""


class NotFoundError(DomainError):
    """La entidad solicitada no existe."""


class ValidationError(DomainError):
    """Los datos de entrada no cumplen una regla de validación."""


class BusinessRuleViolationError(DomainError):
    """Una regla de negocio (no de validación de forma) impide la operación,
    ej. anular una venta ya facturada, vender más de lo que hay en stock."""


class ConflictError(DomainError):
    """La operación entra en conflicto con el estado actual del sistema,
    ej. un `username` que ya existe, un conflicto de sincronización."""


class AuthenticationError(DomainError):
    """Credenciales inválidas o sesión no autenticada."""


class AccountLockedError(AuthenticationError):
    """La cuenta está bloqueada por múltiples intentos fallidos."""


class PermissionDeniedError(DomainError):
    """El usuario autenticado no tiene el permiso requerido para la acción."""
