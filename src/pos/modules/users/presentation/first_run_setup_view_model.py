"""View model de la pantalla de configuración inicial (primer arranque:
base de datos recién creada, cero usuarios)."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.core.security.session import ActiveSession
from pos.modules.auth.application.authentication_service import AuthenticationService
from pos.modules.roles.application.role_management_service import RoleManagementService
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.modules.settings.infrastructure.models import SettingValueType
from pos.modules.users.application.user_management_service import UserManagementService

_MIN_PASSWORD_LENGTH = 8


class FirstRunSetupViewModel(QObject):
    setup_completed = Signal(object)
    error_occurred = Signal(str)

    def __init__(
        self,
        role_service: RoleManagementService,
        user_service: UserManagementService,
        settings_service: BusinessSettingsService,
        auth_service: AuthenticationService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._role_service = role_service
        self._user_service = user_service
        self._settings_service = settings_service
        self._auth_service = auth_service

    def complete_setup(
        self,
        *,
        business_name: str,
        admin_username: str,
        admin_full_name: str,
        admin_password: str,
        admin_password_confirm: str,
    ) -> None:
        """Crea los roles/permisos base, la cuenta de administrador y deja
        la sesión iniciada — el operador nunca ve un login vacío en el
        primer arranque, pasa directo a la app ya autenticado."""
        if admin_password != admin_password_confirm:
            self.error_occurred.emit("Las contraseñas no coinciden.")
            return
        if len(admin_password) < _MIN_PASSWORD_LENGTH:
            self.error_occurred.emit(
                f"La contraseña debe tener al menos {_MIN_PASSWORD_LENGTH} caracteres."
            )
            return

        try:
            admin_role_id = self._role_service.ensure_system_defaults()
            self._user_service.create_user(
                username=admin_username,
                password=admin_password,
                full_name=admin_full_name,
                role_id=admin_role_id,
            )
            if business_name.strip():
                self._settings_service.set_value(
                    "business_name", business_name.strip(), SettingValueType.STRING
                )
            session: ActiveSession = self._auth_service.login(admin_username, admin_password)
        except DomainError as error:
            self.error_occurred.emit(str(error))
            return

        self.setup_completed.emit(session)
