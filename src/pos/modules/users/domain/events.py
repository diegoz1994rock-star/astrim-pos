"""Eventos de dominio publicados por el módulo de usuarios."""

from __future__ import annotations

from dataclasses import dataclass

from pos.core.events.event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class UserCreatedEvent(DomainEvent):
    """Se creó un nuevo usuario del sistema."""

    user_id: int
    username: str


@dataclass(frozen=True, kw_only=True)
class UserStatusChangedEvent(DomainEvent):
    """Un usuario fue activado o desactivado."""

    user_id: int
    is_active: bool
