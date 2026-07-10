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
from pos.core.database.migrate import run_pending_migrations
from pos.core.database.session import init_engine
from pos.core.di.container import Container, get_container
from pos.core.events.bus import EventBus, get_event_bus
from pos.core.logging.config import setup_logging
from pos.core.security.session import ActiveSession, SessionManager
from pos.modules.auth.application.authentication_service import AuthenticationService
from pos.modules.auth.presentation.login_view import LoginView
from pos.modules.auth.presentation.login_view_model import LoginViewModel
from pos.modules.backups.application.backup_service import BackupService
from pos.modules.backups.application.scheduler import BackupScheduler
from pos.modules.backups.presentation.backups_view import BackupsView
from pos.modules.backups.presentation.backups_view_model import BackupsViewModel
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
from pos.modules.kitchen.application.kitchen_service import KitchenService
from pos.modules.kitchen.presentation.kitchen_view import KitchenView
from pos.modules.kitchen.presentation.kitchen_view_model import KitchenViewModel
from pos.modules.licensing.application.license_service import LicenseService
from pos.modules.licensing.domain.enums import LicenseVerificationResult
from pos.modules.licensing.infrastructure.embedded_public_key import VENDOR_PUBLIC_KEY_B64
from pos.modules.licensing.presentation.license_view import LicenseView
from pos.modules.licensing.presentation.license_view_model import LicenseViewModel
from pos.modules.products.application.category_service import CategoryManagementService
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.products.domain.events import ProductCreatedEvent
from pos.modules.products.presentation.categories_view import CategoriesView
from pos.modules.products.presentation.categories_view_model import CategoriesViewModel
from pos.modules.products.presentation.products_view import ProductsView
from pos.modules.products.presentation.products_view_model import ProductsViewModel
from pos.modules.promotions.application.promotion_service import PromotionService
from pos.modules.promotions.presentation.promotions_view import PromotionsView
from pos.modules.promotions.presentation.promotions_view_model import PromotionsViewModel
from pos.modules.reports.application.reports_service import ReportsService
from pos.modules.reports.presentation.reports_view import ReportsView
from pos.modules.reports.presentation.reports_view_model import ReportsViewModel
from pos.modules.restaurant.application.restaurant_service import RestaurantService
from pos.modules.restaurant.presentation.restaurant_view import RestaurantView
from pos.modules.restaurant.presentation.restaurant_view_model import RestaurantViewModel
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
from pos.modules.sync.application.sync_service import SyncService
from pos.modules.sync.application.sync_transport import SyncTransport
from pos.modules.sync.presentation.sync_view import SyncView
from pos.modules.sync.presentation.sync_view_model import SyncViewModel
from pos.modules.users.application.user_management_service import UserManagementService
from pos.modules.users.presentation.first_run_setup_view import FirstRunSetupView
from pos.modules.users.presentation.first_run_setup_view_model import FirstRunSetupViewModel
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
    run_pending_migrations(config.database_url)
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
    container.register_singleton(PromotionService, PromotionService)
    container.register_singleton(RestaurantService, RestaurantService)
    container.register_singleton(KitchenService, KitchenService)
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
    container.register_singleton(
        LicenseService, lambda: LicenseService(VENDOR_PUBLIC_KEY_B64, config.data_dir)
    )
    container.register_singleton(
        BackupService,
        lambda: BackupService(config.database_url, config.data_dir / "backups"),
    )
    container.register_singleton(
        SyncService,
        lambda: SyncService(event_bus, container.resolve(BusinessSettingsService)),
    )
    container.register_singleton(
        SyncTransport, lambda: SyncTransport(container.resolve(SyncService))
    )

    # Registro de manejadores de eventos entre módulos (ver ARCHITECTURE.md
    # §5): Inventario reacciona a que Productos publique un producto nuevo.
    inventory_handlers = InventoryProductEventHandlers(container.resolve(InventoryService))
    event_bus.subscribe(ProductCreatedEvent, inventory_handlers.on_product_created)

    # Captura de outbox de Sincronización (ARCHITECTURE.md §10): TODO evento
    # de dominio publicado en el proceso queda registrado como entrada de
    # `sync_log`, sin que cada módulo nuevo tenga que suscribirse a mano.
    event_bus.subscribe_all(container.resolve(SyncService).capture_event)

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


def _build_promotions_content(container: Container) -> QWidget:
    promotion_service = container.resolve(PromotionService)
    return PromotionsView(PromotionsViewModel(promotion_service))


