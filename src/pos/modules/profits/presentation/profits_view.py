"""Pantalla de Ganancias: 6 pestañas (Diario/Semanal/Mensual/Trimestral/
Semestral (6 meses)/Anual), cada una una instancia independiente de
`ProfitsTabView` — la única diferencia entre pestañas es el
`DateRangePreset` que reciben; toda la lógica de consulta, filtros,
tabla, gráficos y exportación vive una sola vez en `ProfitsTabView`."""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from pos.core.security.session import SessionManager
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.invoice_settings.application.invoice_settings_service import (
    InvoiceSettingsService,
)
from pos.modules.products.application.category_service import CategoryManagementService
from pos.modules.profits.application.profits_service import ProfitsService
from pos.modules.profits.domain.enums import DateRangePreset
from pos.modules.profits.presentation.profits_tab_view import ProfitsTabView
from pos.modules.profits.presentation.profits_view_model import ProfitsViewModel
from pos.modules.suppliers.application.supplier_service import SupplierManagementService
from pos.modules.users.application.user_management_service import UserManagementService

_TAB_LABELS = [
    (DateRangePreset.DAILY, "Diario"),
    (DateRangePreset.WEEKLY, "Semanal"),
    (DateRangePreset.MONTHLY, "Mensual"),
    (DateRangePreset.QUARTERLY, "Trimestral"),
    (DateRangePreset.SEMIANNUAL, "Semestral (6 meses)"),
    (DateRangePreset.ANNUAL, "Anual"),
]


class ProfitsView(QWidget):
    def __init__(
        self,
        profits_service: ProfitsService,
        category_service: CategoryManagementService,
        supplier_service: SupplierManagementService,
        inventory_service: InventoryService,
        user_service: UserManagementService,
        cash_register_service: CashRegisterService,
        customer_service: CustomerManagementService,
        invoice_settings_service: InvoiceSettingsService,
        session_manager: SessionManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget(self)
        for preset, label in _TAB_LABELS:
            view_model = ProfitsViewModel(
                preset,
                profits_service,
                category_service,
                supplier_service,
                inventory_service,
                user_service,
                cash_register_service,
                customer_service,
            )
            tab = ProfitsTabView(preset, view_model, invoice_settings_service, session_manager)
            tabs.addTab(tab, label)
        layout.addWidget(tabs)
