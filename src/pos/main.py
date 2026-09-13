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
import os
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path


class _NullStream:
    """Sustituto seguro para `sys.stdout`/`sys.stderr`/`sys.stdin` cuando
    son `None` — no un archivo redirigido a NUL, literalmente `None`, el
    comportamiento estándar de CPython para un proceso sin consola adjunta
    (idéntico a `pythonw.exe`; ver "Sys.stdout and sys.stderr" en la
    documentación de PyInstaller sobre problemas comunes). El `.exe`
    empaquetado usa `console=False` (`installer/pos.spec`) para no abrir una
    ventana de consola detrás de la GUI, así que esto pasa en cada arranque
    real del cliente — no solo en un caso raro.

    Sin este reemplazo, cualquier librería que asuma un stream real (Uvicorn
    decidiendo si usar colores vía `sys.stdout.isatty()`, `warnings.warn`
    escribiendo a `sys.stderr`, un `print()` de depuración de alguna
    dependencia, etc.) revienta con `AttributeError: 'NoneType' object has
    no attribute '...'` en vez de simplemente no imprimir nada — que es el
    comportamiento correcto para una app sin consola."""

    encoding = "utf-8"

    def write(self, *_args: object, **_kwargs: object) -> int:
        return 0

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return False

    def readable(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def fileno(self) -> int:
        raise OSError("Stream nulo: esta aplicación no tiene consola.")


def _fix_none_streams_for_frozen_app() -> None:
    """Reemplaza `sys.stdout`/`sys.stderr`/`sys.stdin` por `_NullStream`
    cuando son `None` — debe ejecutarse antes de importar cualquier
    dependencia que pueda tocarlos al importarse o al usarse (Uvicorn,
    `logging`, etc.), por eso es lo primero que corre `main.py`."""
    if sys.stdout is None:
        sys.stdout = _NullStream()  # type: ignore[assignment]
    if sys.stderr is None:
        sys.stderr = _NullStream()  # type: ignore[assignment]
    if sys.stdin is None:
        sys.stdin = _NullStream()  # type: ignore[assignment]


_fix_none_streams_for_frozen_app()


def _bundled_resources_dir() -> Path:
    """Resuelve `resources/` tanto en desarrollo (relativo al repo) como
    empaquetado con PyInstaller (`sys._MEIPASS`) — mismo patrón que
    `shared_ui/theme/fonts.py::_resources_fonts_dir`, usado acá para
    encontrar el pool de códigos de licencia pre-generados
    (`resources/licenses_pool.db`, ver `bootstrap_core`)."""
    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base is not None:
        return Path(frozen_base) / "resources"
    return Path(__file__).resolve().parents[2] / "resources"


def _fix_qt_plugin_path() -> None:
    """Apunta Qt a su propia carpeta de plugins vía introspección de
    `PySide6.__file__`, en vez de confiar en la autodetección de Qt.

    En algunos entornos (venvs creados desde el instalador oficial de
    python.org en macOS, entre otros) Qt no localiza sus plugins de
    plataforma (`cocoa`, `windows`, etc.) aunque el archivo exista en el
    wheel — falla con "Could not find the Qt platform plugin" pese a que
    `QPluginLoader` puede cargarlo si se le da la ruta absoluta. Debe
    ejecutarse antes de importar cualquier submódulo de PySide6, porque
    Qt lee estas variables al inicializar la integración de plataforma.
    """
    import PySide6

    qt_dir = Path(PySide6.__file__).parent / "Qt"
    plugins_dir = qt_dir / "plugins"
    os.environ.setdefault("QT_PLUGIN_PATH", str(plugins_dir))
    os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(plugins_dir / "platforms"))


