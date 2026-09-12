"""View model de Ganancias — una instancia por pestaña (cada una guarda su
propio rango de fechas y filtros); la pestaña solo le pasa un
`DateRangePreset` distinto al construirla, el resto de la lógica es
exactamente la misma para las 6 (ver `profits_view.py`)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.products.application.category_service import CategoryManagementService
from pos.modules.profits.application.profits_service import ProfitsService
from pos.modules.profits.domain.date_ranges import resolve_range
from pos.modules.profits.domain.enums import DateRangePreset
from pos.modules.profits.domain.filters import ProfitFilters
from pos.modules.suppliers.application.supplier_service import SupplierManagementService
from pos.modules.users.application.user_management_service import UserManagementService


class ProfitsViewModel(QObject):
    filter_options_loaded = Signal(list, list, list, list, list, list)
    """(categorías, proveedores, bodegas, usuarios, cajas, clientes)."""
    summary_loaded = Signal(object)
    rows_loaded = Signal(list)
    category_groups_loaded = Signal(list)
    top_lists_loaded = Signal(object)
    chart_series_loaded = Signal(object)
    history_loaded = Signal(list)
    date_range_changed = Signal(object, object)
    error_occurred = Signal(str)

    def __init__(
        self,
        preset: DateRangePreset,
        profits_service: ProfitsService,
        category_service: CategoryManagementService,
        supplier_service: SupplierManagementService,
        inventory_service: InventoryService,
        user_service: UserManagementService,
        cash_register_service: CashRegisterService,
        customer_service: CustomerManagementService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._preset = preset
        self._profits_service = profits_service
        self._category_service = category_service
        self._supplier_service = supplier_service
        self._inventory_service = inventory_service
        self._user_service = user_service
        self._cash_register_service = cash_register_service
        self._customer_service = customer_service

        self._date_from, self._date_to = resolve_range(preset, date.today())
        self._filters = ProfitFilters()

    def load(self) -> None:
        self._load_filter_options()
        self.date_range_changed.emit(self._date_from, self._date_to)
        self.refresh()

    def _load_filter_options(self) -> None:
        categories = self._category_service.list_categories()
        suppliers = self._supplier_service.list_suppliers()
        warehouses = self._inventory_service.list_all_warehouses()
        users = self._user_service.list_users()
        cash_registers = self._cash_register_service.list_all_registers()
        customers = self._customer_service.list_customers()
        self.filter_options_loaded.emit(
            categories, suppliers, warehouses, users, cash_registers, customers
        )

    def set_date_range(self, date_from: date, date_to: date) -> None:
        self._date_from = date_from
        self._date_to = date_to
        self.refresh()

    def set_filters(self, filters: ProfitFilters) -> None:
        self._filters = filters
        self.refresh()

    def filters(self) -> ProfitFilters:
        return self._filters

    def date_range(self) -> tuple[date, date]:
        return self._date_from, self._date_to

    def refresh(self) -> None:
        try:
            summary = self._profits_service.get_summary(
                self._date_from, self._date_to, self._filters
            )
            rows = self._profits_service.get_product_rows(
                self._date_from, self._date_to, self._filters
            )
            category_groups = self._profits_service.get_category_groups(
                self._date_from, self._date_to, self._filters
            )
            top_lists = self._profits_service.get_top_lists(
                self._date_from, self._date_to, self._filters
            )
            chart_series = self._profits_service.get_chart_series(
                self._date_from, self._date_to, self._filters
            )
        except Exception as error:  # noqa: BLE001 - módulo de solo lectura, nunca debe tumbar la UI
            self.error_occurred.emit(str(error))
            return
        self.summary_loaded.emit(summary)
        self.rows_loaded.emit(rows)
        self.category_groups_loaded.emit(category_groups)
        self.top_lists_loaded.emit(top_lists)
        self.chart_series_loaded.emit(chart_series)

    def load_history(self, product_id: int) -> None:
        try:
            history = self._profits_service.get_product_history(
                product_id, self._date_from, self._date_to, self._filters
            )
        except Exception as error:  # noqa: BLE001
            self.error_occurred.emit(str(error))
            return
        self.history_loaded.emit(history)

    def export_to_excel(self, file_path: Path, period_label: str) -> None:
        self._profits_service.export_to_excel(
            self._date_from, self._date_to, self._filters, file_path, period_label
        )

    def export_to_pdf(
        self,
        file_path: Path,
        *,
        company_name: str,
        logo_path: str | None,
        generated_by: str,
        period_label: str,
        filters_description: str,
    ) -> None:
        self._profits_service.export_to_pdf(
            self._date_from,
            self._date_to,
            self._filters,
            file_path,
            company_name=company_name,
            logo_path=logo_path,
            generated_by=generated_by,
            period_label=period_label,
            filters_description=filters_description,
        )
