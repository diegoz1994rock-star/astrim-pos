"""View model del historial de ventas y anulación — incluye el Resumen
Diario (ventas + abonos de hoy, por cajero, y el cierre de caja
combinado)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from PySide6.QtCore import QObject, Signal

from pos.core.database.base import today_utc_bounds
from pos.core.exceptions import DomainError
from pos.core.security.session import SessionManager
from pos.modules.billing.application.billing_service import BillingService
from pos.modules.billing.application.dto import DailyPaymentEntryDTO
from pos.modules.billing.application.print_helper import print_invoice_for_sale
from pos.modules.billing.application.receipt_printer import ReceiptPrinter
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.printers.application.printer_service import PrinterService
from pos.modules.sales.application.sale_service import SalesService
from pos.modules.sales.domain.enums import PaymentMethod
from pos.modules.users.application.user_management_service import UserManagementService


@dataclass(frozen=True)
class NamedTotalDTO:
    name: str
    total: Decimal


@dataclass(frozen=True)
class CashierClosingRowDTO:
    """Una fila de "Cierre de caja" → "Por cajero": ventas + abonos de ESE
    cajero hoy, y el total que debería tener en mano al entregar turno."""

    cashier_name: str
    sales_total: Decimal
    payments_total: Decimal
    total_received: Decimal


@dataclass(frozen=True)
class DailyClosingSummaryDTO:
    """Resumen completo del día (Ventas → Historial) — combina lo que ya
    calculó `SalesService.get_daily_totals`/`BillingService.
    get_daily_payment_summary` en SQL agregado; combinar 2-3 listas
    pequeñas (una por cajero activo) en Python es económico, el trabajo
    pesado ya lo hizo el `GROUP BY`."""

    sales_total: Decimal
    sales_by_cashier: list[NamedTotalDTO] = field(default_factory=list)
    payments_total: Decimal = Decimal(0)
    payment_entries: list[DailyPaymentEntryDTO] = field(default_factory=list)
    payments_by_cashier: list[NamedTotalDTO] = field(default_factory=list)
    total_cash_in: Decimal = Decimal(0)
    by_cashier: list[CashierClosingRowDTO] = field(default_factory=list)


class SalesHistoryViewModel(QObject):
    sales_loaded = Signal(list)
    daily_summary_loaded = Signal(object)
    """Emite `DailyClosingSummaryDTO` — Resumen Diario de Caja."""
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(
        self,
        sales_service: SalesService,
        inventory_service: InventoryService,
        billing_service: BillingService,
        session_manager: SessionManager,
        receipt_printer: ReceiptPrinter,
        user_service: UserManagementService,
        cash_register_service: CashRegisterService,
        printer_service: PrinterService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._sales_service = sales_service
        self._inventory_service = inventory_service
        self._billing_service = billing_service
        self._session_manager = session_manager
        self._receipt_printer = receipt_printer
        self._cash_register_service = cash_register_service
        self._printer_service = printer_service
        self._user_service = user_service

    def load(self) -> None:
        self.sales_loaded.emit(self._sales_service.list_recent_sales())
        self._load_daily_summary()

    def _load_daily_summary(self) -> None:
        start, end = today_utc_bounds()
        sales_totals = self._sales_service.get_daily_totals(start, end)
        payment_summary = self._billing_service.get_daily_payment_summary(start, end)
        users_by_id = {u.id: u.full_name for u in self._user_service.list_users()}

        sales_by_cashier = [
            NamedTotalDTO(name=users_by_id.get(c.user_id, "—"), total=c.total)
            for c in sales_totals.by_cashier
        ]
        payments_by_cashier = [
            NamedTotalDTO(name=c.cashier_name, total=c.total) for c in payment_summary.by_cashier
        ]

        sales_by_user = {c.user_id: c.total for c in sales_totals.by_cashier}
        payments_by_user = {c.user_id: c.total for c in payment_summary.by_cashier}
        combined = [
            CashierClosingRowDTO(
                cashier_name=users_by_id.get(user_id, "—"),
                sales_total=sales_by_user.get(user_id, Decimal(0)),
                payments_total=payments_by_user.get(user_id, Decimal(0)),
                total_received=(
                    sales_by_user.get(user_id, Decimal(0))
                    + payments_by_user.get(user_id, Decimal(0))
                ),
            )
            for user_id in sorted(set(sales_by_user) | set(payments_by_user))
        ]

        self.daily_summary_loaded.emit(
            DailyClosingSummaryDTO(
                sales_total=sales_totals.total,
                sales_by_cashier=sales_by_cashier,
                payments_total=payment_summary.total,
                payment_entries=payment_summary.entries,
                payments_by_cashier=payments_by_cashier,
                total_cash_in=sales_totals.total + payment_summary.total,
                by_cashier=combined,
            )
        )

    def generate_invoice(self, sale_id: int) -> None:
        try:
            sale = self._sales_service.get_sale(sale_id)
            credit_amount = sum(
                (p.amount for p in sale.payments if p.payment_method is PaymentMethod.CUSTOMER_CREDIT),
                Decimal(0),
            )
            """Sin esto, regenerar (o generar tardíamente) la factura de una
            venta a crédito la dejaba con `balance_due=0` por defecto — ver
            el mismo cálculo en `sale_view_model.py`."""
            invoice = self._billing_service.generate_invoice(sale_id, credit_amount=credit_amount)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(
                f"Factura {invoice.invoice_number} generada: {invoice.pdf_path}"
            )

    def open_invoice_pdf(self, sale_id: int) -> None:
        """Reimprime la factura de esta venta — la genera primero si
        todavía no existe (`generate_invoice` es idempotente: si ya existe,
        la devuelve tal cual sin regenerarla ni cambiar su número). La
        envía a la impresora asignada a la caja donde se hizo la venta, o
        al visor del sistema si no hay ninguna configurada."""
        sale = self._sales_service.get_sale(sale_id)
        cash_register_id = None
        if sale.cash_session_id is not None:
            cash_session = self._cash_register_service.get_session(sale.cash_session_id)
            cash_register_id = cash_session.cash_register_id if cash_session is not None else None
        current_user = self._session_manager.current
        try:
            outcome = print_invoice_for_sale(
                billing_service=self._billing_service,
                printer_service=self._printer_service,
                receipt_printer=self._receipt_printer,
                sale_id=sale_id,
                cash_register_id=cash_register_id,
                user_id=current_user.user_id if current_user is not None else None,
                username=current_user.username if current_user is not None else None,
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
            return
        if not outcome.printed:
            self.error_occurred.emit(outcome.error or "No se pudo imprimir la factura.")

    def void_sale(self, sale_id: int, reason: str) -> None:
        default_warehouse = next(iter(self._inventory_service.list_warehouses()), None)
        if default_warehouse is None:
            self.error_occurred.emit("No hay ninguna bodega configurada.")
            return
        current_user = self._session_manager.current
        try:
            self._sales_service.void_sale(
                sale_id=sale_id,
                warehouse_id=default_warehouse.id,
                reason=reason or None,
                created_by_user_id=current_user.user_id if current_user is not None else None,
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Venta #{sale_id} anulada.")
            self.load()