_fix_qt_plugin_path()

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QFrame,
    QGridLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
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
from pos.modules.barcode_scanners.application.barcode_read_service import BarcodeReadService
from pos.modules.barcode_scanners.application.barcode_scanner_service import BarcodeScannerService
from pos.modules.barcode_scanners.presentation.barcode_scanners_view import BarcodeScannersView
from pos.modules.barcode_scanners.presentation.barcode_scanners_view_model import (
    BarcodeScannersViewModel,
)
from pos.modules.billing.application.billing_service import BillingService
from pos.modules.billing.application.receipt_printer import DefaultReceiptPrinter, ReceiptPrinter
from pos.modules.bre_b_payments.application.breb_payment_service import BreBPaymentService
from pos.modules.bre_b_payments.presentation.breb_payment_config_view import BreBPaymentConfigView
from pos.modules.bre_b_payments.presentation.breb_payment_config_view_model import (
    BreBPaymentConfigViewModel,
)
from pos.modules.cash_drawers.application.cash_drawer_service import CashDrawerService
from pos.modules.cash_drawers.presentation.cash_drawers_view import CashDrawersView
from pos.modules.cash_drawers.presentation.cash_drawers_view_model import CashDrawersViewModel
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.cash_register.presentation.cash_register_view import CashRegisterView
from pos.modules.cash_register.presentation.cash_register_view_model import (
    CashRegisterViewModel,
)
from pos.modules.cash_register.presentation.cash_registers_view import CashRegistersView
from pos.modules.cash_register.presentation.cash_registers_view_model import (
    CashRegistersViewModel,
)
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.customers.presentation.customers_view import CustomersView
from pos.modules.customers.presentation.customers_view_model import CustomersViewModel
from pos.modules.inventory.application.event_handlers import InventoryProductEventHandlers
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.inventory.presentation.inventory_view import InventoryView
from pos.modules.inventory.presentation.inventory_view_model import InventoryViewModel
from pos.modules.inventory.presentation.warehouses_view import WarehousesView
from pos.modules.inventory.presentation.warehouses_view_model import WarehousesViewModel
from pos.modules.invoice_settings.application.invoice_settings_service import (
    InvoiceSettingsService,
)
from pos.modules.invoice_settings.presentation.invoice_settings_view import InvoiceSettingsView
from pos.modules.invoice_settings.presentation.invoice_settings_view_model import (
    InvoiceSettingsViewModel,
)
from pos.modules.job_positions.application.job_position_management_service import (
    JobPositionManagementService,
)
from pos.modules.job_positions.presentation.job_positions_view import JobPositionsView
from pos.modules.job_positions.presentation.job_positions_view_model import (
    JobPositionsViewModel,
)
from pos.modules.kitchen.application.kitchen_service import KitchenService
from pos.modules.kitchen.presentation.kitchen_view import KitchenView
from pos.modules.kitchen.presentation.kitchen_view_model import KitchenViewModel
from pos.modules.licensing.application.license_service import LicenseService
from pos.modules.licensing.domain.enums import LicenseVerificationResult
from pos.modules.licensing.infrastructure.pool_db import LicensePoolDatabase
from pos.modules.licensing.presentation.license_dashboard_view import LicenseDashboardView
from pos.modules.licensing.presentation.license_dashboard_view_model import (
    LicenseDashboardViewModel,
)
from pos.modules.licensing.presentation.license_view import LicenseView
from pos.modules.licensing.presentation.license_view_model import LicenseViewModel
from pos.modules.nequi_payments.application.nequi_payment_service import NequiPaymentService
from pos.modules.nequi_payments.presentation.nequi_payment_config_view import NequiPaymentConfigView
from pos.modules.nequi_payments.presentation.nequi_payment_config_view_model import (
    NequiPaymentConfigViewModel,
)
from pos.modules.notifications.application.event_handlers import NotificationEventHandlers
from pos.modules.notifications.application.notification_service import NotificationService
from pos.modules.printers.application.printer_service import PrinterService
from pos.modules.printers.presentation.printers_view import PrintersView
from pos.modules.printers.presentation.printers_view_model import PrintersViewModel
from pos.modules.products.application.category_service import CategoryManagementService
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.products.domain.events import ProductCreatedEvent
from pos.modules.products.presentation.categories_view import CategoriesView
from pos.modules.products.presentation.categories_view_model import CategoriesViewModel
from pos.modules.products.presentation.products_view import ProductsView
from pos.modules.products.presentation.products_view_model import ProductsViewModel
from pos.modules.profits.application.profits_service import ProfitsService
from pos.modules.profits.presentation.profits_view import ProfitsView
from pos.modules.qr_payments.application.qr_payment_service import QrPaymentService
from pos.modules.qr_payments.presentation.qr_payment_config_view import QrPaymentConfigView
from pos.modules.qr_payments.presentation.qr_payment_config_view_model import (
    QrPaymentConfigViewModel,
)
from pos.modules.reports.application.reports_service import ReportsService
from pos.modules.reports.presentation.reports_view import ReportsView
from pos.modules.reports.presentation.reports_view_model import ReportsViewModel
from pos.modules.restaurant.application.restaurant_service import RestaurantService
from pos.modules.restaurant.domain.events import OrderCreatedEvent
from pos.modules.restaurant.presentation.restaurant_view import RestaurantView
from pos.modules.restaurant.presentation.restaurant_view_model import RestaurantViewModel
from pos.modules.sales.application.sale_service import SalesService
from pos.modules.sales.presentation.sale_view import SaleView
from pos.modules.sales.presentation.sale_view_model import SaleViewModel
from pos.modules.sales.presentation.sales_history_view import SalesHistoryView
from pos.modules.sales.presentation.sales_history_view_model import SalesHistoryViewModel
from pos.modules.scales.application.scale_read_service import ScaleReadService
from pos.modules.scales.application.scale_service import ScaleService
from pos.modules.scales.presentation.scales_view import ScalesView
from pos.modules.scales.presentation.scales_view_model import ScalesViewModel
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.modules.settings.domain.business_type import BusinessType, get_business_type
from pos.modules.settings.presentation.interface_settings_view import InterfaceSettingsView
from pos.modules.settings.presentation.interface_settings_view_model import (
    BACKGROUND_IMAGE_KEY,
    InterfaceSettingsViewModel,
)
from pos.modules.suppliers.application.supplier_service import SupplierManagementService
from pos.modules.suppliers.presentation.suppliers_view import SuppliersView
from pos.modules.suppliers.presentation.suppliers_view_model import SuppliersViewModel
from pos.modules.sync.application.sync_service import SyncService
from pos.modules.sync.application.sync_transport import SyncTransport
from pos.modules.sync.presentation.audit_log_view import AuditLogView
from pos.modules.sync.presentation.audit_log_view_model import AuditLogViewModel
from pos.modules.sync.presentation.sync_view import SyncView
from pos.modules.sync.presentation.sync_view_model import SyncViewModel
from pos.modules.sync.server.runner import SyncServerStartError
from pos.modules.taxes.application.tax_service import TaxService
from pos.modules.taxes.presentation.taxes_view import TaxesView
from pos.modules.taxes.presentation.taxes_view_model import TaxesViewModel
from pos.modules.users.application.user_management_service import UserManagementService
from pos.modules.users.presentation.first_run_setup_view import FirstRunSetupView
from pos.modules.users.presentation.first_run_setup_view_model import FirstRunSetupViewModel
from pos.modules.users.presentation.users_view import UsersView
from pos.modules.users.presentation.users_view_model import UsersViewModel
from pos.shared_ui.formatting import format_currency
from pos.shared_ui.theme.fonts import load_bundled_fonts
from pos.shared_ui.theme.theme_manager import ThemeManager
from pos.shared_ui.widgets.about_dialog import AboutDialog
from pos.shared_ui.widgets.kpi_card import KpiCard
from pos.shared_ui.widgets.quick_access_panel import QuickAccessPanel
from pos.shared_ui.widgets.top_bar import TopBar


@dataclass(frozen=True)
class NavPanel:
    """Un panel accesible desde la pantalla de bienvenida, visible según
    tres filtros en cascada (ver `_panel_visible`):

    1. `business_types`: si no es `None`, el panel solo existe cuando el
       tipo de negocio configurado está en ese conjunto — aplica incluso a
       `Administrador General` (ej. un futuro módulo exclusivo de
       Farmacia). `None` = módulo genérico, siempre disponible sin
       importar el rubro ("Vendedor"/"Despacho" son genéricos: sirven
       para cualquier tipo de negocio, no solo restaurantes).
    2. `admin_only`: si es `True`, solo lo ve una sesión con `is_admin`
       (cargo "Administrador General"), sin importar `permission_code`.
    3. `permission_code`: para paneles no admin-only, el cargo del usuario
       necesita ese código otorgado (ver "Áreas y cargos") — ignorado por
       completo si la sesión es `is_admin`.

    Agregar un módulo nuevo con pantalla propia es agregar una entrada a
    `_build_nav_panels`, no cablear un botón a mano cada vez."""

    label: str
    on_click: Callable[[], None]
    admin_only: bool = False
    business_types: frozenset[BusinessType] | None = None
    permission_code: str | None = None


# Metadata puramente visual para el panel de accesos rápidos del Dashboard
# (ver `build_welcome_widget`), indexada por `NavPanel.label` en vez de
# agregar campos a `NavPanel` — así el dataclass y `_build_nav_panels`
# quedan intactos. Un panel sin entrada aquí simplemente usa un ícono/grupo
# genérico (ver `QuickAccessPanel`).
_PANEL_ICONS: dict[str, str] = {
    "Administración": "settings",
    "Ganancias": "trending-up",
    "Catálogo": "clipboard",
    "Vendedor": "receipt",
    "Despacho": "package",
    "Inventario": "package",
    "Clientes y Proveedores": "users",
    "Caja": "cash",
    "Ventas": "cart",
    "Reportes": "bar-chart",
    "Licencia": "key",
    "Backups": "save",
    "Sincronización": "sync",
}
"""Nombre del ícono vectorial (`shared_ui/icons.py::get_icon`), no emoji
— ver DESIGN_SYSTEM.md §10. Antes de la Fase 6 del Design System, cada
valor era un carácter emoji (renderizado distinto entre Windows/macOS/
Linux, sin relación con el tema activo)."""

