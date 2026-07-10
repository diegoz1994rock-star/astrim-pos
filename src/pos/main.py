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
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.cash_register.presentation.cash_register_view import CashRegisterView
from pos.modules.cash_register.presentation.cash_register_view_model import (
    CashRegisterViewModel,
)
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.customers.presentation.customers_view import CustomersView
from pos.modules.customers.presentation.customers_view_model import CustomersViewModel
from pos.modules.inventory.application.event_handlers import InventoryProductEventHandlers
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.inventory.presentation.inventory_view import InventoryView
from pos.modules.inventory.presentation.inventory_view_model import InventoryViewModel
from pos.modules.products.application.category_service import CategoryManagementService
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.products.domain.events import ProductCreatedEvent
from pos.modules.products.presentation.categories_view import CategoriesView
from pos.modules.products.presentation.categories_view_model import CategoriesViewModel
from pos.modules.products.presentation.products_view import ProductsView
from pos.modules.products.presentation.products_view_model import ProductsViewModel
from pos.modules.reports.application.reports_service import ReportsService
from pos.modules.reports.presentation.reports_view import ReportsView
from pos.modules.reports.presentation.reports_view_model import ReportsViewModel
from pos.modules.roles.application.role_management_service import RoleManagementService
from pos.modules.roles.presentation.roles_view import RolesView
from pos.modules.roles.presentation.roles_view_model import RolesViewModel
from pos.modules.sales.application.sale_service import SalesService
from pos.modules.sales.presentation.sale_view import SaleView
from pos.modules.sales.presentation.sale_view_model import SaleViewModel
from pos.modules.sales.presentation.sales_history_view import SalesHistoryView
from pos.modules.sales.presentation.sales_history_view_model import SalesHistoryViewModel
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.modules.suppliers.application.supplier_service import SupplierManagementService
from pos.modules.suppliers.presentation.suppliers_view import SuppliersView
from pos.modules.suppliers.presentation.suppliers_view_model import SuppliersViewModel
from pos.modules.users.application.user_management_service import UserManagementService
from pos.modules.users.presentation.users_view import UsersView
from pos.modules.users.presentation.users_view_model import UsersViewModel
from pos.shared_ui.theme.theme_manager import ThemeManager


@dataclass(frozen=True)
class NavPanel:
    """Un panel accesible desde la pantalla de bienvenida, visible solo si
    la sesión activa tiene `permission_code`. Agregar un módulo nuevo con
    pantalla propia es agregar una entrada a `_build_nav_panels`, no cablear
    un botón a mano cada vez."""

    label: str
    permission_code: str
    on_click: Callable[[], None]


