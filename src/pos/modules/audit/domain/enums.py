"""Enumeraciones de dominio del módulo de auditoría."""

from __future__ import annotations

import enum


class AuditAction(enum.Enum):
    """Tipo de acción registrada en la bitácora de auditoría."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PERMISSION_CHANGE = "permission_change"
    CONFIG_CHANGE = "config_change"
    SALE_VOIDED = "sale_voided"
