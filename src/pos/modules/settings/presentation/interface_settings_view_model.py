"""View model de Administración → Configuración de interfaz → Imagen de fondo."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.modules.settings.infrastructure.models import SettingValueType

BACKGROUND_IMAGE_KEY = "dashboard_background_image_path"
"""Clave en `business_settings` — exclusiva del Dashboard principal. Nunca
debe leerse desde `billing`/`invoice_settings` ni desde ningún generador
de documentos imprimibles (factura, recibos, reportes): Configuración de
interfaz y Configuración de factura son módulos completamente separados
— ver el docstring de `invoice_settings/domain/layout_plan.py`."""


class InterfaceSettingsViewModel(QObject):
    background_image_loaded = Signal(str)
    """Emite la ruta configurada, o `""` si no hay ninguna."""
    operation_succeeded = Signal(str)

    def __init__(
        self, settings_service: BusinessSettingsService, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._settings_service = settings_service

    def load(self) -> None:
        self.background_image_loaded.emit(
            self._settings_service.get_str(BACKGROUND_IMAGE_KEY, "") or ""
        )

    def set_background_image(self, path: str) -> None:
        self._settings_service.set_value(BACKGROUND_IMAGE_KEY, path, SettingValueType.STRING)
        self.operation_succeeded.emit("Imagen de fondo actualizada.")
        self.load()

    def clear_background_image(self) -> None:
        self._settings_service.set_value(BACKGROUND_IMAGE_KEY, "", SettingValueType.STRING)
        self.operation_succeeded.emit("Imagen de fondo eliminada.")
        self.load()
