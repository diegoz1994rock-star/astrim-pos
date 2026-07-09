"""Repositorio de parámetros de configuración del negocio."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos.modules.settings.infrastructure.models import BusinessSetting, SettingValueType


class BusinessSettingsRepository:
    """Acceso a la tabla `business_settings` mediante una `Session` dada."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_all(self) -> list[BusinessSetting]:
        """Devuelve todos los parámetros de configuración almacenados."""
        return list(self._session.scalars(select(BusinessSetting)))

    def get_by_key(self, key: str) -> BusinessSetting | None:
        """Busca un parámetro por su clave única."""
        return self._session.scalar(select(BusinessSetting).where(BusinessSetting.key == key))

    def upsert(self, key: str, value: str | None, value_type: SettingValueType) -> BusinessSetting:
        """Crea o actualiza el parámetro `key` con el valor dado."""
        setting = self.get_by_key(key)
        if setting is None:
            setting = BusinessSetting(key=key, value=value, value_type=value_type)
            self._session.add(setting)
        else:
            setting.value = value
            setting.value_type = value_type
        return setting