_PANEL_GROUPS: dict[str, str] = {
    "Administración": "Administración",
    "Ganancias": "Administración",
    "Catálogo": "Inventario",
    "Vendedor": "Ventas",
    "Despacho": "Ventas",
    "Inventario": "Inventario",
    "Clientes y Proveedores": "Clientes",
    "Caja": "Administración",
    "Ventas": "Ventas",
    "Reportes": "Administración",
    "Licencia": "Sistema",
    "Backups": "Sistema",
    "Sincronización": "Sistema",
}

_PANEL_DESCRIPTIONS: dict[str, str] = {
    "Administración": "Usuarios, permisos y configuración",
    "Ganancias": "Reportes y estadísticas",
    "Catálogo": "Productos y categorías",
    "Vendedor": "Gestión de vendedores",
    "Despacho": "Órdenes y entregas",
    "Inventario": "Stock y movimientos",
    "Clientes y Proveedores": "Gestión de clientes y proveedores",
    "Caja": "Apertura y cierres",
    "Ventas": "Nueva venta rápida",
    "Reportes": "Informes del sistema",
    "Licencia": "Información de licencia",
    "Backups": "Respaldo y restauración",
    "Sincronización": "Sincronizar datos",
}
"""Subtítulo de cada tarjeta de acceso rápido del Dashboard (ver
`QuickAccessPanel`) — puramente descriptivo, no afecta navegación ni
permisos. Un panel sin entrada aquí simplemente no muestra subtítulo."""
_DEFAULT_PANEL_ICON = "square"
_DEFAULT_PANEL_GROUP = "General"
_KPI_CARD_COLUMNS = 4
_BACKGROUND_IMAGE_WIDTH = 1000
"""Ancho al que se escala la imagen de fondo del Dashboard — el contenido
del Dashboard no tiene un ancho dinámico real (vive en un `QScrollArea` de
alto variable pero ancho típico de ventana), así que se fija a un valor que
ocupa prácticamente todo el ancho usual sin estirar el layout."""


@dataclass(frozen=True)
class _DashboardMetrics:
    """Datos de solo lectura para las tarjetas del Dashboard — cada campo
    se calcula en `_compute_dashboard_metrics` a partir de servicios ya
    existentes, sin agregar ninguna lógica de negocio nueva."""

    sales_today_total: Decimal
    sales_today_count: int
    sales_month_total: Decimal
    sales_month_delta_pct: Decimal | None
    sales_month_trend: list[Decimal]
    profit_today_total: Decimal
    profit_month_total: Decimal
    profit_month_delta_pct: Decimal | None
    profit_month_trend: list[Decimal]
    open_registers_count: int
    open_registers_expected_total: Decimal
    active_employees_count: int
    last_sale_at: datetime | None
    last_sale_total: Decimal | None
    customers_count: int
    pending_dispatch_count: int
    """Cantidad de pedidos en estado `PENDING` únicamente — viene de
    `KitchenService.get_pending_dispatch_count()`, la única fuente de
    verdad para este número (no `list_dispatch_queue`, que trae también
    PREPARING/READY/DELIVERED para la pantalla de Despacho)."""


def _percent_change(current: Decimal, previous: Decimal) -> Decimal | None:
    """`None` cuando el mes anterior fue `$0` — un cambio porcentual sobre
    una base cero no tiene un valor real que mostrar (no se inventa un
    "∞%"), mismo criterio de honestidad ya aplicado en báscula/impresoras
    ("no disponible" en vez de un dato falso)."""
    if previous == 0:
        return None
    return (current - previous) / previous * 100


def _compute_dashboard_metrics(container: Container) -> _DashboardMetrics:
    """Compone las métricas del Dashboard llamando exclusivamente métodos
    de solo lectura ya existentes en cada módulo — no se modifica ni se
    agrega lógica de negocio en ningún service."""
    reports_service = container.resolve(ReportsService)
    cash_register_service = container.resolve(CashRegisterService)
    user_service = container.resolve(UserManagementService)
    sales_service = container.resolve(SalesService)
    customer_service = container.resolve(CustomerManagementService)
    kitchen_service = container.resolve(KitchenService)

    today = date.today()
    month_start = today.replace(day=1)
    prev_month_end = month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    sales_today = reports_service.sales_report(today, today)
    sales_month = reports_service.sales_report(month_start, today)
    profit_today_total = reports_service.product_profit(today, today)
    profit_month_total = reports_service.product_profit(month_start, today)
    sales_month_prev_total = reports_service.sales_report(
        prev_month_start, prev_month_end
    ).total_amount
    profit_month_prev_total = reports_service.product_profit(prev_month_start, prev_month_end)
    sales_month_delta_pct = _percent_change(sales_month.total_amount, sales_month_prev_total)
    profit_month_delta_pct = _percent_change(profit_month_total, profit_month_prev_total)
    month_chart = reports_service.sales_and_profit_chart(month_start, today, monthly=False)
    sales_month_trend = [point.sales_total for point in month_chart]
    profit_month_trend = [point.profit_total for point in month_chart]

    open_registers_count = 0
    open_registers_expected_total = Decimal(0)
    for register in cash_register_service.list_registers():
        session = cash_register_service.get_open_session(register.id)
        if session is not None:
            open_registers_count += 1
            open_registers_expected_total += cash_register_service.calculate_expected_amount(
                session.id
            )

    active_employees_count = sum(1 for user in user_service.list_users() if user.is_active)

    recent_sales = sales_service.list_recent_sales(limit=1)
    last_sale_at = recent_sales[0].created_at if recent_sales else None
    last_sale_total = recent_sales[0].total if recent_sales else None

    customers_count = len(customer_service.list_customers())
    pending_dispatch_count = kitchen_service.get_pending_dispatch_count()

    return _DashboardMetrics(
        sales_today_total=sales_today.total_amount,
        sales_today_count=sales_today.total_count,
        sales_month_total=sales_month.total_amount,
        sales_month_delta_pct=sales_month_delta_pct,
        sales_month_trend=sales_month_trend,
        profit_today_total=profit_today_total,
        profit_month_total=profit_month_total,
        profit_month_delta_pct=profit_month_delta_pct,
        profit_month_trend=profit_month_trend,
        open_registers_count=open_registers_count,
        open_registers_expected_total=open_registers_expected_total,
        active_employees_count=active_employees_count,
        last_sale_at=last_sale_at,
        last_sale_total=last_sale_total,
        customers_count=customers_count,
        pending_dispatch_count=pending_dispatch_count,
    )


