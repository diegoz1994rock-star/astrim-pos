"""Punto de entrada de la aplicación de escritorio.

Es la raíz de composición (composition root): el único lugar que conoce
todas las piezas del núcleo y las conecta entre sí. Ningún módulo de
negocio debe replicar este cableado — todos reciben sus dependencias ya
resueltas desde aquí (vía el contenedor de DI) o desde el bus de eventos.

Requiere que el esquema de base de datos ya exista (`alembic upgrade head`)
antes del primer arranque; ver README.md.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pos.core.config.bootstrap import BootstrapConfig, load_bootstrap_config
from pos.core.database.session import init_engine
from pos.core.di.container import Container, get_container
from pos.core.events.bus import EventBus, get_event_bus
from pos.core.logging.config import setup_logging
from pos.core.security.session import ActiveSession, SessionManager
from pos.modules.auth.application.authentication_service import AuthenticationService
from pos.modules.auth.presentation.login_view import LoginView
from pos.modules.auth.presentation.login_view_model import LoginViewModel
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.shared_ui.theme.theme_manager import ThemeManager


def bootstrap_core(container: Container) -> BootstrapConfig:
    """Inicializa logging, el engine de base de datos y registra los
    servicios transversales del núcleo en el contenedor de DI.

    Debe ejecutarse una única vez, antes de construir cualquier ventana.
    """
    config = load_bootstrap_config()
    setup_logging(config.log_dir, level=_parse_log_level(config.log_level))
    init_engine(config.database_url)

    event_bus = get_event_bus()
    session_manager = SessionManager()
    container.register_instance(EventBus, event_bus)
    container.register_instance(SessionManager, session_manager)
    container.register_singleton(
        BusinessSettingsService, lambda: BusinessSettingsService(event_bus)
    )
    container.register_singleton(
        AuthenticationService, lambda: AuthenticationService(session_manager, event_bus)
    )
    return config


def _parse_log_level(level_name: str) -> int:
    return logging.getLevelNamesMapping().get(level_name.upper(), logging.INFO)


def build_application() -> QApplication:
    """Crea la instancia de QApplication con metadata básica de la app."""
    app = QApplication(sys.argv)
    app.setApplicationName("Sistema POS")
    app.setOrganizationName("POS")
    return app


def build_welcome_widget(session: ActiveSession, on_logout: Callable[[], None]) -> QWidget:
    """Pantalla temporal mostrada tras un login exitoso.

    Es solo un punto de prueba de extremo a extremo del núcleo (sesión +
    tema + eventos); el panel real por rol (Usuarios, Ventas, etc.) se
    construye módulo por módulo en las siguientes etapas.
    """
    outer_layout = QVBoxLayout()
    outer_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    card = QFrame()
    card.setObjectName("surface")
    card.setFixedWidth(360)
    card_layout = QVBoxLayout(card)
    card_layout.setSpacing(12)
    card_layout.setContentsMargins(32, 32, 32, 32)

    welcome_label = QLabel(f"Bienvenido, {session.full_name}")
    welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    logout_button = QPushButton("Cerrar sesión")
    logout_button.clicked.connect(on_logout)

    card_layout.addWidget(welcome_label)
    card_layout.addWidget(logout_button)
    outer_layout.addWidget(card)

    widget = QWidget()
    widget.setLayout(outer_layout)
    return widget


def build_main_window(
    theme_manager: ThemeManager,
    auth_service: AuthenticationService,
) -> QMainWindow:
    """Construye la ventana principal: arranca mostrando el login y, tras
    autenticar, cambia al contenido de la aplicación."""
    theme_manager.apply_light()
    window = QMainWindow()
    window.setWindowTitle("Sistema POS")
    window.resize(1280, 800)

    def show_login() -> None:
        login_view = LoginView(LoginViewModel(auth_service))
        login_view.authenticated.connect(show_welcome)
        window.setCentralWidget(login_view)

    def show_welcome(session: ActiveSession) -> None:
        def handle_logout() -> None:
            auth_service.logout()
            show_login()

        window.setCentralWidget(build_welcome_widget(session, handle_logout))

    show_login()
    return window


def main() -> int:
    """Arranca la aplicación de escritorio."""
    container = get_container()
    bootstrap_core(container)

    app = build_application()
    theme_manager = ThemeManager(app)
    container.register_instance(ThemeManager, theme_manager)

    auth_service = container.resolve(AuthenticationService)
    window = build_main_window(theme_manager, auth_service)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
