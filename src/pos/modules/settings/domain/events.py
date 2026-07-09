"""Eventos de dominio publicados por el módulo de configuración."""

from __future__ import annotations

from dataclasses import dataclass

from pos.core.events.event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class BusinessSettingChangedEvent(DomainEvent):
    """Se publica cuando un parámetro de configuración del negocio cambia.

    Consumido, por ejemplo, por el módulo de Auditoría para registrar el
    cambio, o por la UI para refrescar el nombre/logo mostrado.
    """

    key: str
    value: str | None