def _current_job_position_name(container: Container, session: ActiveSession) -> str | None:
    """Nombre del cargo del usuario activo, solo para mostrarlo en la
    barra superior — no se agrega ningún campo a `ActiveSession` ni se
    toca el módulo de autenticación; se resuelve con una consulta de
    solo lectura ya existente."""
    user_service = container.resolve(UserManagementService)
    return next(
        (user.job_position_name for user in user_service.list_users() if user.id == session.user_id),
        None,
    )


def _greeting_for_now(first_name: str) -> str:
    hour = datetime.now().hour
    if hour < 12:
        prefix = "Buenos días"
    elif hour < 19:
        prefix = "Buenas tardes"
    else:
        prefix = "Buenas noches"
    return f"{prefix}, {first_name}"


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
    container.register_instance(BootstrapConfig, config)
    container.register_singleton(
        BusinessSettingsService, lambda: BusinessSettingsService(event_bus)
    )
    container.register_singleton(
        AuthenticationService, lambda: AuthenticationService(session_manager, event_bus)
    )
    container.register_singleton(UserManagementService, lambda: UserManagementService(event_bus))
    container.register_singleton(JobPositionManagementService, JobPositionManagementService)
    container.resolve(JobPositionManagementService).ensure_system_defaults()
    container.register_singleton(CategoryManagementService, CategoryManagementService)
    container.register_singleton(
        ProductManagementService, lambda: ProductManagementService(event_bus)
    )
    container.register_singleton(InventoryService, lambda: InventoryService(event_bus))
    container.register_singleton(CustomerManagementService, CustomerManagementService)
    container.register_singleton(SupplierManagementService, SupplierManagementService)
    container.register_singleton(RestaurantService, lambda: RestaurantService(event_bus))
    container.register_singleton(
        KitchenService,
        lambda: KitchenService(
            container.resolve(UserManagementService),
            container.resolve(RestaurantService),
            container.resolve(SalesService),
            container.resolve(CashRegisterService),
        ),
    )
    container.register_singleton(NotificationService, NotificationService)
    container.register_singleton(QrPaymentService, QrPaymentService)
    container.register_singleton(NequiPaymentService, NequiPaymentService)
    container.register_singleton(BreBPaymentService, BreBPaymentService)
    container.register_singleton(
        CashRegisterService, lambda: CashRegisterService(event_bus)
    )
    container.register_singleton(TaxService, lambda: TaxService(event_bus))
    container.register_singleton(ScaleService, lambda: ScaleService(event_bus))
    container.resolve(ScaleService).reset_stale_connections()
    container.register_singleton(
        ScaleReadService,
        lambda: ScaleReadService(
            container.resolve(ScaleService), container.resolve(ProductManagementService)
        ),
    )
    container.register_singleton(
        CashDrawerService,
        lambda: CashDrawerService(event_bus, container.resolve(CashRegisterService)),
    )
    container.resolve(CashDrawerService).reset_stale_connections()
    container.register_singleton(PrinterService, lambda: PrinterService(event_bus))
    container.resolve(PrinterService).reset_stale_connections()
    container.register_singleton(BarcodeScannerService, lambda: BarcodeScannerService(event_bus))
    container.resolve(BarcodeScannerService).reset_stale_connections()
    container.register_singleton(
        BarcodeReadService,
        lambda: BarcodeReadService(
            container.resolve(BusinessSettingsService), container.resolve(ProductManagementService)
        ),
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
    container.register_singleton(ProfitsService, ProfitsService)
    container.register_singleton(InvoiceSettingsService, InvoiceSettingsService)
    container.register_singleton(
        BillingService,
        lambda: BillingService(
            container.resolve(SalesService),
            container.resolve(CustomerManagementService),
            container.resolve(BusinessSettingsService),
            container.resolve(InvoiceSettingsService),
            container.resolve(UserManagementService),
            container.resolve(CashRegisterService),
            container.resolve(CashDrawerService),
            config.data_dir / "invoices",
        ),
    )
    container.register_singleton(ReceiptPrinter, DefaultReceiptPrinter)

    pool_db_path = config.data_dir / "licenses_pool.db"
    if not pool_db_path.exists():
        bundled_pool_db = _bundled_resources_dir() / "licenses_pool.db"
        if bundled_pool_db.exists():
            shutil.copy(bundled_pool_db, pool_db_path)
    container.register_instance(LicensePoolDatabase, LicensePoolDatabase(pool_db_path))

    container.register_singleton(
        LicenseService,
        lambda: LicenseService(
            config.data_dir,
            event_bus,
            container.resolve(UserManagementService),
            container.resolve(InventoryService),
            container.resolve(CashRegisterService),
            container.resolve(InvoiceSettingsService),
            container.resolve(LicensePoolDatabase),
        ),
    )
    container.register_singleton(
        BackupService,
        lambda: BackupService(
            config.database_url,
            config.data_dir / "backups",
            container.resolve(BusinessSettingsService),
        ),
    )
    container.register_singleton(
        SyncService,
        lambda: SyncService(event_bus, container.resolve(BusinessSettingsService)),
    )
    container.register_singleton(
        SyncTransport,
        lambda: SyncTransport(
            container.resolve(SyncService),
            container.resolve(AuthenticationService),
            container.resolve(ProductManagementService),
            container.resolve(CategoryManagementService),
            container.resolve(SalesService),
            container.resolve(InventoryService),
            container.resolve(CashRegisterService),
            container.resolve(KitchenService),
            container.resolve(CustomerManagementService),
            container.resolve(UserManagementService),
            container.resolve(RestaurantService),
            container.resolve(QrPaymentService),
            container.resolve(NequiPaymentService),
            container.resolve(BreBPaymentService),
        ),
    )

    # Registro de manejadores de eventos entre módulos (ver ARCHITECTURE.md
    # §5): Inventario reacciona a que Productos publique un producto nuevo.
    inventory_handlers = InventoryProductEventHandlers(container.resolve(InventoryService))
    event_bus.subscribe(ProductCreatedEvent, inventory_handlers.on_product_created)

    # Notificaciones reacciona a que Vendedor (Restaurante) confirme un
    # pedido nuevo — Despacho y Caja se enteran de inmediato sin que
    # Vendedor conozca a sus consumidores.
    notification_handlers = NotificationEventHandlers(container.resolve(NotificationService))
    event_bus.subscribe(OrderCreatedEvent, notification_handlers.on_order_created)

    # Captura de outbox de Sincronización (ARCHITECTURE.md §10): TODO evento
    # de dominio publicado en el proceso queda registrado como entrada de
    # `sync_log`, sin que cada módulo nuevo tenga que suscribirse a mano.
    event_bus.subscribe_all(container.resolve(SyncService).capture_event)

    return config


def _parse_log_level(level_name: str) -> int:
    return logging.getLevelNamesMapping().get(level_name.upper(), logging.INFO)


def build_application() -> QApplication:
    """Crea la instancia de QApplication con metadata básica de la app.

    `setHighDpiScaleFactorRoundingPolicy` debe llamarse antes de construir
    `QApplication` (Qt lo lee una sola vez, al inicializar la integración de
    plataforma) — se fija explícitamente en `PassThrough` (factores de
    escala fraccionarios exactos, sin redondeo) en vez de dejarlo en el
    valor por defecto implícito de la versión de Qt instalada, para que el
    comportamiento no cambie silenciosamente entre versiones."""
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
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


def _wire_tab_reload(tabs: QTabWidget) -> None:
    """Recarga los datos de la pestaña recién seleccionada, para que un
    cambio hecho en una pestaña (ej. completar una venta en "Nueva venta")
    se vea de inmediato en otra (ej. "Historial") sin salir y volver a
    entrar al módulo completo."""

    def _on_tab_changed(index: int) -> None:
        reload = getattr(tabs.widget(index), "reload", None)
        if callable(reload):
            reload()

    tabs.currentChanged.connect(_on_tab_changed)


def _build_devices_content(container: Container) -> QWidget:
    """Primer nivel de menú anidado en Administración: cada tipo de
    dispositivo (báscula, cajón monedero, lector de códigos de barras,
    impresoras) es su propia sub-pestaña, con su propio modelo/servicio/
    vista/CRUD y adaptador de conexión — agregar un tipo nuevo a futuro es
    agregar una línea más acá, sin tocar esta pantalla ni las demás."""
    scale_service = container.resolve(ScaleService)
    scale_read_service = container.resolve(ScaleReadService)
    cash_register_service = container.resolve(CashRegisterService)
    user_service = container.resolve(UserManagementService)
    cash_drawer_service = container.resolve(CashDrawerService)
    session_manager = container.resolve(SessionManager)
    barcode_scanner_service = container.resolve(BarcodeScannerService)
    barcode_read_service = container.resolve(BarcodeReadService)
    printer_service = container.resolve(PrinterService)
    invoices_dir = container.resolve(BootstrapConfig).data_dir / "invoices"
    tabs = QTabWidget()
    tabs.addTab(
        ScalesView(
            ScalesViewModel(scale_service, cash_register_service, user_service, scale_read_service)
        ),
        "Báscula electrónica",
    )
    tabs.addTab(
        CashDrawersView(
            CashDrawersViewModel(cash_drawer_service, cash_register_service, session_manager)
        ),
        "Cajón monedero",
    )
    tabs.addTab(
        BarcodeScannersView(
            BarcodeScannersViewModel(
                barcode_scanner_service, cash_register_service, barcode_read_service
            )
        ),
        "Código de barras",
    )
    tabs.addTab(
        PrintersView(
            PrintersViewModel(printer_service, cash_register_service, session_manager),
            invoices_dir,
        ),
        "Impresoras",
    )
    _wire_tab_reload(tabs)
    return tabs


def _build_electronic_payments_content(
    qr_payment_service: QrPaymentService,
    nequi_payment_service: NequiPaymentService,
    breb_payment_service: BreBPaymentService,
) -> QWidget:
    """Segundo nivel de menú anidado en Administración (mismo patrón que
    `_build_devices_content`): un medio de pago electrónico manual por
    sub-pestaña — agregar uno nuevo a futuro es una pestaña más acá, sin
    tocar Ventas ni las demás sub-pestañas."""
    tabs = QTabWidget()
    tabs.addTab(QrPaymentConfigView(QrPaymentConfigViewModel(qr_payment_service)), "QR")
    tabs.addTab(NequiPaymentConfigView(NequiPaymentConfigViewModel(nequi_payment_service)), "Nequi")
    tabs.addTab(BreBPaymentConfigView(BreBPaymentConfigViewModel(breb_payment_service)), "Bre-B")
    _wire_tab_reload(tabs)
    return tabs


def _build_admin_content(container: Container) -> QWidget:
    user_service = container.resolve(UserManagementService)
    job_position_service = container.resolve(JobPositionManagementService)
    settings_service = container.resolve(BusinessSettingsService)
    cash_register_service = container.resolve(CashRegisterService)
    qr_payment_service = container.resolve(QrPaymentService)
    nequi_payment_service = container.resolve(NequiPaymentService)
    breb_payment_service = container.resolve(BreBPaymentService)
    sync_service = container.resolve(SyncService)
    tax_service = container.resolve(TaxService)
    invoice_settings_service = container.resolve(InvoiceSettingsService)
    tabs = QTabWidget()
    tabs.addTab(UsersView(UsersViewModel(user_service, job_position_service)), "Usuarios")
    tabs.addTab(
        JobPositionsView(JobPositionsViewModel(job_position_service)), "Áreas y cargos"
    )
    tabs.addTab(
        CashRegistersView(CashRegistersViewModel(cash_register_service)), "Cajas"
    )
    tabs.addTab(
        _build_electronic_payments_content(
            qr_payment_service, nequi_payment_service, breb_payment_service
        ),
        "Pagos electrónicos",
    )
    tabs.addTab(TaxesView(TaxesViewModel(tax_service)), "Impuestos")
    tabs.addTab(_build_devices_content(container), "Dispositivos")
    tabs.addTab(
        InvoiceSettingsView(InvoiceSettingsViewModel(invoice_settings_service)),
        "Configuración de factura",
    )
    tabs.addTab(
        InterfaceSettingsView(InterfaceSettingsViewModel(settings_service)),
        "Configuración de interfaz",
    )
    tabs.addTab(AuditLogView(AuditLogViewModel(sync_service)), "Auditoría")
    _wire_tab_reload(tabs)
    return tabs


def _build_catalog_content(container: Container) -> QWidget:
    product_service = container.resolve(ProductManagementService)
    category_service = container.resolve(CategoryManagementService)
    tabs = QTabWidget()
    tabs.addTab(CategoriesView(CategoriesViewModel(category_service)), "Categorías")
    tabs.addTab(
        ProductsView(ProductsViewModel(product_service, category_service)), "Productos"
    )
    _wire_tab_reload(tabs)
    return tabs


def _build_inventory_content(container: Container) -> QWidget:
    inventory_service = container.resolve(InventoryService)
    product_service = container.resolve(ProductManagementService)
    user_service = container.resolve(UserManagementService)
    session_manager = container.resolve(SessionManager)
    tabs = QTabWidget()
    tabs.addTab(
        InventoryView(
            InventoryViewModel(inventory_service, product_service, user_service, session_manager)
        ),
        "Existencias",
    )
    tabs.addTab(
        WarehousesView(WarehousesViewModel(inventory_service, product_service)), "Bodegas"
    )
    _wire_tab_reload(tabs)
    return tabs


def _build_restaurant_content(container: Container) -> QWidget:
    restaurant_service = container.resolve(RestaurantService)
    product_service = container.resolve(ProductManagementService)
    category_service = container.resolve(CategoryManagementService)
    inventory_service = container.resolve(InventoryService)
    sales_service = container.resolve(SalesService)
    session_manager = container.resolve(SessionManager)
    scale_read_service = container.resolve(ScaleReadService)
    return RestaurantView(
        RestaurantViewModel(
            restaurant_service,
            product_service,
            category_service,
            inventory_service,
            sales_service,
            session_manager,
            scale_read_service,
        )
    )


def _build_kitchen_content(container: Container) -> QWidget:
    kitchen_service = container.resolve(KitchenService)
    session_manager = container.resolve(SessionManager)
    event_bus = container.resolve(EventBus)
    return KitchenView(KitchenViewModel(kitchen_service, session_manager, event_bus))


def _build_cash_register_content(container: Container) -> QWidget:
    cash_register_service = container.resolve(CashRegisterService)
    session_manager = container.resolve(SessionManager)
    user_service = container.resolve(UserManagementService)
    return CashRegisterView(
        CashRegisterViewModel(cash_register_service, session_manager, user_service)
    )


def _build_sales_content(container: Container) -> QWidget:
    sales_service = container.resolve(SalesService)
    product_service = container.resolve(ProductManagementService)
    customer_service = container.resolve(CustomerManagementService)
    inventory_service = container.resolve(InventoryService)
    cash_register_service = container.resolve(CashRegisterService)
    billing_service = container.resolve(BillingService)
    receipt_printer = container.resolve(ReceiptPrinter)
    cash_drawer_service = container.resolve(CashDrawerService)
    qr_payment_service = container.resolve(QrPaymentService)
    restaurant_service = container.resolve(RestaurantService)
    session_manager = container.resolve(SessionManager)
    scale_read_service = container.resolve(ScaleReadService)
    nequi_payment_service = container.resolve(NequiPaymentService)
    breb_payment_service = container.resolve(BreBPaymentService)
    user_service = container.resolve(UserManagementService)
    barcode_read_service = container.resolve(BarcodeReadService)
    printer_service = container.resolve(PrinterService)

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
                billing_service,
                receipt_printer,
                cash_drawer_service,
                qr_payment_service,
                restaurant_service,
                scale_read_service,
                nequi_payment_service,
                breb_payment_service,
                barcode_read_service,
                printer_service,
            )
        ),
        "Nueva venta",
    )
    tabs.addTab(
        SalesHistoryView(
            SalesHistoryViewModel(
                sales_service,
                inventory_service,
                billing_service,
                session_manager,
                receipt_printer,
                user_service,
                cash_register_service,
                printer_service,
            )
        ),
        "Historial",
    )
    _wire_tab_reload(tabs)
    return tabs


