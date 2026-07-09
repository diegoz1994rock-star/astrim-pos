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
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
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
from pos.modules.products.application.category_service import CategoryManagementService
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.products.presentation.categories_view import CategoriesView
from pos.modules.products.presentation.categories_view_model import CategoriesViewModel
from pos.modules.products.presentation.products_view import ProductsView
from pos.modules.products.presentation.products_view_model import ProductsViewModel
from pos.modules.roles.application.role_management_service import RoleManagementService
from pos.modules.roles.presentation.roles_view import RolesView
from pos.modules.roles.presentation.roles_view_model import RolesViewModel
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.modules.users.application.user_management_service import UserManagementService
from pos.modules.users.presentation.users_view import UsersView
from pos.modules.users.presentation.users_view_model import UsersViewModel
from pos.shared_ui.theme.theme_manager import ThemeManager


@dataclass(frozen=True)
class NavPanel:
    """Un panel accesible desde la pantalla de bienvenida, visible solo si
    la sesión activa tiene `permission_code`. Agregar un módulo nuevo con
    pantalla propia es agregar una entrada aquí, no cablear un botón a mano
    cada vez (ver `_build_nav_panels`)."""

    label: str
    permission_code: str
    on_click: Callable[[], None]


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
    container.register_singleton(RoleManagementService, lambda: RoleManagementService(event_bus))
    container.register_singleton(UserManagementService, lambda: UserManagementService(event_bus))
    container.register_singleton(CategoryManagementService, CategoryManagementService)
    container.register_singleton(
        ProductManagementService, lambda: ProductManagementService(event_bus)
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


def _wrap_with_back_button(content: QWidget, on_back: Callable[[], None]) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    back_button = QPushButton("← Volver")
    back_button.clicked.connect(on_back)
    layout.addWidget(back_button)
    layout.addWidget(content)
    return widget


def _build_admin_content(
    user_service: UserManagementService, role_service: RoleManagementService
) -> QWidget:
    tabs = QTabWidget()
    tabs.addTab(UsersView(UsersViewModel(user_service, role_service)), "Usuarios")
    tabs.addTab(RolesView(RolesViewModel(role_service)), "Roles y permisos")
    return tabs


def _build_catalog_content(
    product_service: ProductManagementService, category_service: CategoryManagementService
) -> QWidget:
    tabs = QTabWidget()
    tabs.addTab(CategoriesView(CategoriesViewModel(category_service)), "Categorías")
    tabs.addTab(
        ProductsView(ProductsViewModel(product_service, category_service)), "Productos"
    )
    return tabs


def build_welcome_widget(
    session: ActiveSession,
    on_logout: Callable[[], None],
    panels: list[NavPanel],
) -> QWidget:
    """Pantalla mostrada tras un login exitoso: bienvenida + un botón por
    cada `NavPanel` cuyo permiso tenga la sesión activa. El panel real por
    módulo de negocio (Ventas, Inventario, etc.) se agrega en las
    siguientes etapas de desarrollo, cada uno como una entrada nueva en
    `_build_nav_panels`."""
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
    card_layout.addWidget(welcome_label)

    for panel in panels:
        if session.has_permission(panel.permission_code):
            button = QPushButton(panel.label)
            button.clicked.connect(panel.on_click)
            card_layout.addWidget(button)

    logout_button = QPushButton("Cerrar sesión")
    logout_button.clicked.connect(on_logout)
    card_layout.addWidget(logout_button)

    outer_layout.addWidget(card)

    widget = QWidget()
    widget.setLayout(outer_layout)
    return widget


def build_main_window(
    theme_manager: ThemeManager,
    auth_service: AuthenticationService,
    user_service: UserManagementService,
    role_service: RoleManagementService,
    product_service: ProductManagementService,
    category_service: CategoryManagementService,
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

        def open_panel(build_content: Callable[[], QWidget]) -> None:
            window.setCentralWidget(
                _wrap_with_back_button(build_content(), on_back=lambda: show_welcome(session))
            )

        panels = [
            NavPanel(
                "Administración",
                "users.manage",
                lambda: open_panel(lambda: _build_admin_content(user_service, role_service)),
            ),
            NavPanel(
                "Catálogo",
                "products.manage",
                lambda: open_panel(
                    lambda: _build_catalog_content(product_service, category_service)
                ),
            ),
        ]
        window.setCentralWidget(build_welcome_widget(session, handle_logout, panels))

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
    user_service = container.resolve(UserManagementService)
    role_service = container.resolve(RoleManagementService)
    product_service = container.resolve(ProductManagementService)
    category_service = container.resolve(CategoryManagementService)
    window = build_main_window(
        theme_manager, auth_service, user_service, role_service, product_service, category_service
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
