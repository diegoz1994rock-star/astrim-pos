"""Caso de uso: leer y escribir los parámetros de configuración del negocio
editables desde el panel de administración (PROJECT_SPEC.md, "CONFIGURACIÓN").

Cualquier módulo que necesite un parámetro de negocio (nombre, moneda,
logo, etc.) pasa por este servicio, nunca consulta `business_settings`
directamente — así se mantiene una única fuente de verdad para el caché.
"""

from __future__ import annotations

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.modules.settings.domain.events import BusinessSettingChangedEvent
from pos.modules.settings.infrastructure.models import SettingValueType
from pos.modules.settings.infrastructure.repository import BusinessSettingsRepository


class BusinessSettingsService:
    """Lectura con caché en memoria y escritura transaccional de parámetros
    de configuración del negocio."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._cache: dict[str, str | None] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with session_scope() as session:
            repo = BusinessSettingsRepository(session)
            self._cache = {s.key: s.value for s in repo.get_all()}
        self._loaded = True

    def refresh(self) -> None:
        """Fuerza una recarga del caché desde la base de datos."""
        self._loaded = False
        self._ensure_loaded()

    def get_str(self, key: str, default: str | None = None) -> str | None:
        """Devuelve el valor de `key` como texto, o `default` si no existe."""
        self._ensure_loaded()
        return self._cache.get(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Devuelve el valor de `key` interpretado como booleano."""
        self._ensure_loaded()
        raw = self._cache.get(key)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    def get_int(self, key: str, default: int = 0) -> int:
        """Devuelve el valor de `key` interpretado como entero."""
        self._ensure_loaded()
        raw = self._cache.get(key)
        if raw is None:
            return default
        return int(raw)

    def set_value(self, key: str, value: str, value_type: SettingValueType) -> None:
        """Crea o actualiza `key`, persiste la transacción y publica
        `BusinessSettingChangedEvent` para que otros módulos (ej. temas,
        auditoría) reaccionen sin acoplarse a este servicio."""
        with session_scope() as session:
            repo = BusinessSettingsRepository(session)
            repo.upsert(key, value, value_type)

        self._cache[key] = value
        self._event_bus.publish(BusinessSettingChangedEvent(key=key, value=value))