def _build_restaurant_content(container: Container) -> QWidget:
    restaurant_service = container.resolve(RestaurantService)
    product_service = container.resolve(ProductManagementService)
    session_manager = container.resolve(SessionManager)
    return RestaurantView(
        RestaurantViewModel(restaurant_service, product_service, session_manager)
    )


def _build_kitchen_content(container: Container) -> QWidget:
    kitchen_service = container.resolve(KitchenService)
    session_manager = container.resolve(SessionManager)
    return KitchenView(KitchenViewModel(kitchen_service, session_manager))


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
    promotion_service = container.resolve(PromotionService)
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
                promotion_service,
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


def _build_backups_content(container: Container) -> QWidget:
    backup_service = container.resolve(BackupService)
    return BackupsView(BackupsViewModel(backup_service))


def _build_license_content(container: Container) -> QWidget:
    license_service = container.resolve(LicenseService)
    return LicenseView(LicenseViewModel(license_service))


def _build_sync_content(container: Container) -> QWidget:
    transport = container.resolve(SyncTransport)
    return SyncView(SyncViewModel(transport))


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
            "Promociones", "promotions.manage", lambda: open_panel(_build_promotions_content)
        ),
        NavPanel(
            "Restaurante", "restaurant.manage", lambda: open_panel(_build_restaurant_content)
        ),
        NavPanel("Cocina", "kitchen.manage", lambda: open_panel(_build_kitchen_content)),
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
        NavPanel(
            "Licencia", "licensing.manage", lambda: open_panel(_build_license_content)
        ),
        NavPanel("Backups", "backups.manage", lambda: open_panel(_build_backups_content)),
        NavPanel("Sincronización", "sync.manage", lambda: open_panel(_build_sync_content)),
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
    """Construye la ventana principal.

    Arranca verificando la licencia (PROJECT_SPEC.md, "LICENCIAS"): si no
    es válida, bloquea el acceso de forma elegante mostrando la pantalla de
    activación en vez del login — nada de la operación del negocio es
    alcanzable sin una licencia vigente. Si es válida, procede al login
    normalmente.
    """
    theme_manager.apply_light()
    window = QMainWindow()
    window.setWindowTitle("Sistema POS")
    window.resize(1280, 800)
    auth_service = container.resolve(AuthenticationService)
    license_service = container.resolve(LicenseService)
    user_service = container.resolve(UserManagementService)

    def show_login() -> None:
        if user_service.count_users() == 0:
            show_first_run_setup()
            return
        login_view = LoginView(LoginViewModel(auth_service))
        login_view.authenticated.connect(show_welcome)
        window.setCentralWidget(login_view)

    def show_first_run_setup() -> None:
        """Base de datos recién creada (sin usuarios): en vez de un login
        vacío e inutilizable, se pide crear la cuenta de administrador —
        necesario para que el instalador de Windows (ver README.md,
        sección Instalador) entregue una app realmente usable sin depender
        de `scripts/seed_demo_data.py`, que es solo para desarrollo."""
        setup_view_model = FirstRunSetupViewModel(
            container.resolve(RoleManagementService),
            user_service,
            container.resolve(BusinessSettingsService),
            auth_service,
        )
        setup_view = FirstRunSetupView(setup_view_model)
        setup_view.setup_completed.connect(show_welcome)
        window.setCentralWidget(setup_view)

    def show_license_gate() -> None:
        license_view_model = LicenseViewModel(license_service)
        license_view_model.status_changed.connect(
            lambda verification: show_login()
            if verification.result is LicenseVerificationResult.VALID
            else None
        )
        window.setCentralWidget(LicenseView(license_view_model))

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

    initial_verification = license_service.verify()
    if initial_verification.result is LicenseVerificationResult.VALID:
        show_login()
    else:
        show_license_gate()
    return window


def main() -> int:
    """Arranca la aplicación de escritorio."""
    container = get_container()
    bootstrap_core(container)

    app = build_application()
    theme_manager = ThemeManager(app)
    container.register_instance(ThemeManager, theme_manager)

    backup_scheduler = BackupScheduler(container.resolve(BackupService))
    backup_scheduler.start()

    sync_transport = container.resolve(SyncTransport)
    sync_transport.apply_persisted_mode()

    window = build_main_window(theme_manager, container)
    window.show()
    try:
        return app.exec()
    finally:
        backup_scheduler.shutdown()
        sync_transport.shutdown()


if __name__ == "__main__":
    sys.exit(main())