def _build_reports_content(container: Container) -> QWidget:
    reports_service = container.resolve(ReportsService)
    return ReportsView(ReportsViewModel(reports_service))


def _build_profits_content(container: Container) -> QWidget:
    return ProfitsView(
        container.resolve(ProfitsService),
        container.resolve(CategoryManagementService),
        container.resolve(SupplierManagementService),
        container.resolve(InventoryService),
        container.resolve(UserManagementService),
        container.resolve(CashRegisterService),
        container.resolve(CustomerManagementService),
        container.resolve(InvoiceSettingsService),
        container.resolve(SessionManager),
    )


def _build_backups_content(container: Container) -> QWidget:
    backup_service = container.resolve(BackupService)
    backup_scheduler = container.resolve(BackupScheduler)
    return BackupsView(
        BackupsViewModel(backup_service, backup_scheduler, container.resolve(SessionManager))
    )


def _build_license_content(container: Container) -> QWidget:
    license_service = container.resolve(LicenseService)
    session_manager = container.resolve(SessionManager)
    return LicenseDashboardView(LicenseDashboardViewModel(license_service, session_manager))


def _build_sync_content(container: Container) -> QWidget:
    transport = container.resolve(SyncTransport)
    return SyncView(SyncViewModel(transport))


def _build_third_parties_content(container: Container) -> QWidget:
    customer_service = container.resolve(CustomerManagementService)
    supplier_service = container.resolve(SupplierManagementService)
    billing_service = container.resolve(BillingService)
    cash_register_service = container.resolve(CashRegisterService)
    session_manager = container.resolve(SessionManager)
    receipt_printer = container.resolve(ReceiptPrinter)
    printer_service = container.resolve(PrinterService)

    tabs = QTabWidget()
    tabs.addTab(
        CustomersView(
            CustomersViewModel(customer_service),
            billing_service,
            customer_service,
            cash_register_service,
            session_manager,
            receipt_printer,
            printer_service,
        ),
        "Clientes",
    )
    tabs.addTab(SuppliersView(SuppliersViewModel(supplier_service)), "Proveedores")
    _wire_tab_reload(tabs)
    return tabs