def bootstrap_core(container: Container) -> BootstrapConfig:
    """Inicializa logging, el engine de base de datos, registra los
    servicios de todos los módulos en el contenedor de DI y conecta los
    manejadores de eventos entre módulos.

    Debe ejecutarse una única vez, antes de construir cualquier ventana.
    Cualquier servicio de aplicación nuevo se registra aquí; `build_main_window`
    y las funciones `_build_*_content` lo resuelven desde `container`, sin
    que cada función nueva tenga que agregar un parámetro más a su firma.
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
    container.register_singleton(InventoryService, lambda: InventoryService(event_bus))
    container.register_singleton(CustomerManagementService, CustomerManagementService)
    container.register_singleton(SupplierManagementService, SupplierManagementService)
    container.register_singleton(
        CashRegisterService, lambda: CashRegisterService(event_bus)
    )
    container.register_singleton(
        SalesService,
        lambda: SalesService(
            event_bus,
            container.resolve(InventoryService),
            container.resolve(CashRegisterService),
            container.resolve(CustomerManagementService),
        ),
    )
    container.register_singleton(
        ReportsService, lambda: ReportsService(container.resolve(InventoryService))
    )

    # Registro de manejadores de eventos entre módulos (ver ARCHITECTURE.md
    # §5): Inventario reacciona a que Productos publique un producto nuevo.
    inventory_handlers = InventoryProductEventHandlers(container.resolve(InventoryService))
    event_bus.subscribe(ProductCreatedEvent, inventory_handlers.on_product_created)

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


def _build_admin_content(container: Container) -> QWidget:
    user_service = container.resolve(UserManagementService)
    role_service = container.resolve(RoleManagementService)
    tabs = QTabWidget()
    tabs.addTab(UsersView(UsersViewModel(user_service, role_service)), "Usuarios")
    tabs.addTab(RolesView(RolesViewModel(role_service)), "Roles y permisos")
    return tabs


def _build_catalog_content(container: Container) -> QWidget:
    product_service = container.resolve(ProductManagementService)
    category_service = container.resolve(CategoryManagementService)
    tabs = QTabWidget()
    tabs.addTab(CategoriesView(CategoriesViewModel(category_service)), "Categorías")
    tabs.addTab(
        ProductsView(ProductsViewModel(product_service, category_service)), "Productos"
    )
    return tabs


def _build_inventory_content(container: Container) -> QWidget:
    inventory_service = container.resolve(InventoryService)
    product_service = container.resolve(ProductManagementService)
    return InventoryView(InventoryViewModel(inventory_service, product_service))


def _build_cash_register_content(container: Container) -> QWidget:
    cash_register_service = container.resolve(CashRegisterService)
    session_manager = container.resolve(SessionManager)
    return CashRegisterView(CashRegisterViewModel(cash_register_service, session_manager))


def _build_sales_content(container: Container) -> QWidget:
    sales_service = container.resolve(SalesService)
    product_service = container.resolve(ProductManagementService)
    customer_service = container.resolve(CustomerManagementService)
    inventory_service = container.resolve(InventoryService)
    cash_register_service = container.resolve(CashRegisterService)
    session_manager = container.resolve(SessionManager)

    tabs = QTabWidget()
    tabs.addTab(
        SaleView(
            SaleViewModel(
                sales_service,
                product_service,
                customer_service,
                inventory_service,
                cash_register_service,
                session_manager,
            )
        ),
        "Nueva venta",
    )
    tabs.addTab(
        SalesHistoryView(
            SalesHistoryViewModel(sales_service, inventory_service, session_manager)
        ),
        "Historial",
    )
    return tabs


def _build_reports_content(container: Container) -> QWidget:
    reports_service = container.resolve(ReportsService)
    return ReportsView(ReportsViewModel(reports_service))


def _build_third_parties_content(container: Container) -> QWidget:
    customer_service = container.resolve(CustomerManagementService)
    supplier_service = container.resolve(SupplierManagementService)
    tabs = QTabWidget()
    tabs.addTab(CustomersView(CustomersViewModel(customer_service)), "Clientes")
    tabs.addTab(SuppliersView(SuppliersViewModel(supplier_service)), "Proveedores")
    return tabs


def _build_nav_panels(
    container: Container, open_panel: Callable[[Callable[[Container], QWidget]], None]
) -> list[NavPanel]:
    """Catálogo de paneles disponibles desde la pantalla de bienvenida.
    Agregar un módulo nuevo con pantalla propia es agregar una línea aquí."""
    return [
        NavPanel("Administración", "users.manage", lambda: open_panel(_build_admin_content)),
        NavPanel("Catálogo", "products.manage", lambda: open_panel(_build_catalog_content)),
        NavPanel(
            "Inventario", "inventory.manage", lambda: open_panel(_build_inventory_content)
        ),
        NavPanel(
            "Clientes y Proveedores",
            "customers.manage",
            lambda: open_panel(_build_third_parties_content),
        ),
        NavPanel(
            "Caja", "cash_register.manage", lambda: open_panel(_build_cash_register_content)
        ),
        NavPanel("Ventas", "sales.create", lambda: open_panel(_build_sales_content)),
        NavPanel("Reportes", "reports.view", lambda: open_panel(_build_reports_content)),
    ]


def build_welcome_widget(
    session: ActiveSession,
    on_logout: Callable[[], None],
    panels: list[NavPanel],
) -> QWidget:
    """Pantalla mostrada tras un login exitoso: bienvenida + un botón por
    cada `NavPanel` cuyo permiso tenga la sesión activa."""
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


def build_main_window(theme_manager: ThemeManager, container: Container) -> QMainWindow:
    """Construye la ventana principal: arranca mostrando el login y, tras
    autenticar, cambia al contenido de la aplicación."""
    theme_manager.apply_light()
    window = QMainWindow()
    window.setWindowTitle("Sistema POS")
    window.resize(1280, 800)
    auth_service = container.resolve(AuthenticationService)

    def show_login() -> None:
        login_view = LoginView(LoginViewModel(auth_service))
        login_view.authenticated.connect(show_welcome)
        window.setCentralWidget(login_view)

    def show_welcome(session: ActiveSession) -> None:
        def handle_logout() -> None:
            auth_service.logout()
            show_login()

        def open_panel(build_content: Callable[[Container], QWidget]) -> None:
            window.setCentralWidget(
                _wrap_with_back_button(
                    build_content(container), on_back=lambda: show_welcome(session)
                )
            )

        panels = _build_nav_panels(container, open_panel)
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

    window = build_main_window(theme_manager, container)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
