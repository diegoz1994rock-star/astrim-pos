"""View model de la pantalla de login: traduce interacción de UI en
llamadas a `AuthenticationService`, sin que la vista conozca la capa de
aplicación directamente (ver ARCHITECTURE.md §7, MVVM ligero)."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import AccountLockedError, AuthenticationError
from pos.core.security.session import ActiveSession
from pos.modules.auth.application.authentication_service import AuthenticationService


class LoginViewModel(QObject):
    """Estado y comportamiento de la pantalla de login."""

    login_succeeded = Signal(object)
    """Emite la `ActiveSession` resultante al autenticar con éxito."""

    login_failed = Signal(str)
    """Emite el mensaje de error a mostrar al usuario."""

    def __init__(self, auth_service: AuthenticationService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._auth_service = auth_service

    def attempt_login(self, username: str, password: str) -> None:
        """Intenta autenticar con las credenciales dadas y emite la señal
        correspondiente según el resultado."""
        username = username.strip()
        if not username or not password:
            self.login_failed.emit("Ingresa tu usuario y contraseña.")
            return

        try:
            session: ActiveSession = self._auth_service.login(username, password)
        except AccountLockedError as error:
            self.login_failed.emit(str(error))
        except AuthenticationError as error:
            self.login_failed.emit(str(error))
        else:
            self.login_succeeded.emit(session)