def _build_nav_panels(
    container: Container, open_panel: Callable[[Callable[[Container], QWidget]], None]
) -> list[NavPanel]:
    """Catálogo de paneles disponibles desde la pantalla de bienvenida.
    Agregar un módulo nuevo con pantalla propia es agregar una línea aquí:
    un módulo genérico solo necesita `permission_code`; uno exclusivo de
    un rubro (ej. futuro módulo de Farmacia) agrega además
    `business_types=frozenset({BusinessType.FARMACIA})`."""
    return [
        NavPanel(
            "Administración", lambda: open_panel(_build_admin_content), admin_only=True
        ),
        NavPanel(
            "Ganancias",
            lambda: open_panel(_build_profits_content),
            permission_code="profits.view",
        ),
        NavPanel(
            "Catálogo",
            lambda: open_panel(_build_catalog_content),
            permission_code="products.manage",
        ),
        NavPanel(
            "Vendedor",
            lambda: open_panel(_build_restaurant_content),
            permission_code="restaurant.manage",
        ),
        NavPanel(
            "Despacho",
            lambda: open_panel(_build_kitchen_content),
            permission_code="kitchen.manage",
        ),
        NavPanel(
            "Inventario",
            lambda: open_panel(_build_inventory_content),
            permission_code="inventory.manage",
        ),
        NavPanel(
            "Clientes y Proveedores",
            lambda: open_panel(_build_third_parties_content),
            permission_code="customers.manage",
        ),
        NavPanel(
            "Caja",
            lambda: open_panel(_build_cash_register_content),
            permission_code="cash_register.manage",
        ),
        NavPanel(
            "Ventas", lambda: open_panel(_build_sales_content), permission_code="sales.create"
        ),
        NavPanel(
            "Reportes", lambda: open_panel(_build_reports_content), permission_code="reports.view"
        ),
        NavPanel("Licencia", lambda: open_panel(_build_license_content), admin_only=True),
        NavPanel("Backups", lambda: open_panel(_build_backups_content), admin_only=True),
        NavPanel("Sincronización", lambda: open_panel(_build_sync_content), admin_only=True),
    ]


