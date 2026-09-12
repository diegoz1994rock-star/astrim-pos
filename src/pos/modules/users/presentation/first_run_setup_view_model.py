"""View model de la pantalla de configuración inicial (primer arranque:
base de datos recién creada, cero usuarios)."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.core.security.session import ActiveSession
from pos.modules.auth.application.authentication_service import AuthenticationService
from pos.modules.job_positions.application.job_position_management_service import (
    JobPositionManagementService,
)
from pos.modules.job_positions.application.system_bootstrap import (
    ADMIN_AREA_NAME,
    ADMIN_POSITION_NAME,
)
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.modules.settings.domain.business_type import BusinessType, set_business_type
from pos.modules.settings.infrastructure.models import SettingValueType
from pos.modules.users.application.user_management_service import UserManagementService

_MIN_PASSWORD_LENGTH = 8


class FirstRunSetupViewModel(QObject):
    setup_completed = Signal(object)
    error_occurred = Signal(str)

    def __init__(
        self,
        job_position_service: JobPositionManagementService,
        user_service: UserManagementService,
        settings_service: BusinessSettingsService,
        auth_service: AuthenticationService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._job_position_service = job_position_service
        self._user_service = user_service
        self._settings_service = settings_service
        self._auth_service = auth_service

    def complete_setup(
        self,
        *,
        business_name: str,
        business_type: BusinessType,
        admin_username: str,
        admin_full_name: str,
        admin_password: str,
        admin_password_confirm: str,
    ) -> None:
        """Crea la cuenta de administrador (cargo "Administrador General",
        ya sembrado en `bootstrap_core`) y deja la sesión iniciada — el
        operador nunca ve un login vacío en el primer arranque, pasa
        directo a la app ya autenticado."""
        if admin_password != admin_password_confirm:
            self.error_occurred.emit("Las contraseñas no coinciden.")
            return
        if len(admin_password) < _MIN_PASSWORD_LENGTH:
            self.error_occurred.emit(
                f"La contraseña debe tener al menos {_MIN_PASSWORD_LENGTH} caracteres."
            )
            return

        try:
            admin_area = next(
                area
                for area in self._job_position_service.list_areas()
                if area.name == ADMIN_AREA_NAME
            )
            admin_position = next(
                position
                for position in admin_area.positions
                if position.name == ADMIN_POSITION_NAME
            )
            self._user_service.create_user(
                username=admin_username,
                password=admin_password,
                full_name=admin_full_name,
                job_area_id=admin_area.id,
                job_position_id=admin_position.id,
            )
            if business_name.strip():
                self._settings_service.set_value(
                    "business_name", business_name.strip(), SettingValueType.STRING
                )
            set_business_type(self._settings_service, business_type)
            session: ActiveSession = self._auth_service.login(admin_username, admin_password)
        except DomainError as error:
            self.error_occurred.emit(str(error))
            return

        self.setup_completed.emit(session)