def _panel_visible(panel: NavPanel, session: ActiveSession, business_type: BusinessType) -> bool:
    """Intersección de los dos filtros del menú: tipo de negocio primero
    (aplica incluso a Administrador General), y sobre lo que queda, el
    permiso del cargo (`is_admin` lo ve todo, sin restricción de permiso)."""
    if panel.business_types is not None and business_type not in panel.business_types:
        return False
    if panel.admin_only:
        return session.is_admin
    if session.is_admin:
        return True
    if panel.permission_code is None:
        return True
    return panel.permission_code in session.permission_codes


_DISPATCH_BELL_REFRESH_MS = 5000
"""Mismo intervalo y misma justificación que `KitchenViewModel._REFRESH_MS`
(ver `kitchen_view_model.py`): la suscripción a `OrderCreatedEvent` cubre
pedidos nuevos al instante; este sondeo cada 5&nbsp;s es el respaldo para
que un pedido entregado/avanzado desde Despacho (que no publica ningún
evento) también se refleje sin que el usuario tenga que salir y volver al
Dashboard."""


def build_welcome_widget(
    session: ActiveSession,
    on_logout: Callable[[], None],
    panels: list[NavPanel],
    business_type: BusinessType,
    metrics: _DashboardMetrics,
    job_position_name: str | None,
    kitchen_service: KitchenService,
    event_bus: EventBus,
    background_image_path: str | None = None,
) -> QWidget:
    """Dashboard mostrado tras un login exitoso: barra superior, tarjetas
    de indicadores, actividad reciente y accesos rápidos agrupados por
    categoría — un botón por cada `NavPanel` visible para el tipo de
    negocio y el cargo de la sesión activa (ver `_panel_visible`). Todo
    dentro de un `QScrollArea` porque el contenido es más alto que una
    pantalla."""
    role_label = "Administrador" if session.is_admin else (job_position_name or "Empleado")
    first_name = session.full_name.split(" ")[0] if session.full_name else session.full_name
    # No existe todavía un concepto de sucursal/multi-local en el sistema
    # (`BusinessSettingsService` solo guarda el tipo de negocio) — texto fijo.
    branch_label = "Sucursal Principal"

    # La campana de despachos solo ofrece "Abrir Despacho" si la sesión
    # tiene acceso al panel — reutiliza el mismo callback que el acceso
    # rápido "Despacho", sin abrir una ruta de navegación nueva.
    dispatch_panel = next(
        (p for p in panels if p.label == "Despacho" and _panel_visible(p, session, business_type)),
        None,
    )
    top_bar = TopBar(
        system_name="Sistema POS",
        greeting=_greeting_for_now(first_name),
        role_label=role_label,
        branch_label=branch_label,
        on_logout=on_logout,
        on_about=lambda: AboutDialog(top_bar).exec(),
        on_open_dispatch=dispatch_panel.on_click if dispatch_panel is not None else None,
    )
    top_bar.set_pending_dispatch_count(metrics.pending_dispatch_count)

    def _refresh_pending_dispatch_count() -> None:
        top_bar.set_pending_dispatch_count(kitchen_service.get_pending_dispatch_count())

    def _on_order_created_for_dispatch_bell(_event: OrderCreatedEvent) -> None:
        _refresh_pending_dispatch_count()

    event_bus.subscribe(OrderCreatedEvent, _on_order_created_for_dispatch_bell)
    dispatch_refresh_timer = QTimer(top_bar)
    dispatch_refresh_timer.setInterval(_DISPATCH_BELL_REFRESH_MS)
    dispatch_refresh_timer.timeout.connect(_refresh_pending_dispatch_count)
    dispatch_refresh_timer.start()

    # Las tarjetas de cifras financieras reutilizan el mismo permiso que ya
    # protege el módulo "Reportes" — sin inventar un código de permiso nuevo.
    can_see_financials = session.is_admin or "reports.view" in session.permission_codes

    kpi_cards: list[QWidget] = []
    if can_see_financials:
        kpi_cards.append(
            KpiCard(
                "Ventas del día",
                f"${format_currency(metrics.sales_today_total)}",
                f"{metrics.sales_today_count} venta(s)",
                icon="cart",
                accent="primary",
            )
        )
        kpi_cards.append(
            KpiCard(
                "Ventas del mes",
                f"${format_currency(metrics.sales_month_total)}",
                icon="trending-up",
                accent="success",
                trend=metrics.sales_month_trend,
                delta_pct=metrics.sales_month_delta_pct,
            )
        )
        kpi_cards.append(
            KpiCard(
                "Ganancias del día",
                f"${format_currency(metrics.profit_today_total)}",
                icon="wallet",
                accent="primary",
            )
        )
        kpi_cards.append(
            KpiCard(
                "Ganancias del mes",
                f"${format_currency(metrics.profit_month_total)}",
                icon="wallet",
                accent="success",
                trend=metrics.profit_month_trend,
                delta_pct=metrics.profit_month_delta_pct,
            )
        )
        kpi_cards.append(
            KpiCard("Compras del mes", "Próximamente", icon="basket", accent="secondary")
        )
    kpi_cards.append(
        KpiCard(
            "Caja actual",
            f"${format_currency(metrics.open_registers_expected_total)}",
            f"{metrics.open_registers_count} abierta(s)",
            icon="cash",
            accent="primary",
        )
    )
    kpi_cards.append(
        KpiCard(
            "Empleados activos",
            str(metrics.active_employees_count),
            icon="users",
            accent="secondary",
        )
    )
    kpi_cards.append(
        KpiCard(
            "Clientes registrados", str(metrics.customers_count), icon="user", accent="secondary"
        )
    )
    if metrics.last_sale_at is not None and metrics.last_sale_total is not None:
        kpi_cards.append(
            KpiCard(
                "Última venta",
                f"${format_currency(metrics.last_sale_total)}",
                metrics.last_sale_at.strftime("%d/%m/%Y %H:%M"),
                icon="receipt",
                accent="primary",
            )
        )
    else:
        kpi_cards.append(
            KpiCard("Última venta", "Sin ventas todavía", icon="receipt", accent="primary")
        )

    kpi_row = QGridLayout()
    kpi_row.setHorizontalSpacing(12)
    kpi_row.setVerticalSpacing(12)
    for index, card in enumerate(kpi_cards):
        kpi_row.addWidget(card, index // _KPI_CARD_COLUMNS, index % _KPI_CARD_COLUMNS)

    visible_panels = [
        panel for panel in panels if _panel_visible(panel, session, business_type)
    ]
    quick_access_items = [
        (
            _PANEL_ICONS.get(panel.label, _DEFAULT_PANEL_ICON),
            panel.label,
            _PANEL_GROUPS.get(panel.label, _DEFAULT_PANEL_GROUP),
            _PANEL_DESCRIPTIONS.get(panel.label, ""),
            panel.on_click,
        )
        for panel in visible_panels
    ]
    quick_access_panel = QuickAccessPanel(quick_access_items)

    content_layout = QVBoxLayout()
    content_layout.setSpacing(16)
    content_layout.setContentsMargins(20, 16, 20, 16)
    content_layout.addWidget(top_bar)
    content_layout.addLayout(kpi_row)
    content_layout.addWidget(quick_access_panel)
    if background_image_path and Path(background_image_path).exists():
        background_label = QLabel()
        background_pixmap = QPixmap(background_image_path)
        if not background_pixmap.isNull():
            background_label.setPixmap(
                background_pixmap.scaledToWidth(
                    _BACKGROUND_IMAGE_WIDTH, Qt.TransformationMode.SmoothTransformation
                )
            )
            background_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            content_layout.addWidget(background_label)
    content_layout.addStretch()

    content = QWidget()
    content.setLayout(content_layout)

    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_area.setFrameShape(QFrame.Shape.NoFrame)
    scroll_area.setWidget(content)

    # La suscripción al bus de eventos no sigue el ciclo de vida de Qt por
    # sí sola (a diferencia del `QTimer`, que muere con `top_bar` al
    # destruirse este widget) — hay que desuscribirla a mano cuando el
    # usuario navega fuera del Dashboard, o cada regreso acumularía un
    # manejador más, igual que ya resuelve `KitchenViewModel` con
    # `destroyed.connect(self._unsubscribe)`.
    def _unsubscribe_dispatch_bell() -> None:
        event_bus.unsubscribe(OrderCreatedEvent, _on_order_created_for_dispatch_bell)

    scroll_area.destroyed.connect(_unsubscribe_dispatch_bell)
    return scroll_area


def _resync_native_window_geometry(window: QMainWindow) -> None:
    """Fuerza a Qt/Cocoa a recalcular por completo la geometría nativa de
    la ventana (backing store de pintura + área de hit-testing del mouse)
    después de que cambia de pantalla.

    Causa raíz del bug reportado ("la interfaz aparece comprimida y el
    clic queda desalineado del botón, se arregla minimizando y
    restaurando"): en macOS, cuando una `NSWindow` se arrastra entre
    pantallas con distinto factor de escala (p. ej. la pantalla Retina
    integrada y un monitor externo no-Retina), Cocoa actualiza el
    `backingScaleFactor` de la ventana nativa, pero Qt no siempre vuelve a
    sincronizar de inmediato las coordenadas de pintura con las de
    hit-testing de eventos de mouse — quedan desfasadas hasta que la
    ventana nativa se recrea, que es exactamente lo que hace minimizar y
    restaurar. No hay ningún código propio de esta app causando el
    desfase (paneles/`QGraphicsView`/splitters no tocan la geometría de
    la ventana — ver investigación de este bug); es una limitación conocida
    de Qt en macOS con monitores de DPI mixto, y no expone una API directa
    de "resincronizar ahora".

    El mitigador estándar (documentado en varios reportes de Qt para este
    mismo síntoma) es un cambio de tamaño inocuo de ida y vuelta: obliga a
    Qt a reconstruir por completo la geometría nativa para la pantalla
    actual, sin que el usuario note un cambio visual real."""
    size = window.size()
    window.resize(size.width() + 1, size.height())
    window.resize(size)


def _watch_screen_changes_for_geometry_resync(window: QMainWindow) -> None:
    """Conecta `screenChanged` de la ventana nativa (solo existe una vez
    que `window.show()` ya creó el `QWindow` real) a `_resync_native_window_geometry`."""
    handle = window.windowHandle()
    if handle is not None:
        handle.screenChanged.connect(lambda _screen: _resync_native_window_geometry(window))


def build_main_window(theme_manager: ThemeManager, container: Container) -> QMainWindow:
    """Construye la ventana principal.

    Arranca verificando la licencia (PROJECT_SPEC.md, "LICENCIAS"): si no
    es válida, bloquea el acceso de forma elegante mostrando la pantalla de
    activación en vez del login — nada de la operación del negocio es
    alcanzable sin una licencia vigente. Si es válida, procede al login
    normalmente.
    """
    load_bundled_fonts()
    theme_manager.apply_dark()
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
            container.resolve(JobPositionManagementService),
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
        settings_service = container.resolve(BusinessSettingsService)
        business_type = get_business_type(settings_service)
        metrics = _compute_dashboard_metrics(container)
        job_position_name = _current_job_position_name(container, session)
        background_image_path = settings_service.get_str(BACKGROUND_IMAGE_KEY, "") or None
        window.setCentralWidget(
            build_welcome_widget(
                session,
                handle_logout,
                panels,
                business_type,
                metrics,
                job_position_name,
                container.resolve(KitchenService),
                container.resolve(EventBus),
                background_image_path,
            )
        )

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

    backup_service = container.resolve(BackupService)
    backup_scheduler = BackupScheduler(backup_service)
    backup_scheduler.start()
    container.register_instance(BackupScheduler, backup_scheduler)

    sync_transport = container.resolve(SyncTransport)
    if sync_transport.sync_service.get_auto_start_enabled():
        try:
            sync_transport.apply_persisted_mode()
        except SyncServerStartError:
            # No debe impedir que el resto de la app arranque — el motivo
            # real ya quedó en el registro de eventos del panel de
            # Sincronización (ver `SyncServer.start()`), visible sin tener
            # que mirar la consola.
            logging.getLogger(__name__).exception(
                "No fue posible iniciar el transporte de sincronización al arrancar"
            )

    window = build_main_window(theme_manager, container)
    window.show()
    _watch_screen_changes_for_geometry_resync(window)
    try:
        return app.exec()
    finally:
        if backup_service.get_backup_on_close_enabled():
            try:
                backup_service.run_manual_backup()
            except Exception:
                logging.getLogger(__name__).exception(
                    "Falló el backup automático al cerrar la aplicación"
                )
        backup_scheduler.shutdown()
        sync_transport.shutdown()


if __name__ == "__main__":
    sys.exit(main())
