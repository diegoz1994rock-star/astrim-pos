"""Caso de uso de Facturación (PROJECT_SPEC.md, "FACTURACIÓN"): genera un
comprobante PDF a partir de una venta ya completada, y — como Cuentas por
Cobrar — administra el saldo pendiente de las facturas de crédito y sus
abonos.

Lee `sales` (la venta) y `customers` (para el snapshot del cliente) a
través de sus servicios de aplicación — no de sus repositorios
directamente, a diferencia de otros módulos de esta pasada — porque ambos
ya exponen exactamente los datos de solo lectura que hacen falta aquí sin
necesidad de tocar su capa de infraestructura (ARCHITECTURE.md §12b permite
ambas formas; se prefiere la de menor acoplamiento cuando el servicio ya
existe).
"""

from __future__ import annotations

import contextlib
import platform
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError, NotFoundError
from pos.modules.billing.application.dto import (
    CashierPaymentTotalDTO,
    DailyPaymentEntryDTO,
    DailyPaymentSummaryDTO,
    DebtPaymentReceiptEntryDTO,
    InvoiceDTO,
    InvoiceHistoryEntryDTO,
)
from pos.modules.billing.infrastructure.models import Invoice
from pos.modules.billing.infrastructure.pdf_renderer import (
    render_debt_payment_receipt_pdf,
    render_invoice_pdf,
)
from pos.modules.billing.infrastructure.repository import BillingRepository
from pos.modules.cash_drawers.application.cash_drawer_service import CashDrawerService
from pos.modules.cash_drawers.domain.enums import CashDrawerOpeningKind
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.cash_register.domain.enums import CashMovementType
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.customers.infrastructure.models import CreditMovementType
from pos.modules.invoice_settings.application.invoice_settings_service import (
    InvoiceSettingsService,
)
from pos.modules.sales.application.sale_service import SalesService
from pos.modules.sales.domain.enums import PaymentMethod, SaleStatus
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.modules.users.application.user_management_service import UserManagementService

_CREDIT_TERM_DAYS = 90
"""Plazo de crédito por defecto: una factura de crédito vence 90 días
después de emitida (`due_date`), a menos que se pague antes."""

_PAYMENT_METHOD_LABELS = {
    PaymentMethod.CASH: "Efectivo",
    PaymentMethod.CARD: "Tarjeta",
    PaymentMethod.TRANSFER: "Transferencia",
    PaymentMethod.NEQUI: "Nequi",
    PaymentMethod.DAVIPLATA: "Daviplata",
    PaymentMethod.QR: "QR",
    PaymentMethod.BRE_B: "Bre-B",
    PaymentMethod.OTHER: "Otro",
}


def _to_dto(invoice: Invoice) -> InvoiceDTO:
    return InvoiceDTO(
        id=invoice.id,
        sale_id=invoice.sale_id,
        invoice_number=invoice.invoice_number,
        issued_at=invoice.issued_at,
        customer_name_snapshot=invoice.customer_name_snapshot,
        customer_document_snapshot=invoice.customer_document_snapshot,
        tax_total=invoice.tax_total,
        total=invoice.total,
        pdf_path=invoice.pdf_path,
        balance_due=invoice.balance_due,
    )


class BillingService:
    def __init__(
        self,
        sales_service: SalesService,
        customer_service: CustomerManagementService,
        settings_service: BusinessSettingsService,
        invoice_settings_service: InvoiceSettingsService,
        user_service: UserManagementService,
        cash_register_service: CashRegisterService,
        cash_drawer_service: CashDrawerService,
        invoices_dir: Path,
    ) -> None:
        self._sales_service = sales_service
        self._customer_service = customer_service
        self._settings_service = settings_service
        self._invoice_settings_service = invoice_settings_service
        self._user_service = user_service
        self._cash_register_service = cash_register_service
        self._cash_drawer_service = cash_drawer_service
        self._invoices_dir = invoices_dir

    def generate_invoice(
        self, sale_id: int, *, credit_amount: Decimal = Decimal(0)
    ) -> InvoiceDTO:
        """`credit_amount` es el componente de la venta pagado con
        `PaymentMethod.CUSTOMER_CREDIT` (0 en el caso normal) — se guarda
        como `balance_due` de la factura recién creada, y fija su
        `due_date` a `_CREDIT_TERM_DAYS` días desde hoy (facturas de
        contado quedan con `due_date=None`, nunca vencen). Si la factura
        ya existía (llamada idempotente), `credit_amount` se ignora — el
        saldo pendiente y el vencimiento ya quedaron fijados por quien la
        creó la primera vez."""
        sale = self._sales_service.get_sale(sale_id)
        if sale.status is not SaleStatus.COMPLETED:
            raise BusinessRuleViolationError(
                "Solo se puede facturar una venta completada (no anulada ni en borrador)."
            )

        with session_scope() as session:
            repo = BillingRepository(session)
            existing = repo.get_by_sale_id(sale_id)
            if existing is not None:
                return _to_dto(existing)

            invoice_number = f"F-{repo.count() + 1:06d}"
            customer_name = sale.customer_name
            customer_document = sale.customer_document
            if not customer_name and sale.customer_id is not None:
                customer = self._customer_service.get_customer(sale.customer_id)
                if customer is not None:
                    customer_name = customer.full_name
                    customer_document = customer.document_id
            customer_name = customer_name or "Sin nombre"
            customer_document = customer_document or "Sin documento"

            issued_at = datetime.now(UTC)
            due_date = (
                (issued_at + timedelta(days=_CREDIT_TERM_DAYS)).date()
                if credit_amount > 0
                else None
            )
            invoice = repo.create_invoice(
                sale_id=sale_id,
                invoice_number=invoice_number,
                customer_name_snapshot=customer_name,
                customer_document_snapshot=customer_document,
                tax_total=sale.tax_total,
                total=sale.total,
                pdf_path=None,
                issued_at=issued_at,
                balance_due=credit_amount,
                due_date=due_date,
            )
            dto = _to_dto(invoice)

        settings = self._invoice_settings_service.get_settings()
        cashier_name = None
        if sale.created_by_user_id is not None:
            cashier_name = next(
                (
                    u.full_name
                    for u in self._user_service.list_users()
                    if u.id == sale.created_by_user_id
                ),
                None,
            )
        register_name = None
        if sale.cash_session_id is not None:
            cash_session = self._cash_register_service.get_session(sale.cash_session_id)
            if cash_session is not None:
                register_name = cash_session.cash_register_name

        pdf_path = self._invoices_dir / f"{invoice_number}.pdf"
        render_invoice_pdf(
            invoice=dto,
            sale=sale,
            settings=settings,
            file_path=pdf_path,
            cashier_name=cashier_name,
            register_name=register_name,
        )

        with session_scope() as session:
            repo = BillingRepository(session)
            stored = repo.get(dto.id)
            assert stored is not None
            stored.pdf_path = str(pdf_path)
            return _to_dto(stored)

    def list_customer_debt_history(self, customer_id: int) -> list[InvoiceHistoryEntryDTO]:
        """Todas las facturas (pendientes Y pagadas) de un cliente —
        alimenta la pestaña "Historial de facturas" de `CustomerHistoryDialog`.
        Oculta (sin borrar) lo emitido antes de `Customer.
        credit_history_cleared_at` ("Borrar historial", ver
        `CustomerManagementService.clear_credit_history`)."""
        customer = self._customer_service.get_customer(customer_id)
        cleared_at = customer.credit_history_cleared_at if customer is not None else None

        with session_scope() as session:
            repo = BillingRepository(session)
            invoices = repo.list_by_customer(customer_id, after=cleared_at)
            last_payments = repo.last_payment_dates([i.id for i in invoices])

        users_by_id = {u.id: u.full_name for u in self._user_service.list_users()}
        locations_by_register_id = {
            r.id: r.location or "—" for r in self._cash_register_service.list_all_registers()
        }
        today = datetime.now(UTC).date()
        entries: list[InvoiceHistoryEntryDTO] = []
        for invoice in invoices:
            sale = self._sales_service.get_sale(invoice.sale_id)
            cashier_name = (
                users_by_id.get(sale.created_by_user_id, "—")
                if sale.created_by_user_id is not None
                else "—"
            )
            register_name = "—"
            branch_location = "—"
            if sale.cash_session_id is not None:
                cash_session = self._cash_register_service.get_session(sale.cash_session_id)
                if cash_session is not None:
                    register_name = cash_session.cash_register_name
                    branch_location = locations_by_register_id.get(
                        cash_session.cash_register_id, "—"
                    )
            is_overdue = (
                invoice.due_date is not None
                and invoice.due_date < today
                and invoice.balance_due > 0
            )
            entries.append(
                InvoiceHistoryEntryDTO(
                    invoice_id=invoice.id,
                    sale_id=invoice.sale_id,
                    invoice_number=invoice.invoice_number,
                    issued_at=invoice.issued_at,
                    original_amount=invoice.total,
                    balance_due=invoice.balance_due,
                    paid_amount=invoice.total - invoice.balance_due,
                    status="Pendiente" if invoice.balance_due > 0 else "Pagada",
                    due_date=invoice.due_date,
                    is_overdue=is_overdue,
                    last_payment_at=last_payments.get(invoice.id),
                    cashier_name=cashier_name,
                    cash_register_name=register_name,
                    branch_location=branch_location,
                )
            )
        return entries

    def list_customer_payment_receipts(self, customer_id: int) -> list[DebtPaymentReceiptEntryDTO]:
        """Historial completo de abonos del cliente ("extracto bancario",
        pestaña "Historial de abonos") — nunca se borra; ver `register_payment`."""
        customer = self._customer_service.get_customer(customer_id)
        cleared_at = customer.credit_history_cleared_at if customer is not None else None

        with session_scope() as session:
            repo = BillingRepository(session)
            receipts = repo.list_receipts_by_customer(customer_id, after=cleared_at)
            invoice_numbers: dict[int, str] = {}
            for invoice_id in {r.invoice_id for r in receipts}:
                invoice = repo.get(invoice_id)
                assert invoice is not None
                invoice_numbers[invoice_id] = invoice.invoice_number

        users_by_id = {u.id: u.full_name for u in self._user_service.list_users()}
        cash_sessions_by_id = {
            cs.id: cs
            for cs in (
                self._cash_register_service.get_session(r.cash_session_id) for r in receipts
            )
            if cs is not None
        }
        entries = []
        for receipt in receipts:
            cash_session = cash_sessions_by_id.get(receipt.cash_session_id)
            entries.append(
                DebtPaymentReceiptEntryDTO(
                    receipt_number=receipt.receipt_number,
                    invoice_id=receipt.invoice_id,
                    invoice_number=invoice_numbers[receipt.invoice_id],
                    paid_at=receipt.paid_at,
                    amount=receipt.amount,
                    cashier_name=(
                        users_by_id.get(receipt.created_by_user_id, "—")
                        if receipt.created_by_user_id is not None
                        else "—"
                    ),
                    cash_register_name=(
                        cash_session.cash_register_name if cash_session is not None else "—"
                    ),
                    payment_method_label=_PAYMENT_METHOD_LABELS.get(
                        receipt.payment_method, receipt.payment_method.value
                    ),
                    note=receipt.note,
                    workstation=receipt.workstation,
                    pdf_path=receipt.pdf_path,
                )
            )
        return entries

    def register_payment(
        self,
        *,
        invoice_id: int,
        customer_id: int,
        amount: Decimal,
        payment_method: PaymentMethod,
        cash_session_id: int,
        note: str | None = None,
        created_by_user_id: int | None = None,
    ) -> DebtPaymentReceiptEntryDTO:
        """Registra un abono a UNA factura de crédito — parcial o total
        (nunca más que el saldo pendiente). Orden "menos a más reversible"
        (mismo criterio que `SalesService.complete_sale`): descuenta el
        saldo de la factura, abona al ledger de crédito del cliente
        (reutiliza `register_credit_movement` sin cambios), mueve caja si
        el pago es en efectivo, y por último emite el recibo (número
        secuencial + PDF) — así, si algo posterior fallara, lo que ya
        quedó guardado (saldo/ledger/caja) sigue siendo correcto incluso
        sin el PDF."""
        if amount <= 0:
            raise BusinessRuleViolationError("El monto del abono debe ser mayor que cero.")
        if payment_method is PaymentMethod.CUSTOMER_CREDIT:
            raise BusinessRuleViolationError(
                "No se puede pagar una deuda agregándola nuevamente a la deuda."
            )

        self._cash_register_service.require_open_session(cash_session_id)

        with session_scope() as session:
            invoice = BillingRepository(session).get(invoice_id)
        if invoice is None:
            raise NotFoundError(f"No existe la factura con id={invoice_id}.")
        sale = self._sales_service.get_sale(invoice.sale_id)
        if sale.customer_id != customer_id:
            raise BusinessRuleViolationError(
                f"La factura {invoice.invoice_number} no pertenece a este cliente."
            )
        if invoice.balance_due <= 0:
            raise BusinessRuleViolationError(
                f"La factura {invoice.invoice_number} ya está pagada — "
                "no se puede volver a cobrar."
            )
        if amount > invoice.balance_due:
            raise BusinessRuleViolationError(
                f"El abono ({amount}) no puede ser mayor que el saldo pendiente "
                f"de la factura ({invoice.balance_due})."
            )

        with session_scope() as session:
            repo = BillingRepository(session)
            new_balance = repo.apply_payment(invoice_id, amount)
            if new_balance is None:
                raise BusinessRuleViolationError(
                    f"El abono ({amount}) no puede ser mayor que el saldo pendiente "
                    "actual de la factura — probablemente ya se registró otro abono "
                    "concurrente. Actualizá la vista e intentá de nuevo."
                )
            invoice_number = invoice.invoice_number

        self._customer_service.register_credit_movement(
            customer_id=customer_id,
            movement_type=CreditMovementType.PAYMENT,
            amount=amount,
            reference=f"Abono a factura {invoice_number}",
            created_by_user_id=created_by_user_id,
        )

        if payment_method is PaymentMethod.CASH:
            self._cash_register_service.register_manual_movement(
                cash_session_id=cash_session_id,
                movement_type=CashMovementType.MANUAL_IN,
                amount=amount,
                reason=f"Abono a factura {invoice_number}",
                created_by_user_id=created_by_user_id,
            )

        remaining_balance = new_balance
        paid_at = datetime.now(UTC)
        workstation = platform.node() or None

        with session_scope() as session:
            repo = BillingRepository(session)
            receipt_number = f"R-{repo.count_receipts() + 1:06d}"
            receipt = repo.create_receipt(
                receipt_number=receipt_number,
                invoice_id=invoice_id,
                amount=amount,
                payment_method=payment_method,
                cash_session_id=cash_session_id,
                created_by_user_id=created_by_user_id,
                note=note,
                workstation=workstation,
                paid_at=paid_at,
            )
            receipt_number = receipt.receipt_number
            receipt_id = receipt.id

        pdf_path = self._render_receipt_pdf(
            invoice=invoice,
            invoice_number=invoice_number,
            receipt_number=receipt_number,
            amount=amount,
            remaining_balance=remaining_balance,
            paid_at=paid_at,
            customer_id=customer_id,
            cash_session_id=cash_session_id,
            created_by_user_id=created_by_user_id,
        )
        with session_scope() as session:
            BillingRepository(session).set_receipt_pdf_path(receipt_id, str(pdf_path))

        cashier_name = None
        if created_by_user_id is not None:
            cashier_name = next(
                (
                    u.full_name
                    for u in self._user_service.list_users()
                    if u.id == created_by_user_id
                ),
                None,
            )
        cash_session = self._cash_register_service.get_session(cash_session_id)
        register_name = cash_session.cash_register_name if cash_session is not None else "—"

        if payment_method is PaymentMethod.CASH and cash_session is not None:
            self._open_drawer_for_cash_abono(
                cash_register_id=cash_session.cash_register_id,
                created_by_user_id=created_by_user_id,
                username=cashier_name,
                invoice_id=invoice_id,
                debt_payment_id=receipt_id,
            )

        return DebtPaymentReceiptEntryDTO(
            receipt_number=receipt_number,
            invoice_id=invoice_id,
            invoice_number=invoice_number,
            paid_at=paid_at,
            amount=amount,
            cashier_name=cashier_name or "—",
            cash_register_name=register_name,
            payment_method_label=_PAYMENT_METHOD_LABELS.get(payment_method, payment_method.value),
            note=note,
            workstation=workstation,
            pdf_path=str(pdf_path),
        )

    def _open_drawer_for_cash_abono(
        self,
        *,
        cash_register_id: int,
        created_by_user_id: int | None,
        username: str | None,
        invoice_id: int,
        debt_payment_id: int,
    ) -> None:
        """Apertura automática del cajón monedero para un abono en
        efectivo — mismo principio que en Ventas (`SaleViewModel.
        open_drawer_if_applicable`): nunca sin usuario autenticado, nunca
        bloquea el abono ya registrado si el cajón no responde."""
        if created_by_user_id is None:
            return
        with contextlib.suppress(BusinessRuleViolationError):
            self._cash_drawer_service.open_drawer_for_cash_register(
                cash_register_id,
                user_id=created_by_user_id,
                username=username,
                opening_kind=CashDrawerOpeningKind.AUTOMATIC,
                invoice_id=invoice_id,
                debt_payment_id=debt_payment_id,
                reason="Abono en efectivo",
            )

    def _render_receipt_pdf(
        self,
        *,
        invoice: Invoice,
        invoice_number: str,
        receipt_number: str,
        amount: Decimal,
        remaining_balance: Decimal,
        paid_at: datetime,
        customer_id: int,
        cash_session_id: int,
        created_by_user_id: int | None,
    ) -> Path:
        sale = self._sales_service.get_sale(invoice.sale_id)
        customer = self._customer_service.get_customer(customer_id)
        customer_name = customer.full_name if customer is not None else "Consumidor final"
        customer_document = customer.document_id if customer is not None else None
        company_name = self._settings_service.get_str("business_name", "Mi Negocio") or "Mi Negocio"

        cashier_name = None
        if created_by_user_id is not None:
            cashier_name = next(
                (
                    u.full_name
                    for u in self._user_service.list_users()
                    if u.id == created_by_user_id
                ),
                None,
            )
        cash_session = self._cash_register_service.get_session(cash_session_id)
        register_name = cash_session.cash_register_name if cash_session is not None else None

        pdf_path = self._invoices_dir / f"{receipt_number}.pdf"
        render_debt_payment_receipt_pdf(
            file_path=pdf_path,
            company_name=company_name,
            customer_name=customer_name,
            customer_document=customer_document,
            receipt_number=receipt_number,
            invoice_number=invoice_number,
            items=sale.items,
            amount_paid=amount,
            remaining_balance=remaining_balance,
            paid_at=paid_at,
            cashier_name=cashier_name,
            register_name=register_name,
        )
        return pdf_path

    def get_daily_payment_summary(self, start: datetime, end: datetime) -> DailyPaymentSummaryDTO:
        """"Abonos recibidos hoy"/"Abonos por cajero" (Ventas → Historial)
        — agregado en SQL, de CUALQUIER cliente. A diferencia de
        `list_customer_payment_receipts`, NO filtra por `Customer.
        credit_history_cleared_at`: el cierre de caja del día debe
        reflejar el dinero real que entró hoy, sin importar si un cliente
        "borró" su propio historial después."""
        with session_scope() as session:
            repo = BillingRepository(session)
            rows = repo.list_receipts_in_range(start, end)
            total = repo.sum_receipts_in_range(start, end)
            cashier_totals = repo.receipt_totals_by_cashier(start, end)

        users_by_id = {u.id: u.full_name for u in self._user_service.list_users()}
        cash_session_cache: dict[int, str] = {}

        def _register_name(cash_session_id: int) -> str:
            if cash_session_id not in cash_session_cache:
                cash_session = self._cash_register_service.get_session(cash_session_id)
                cash_session_cache[cash_session_id] = (
                    cash_session.cash_register_name if cash_session is not None else "—"
                )
            return cash_session_cache[cash_session_id]

        entries = [
            DailyPaymentEntryDTO(
                customer_name=customer_name_snapshot or "Consumidor final",
                invoice_number=invoice_number,
                amount=receipt.amount,
                paid_at=receipt.paid_at,
                cashier_name=(
                    users_by_id.get(receipt.created_by_user_id, "—")
                    if receipt.created_by_user_id is not None
                    else "—"
                ),
                cash_register_name=_register_name(receipt.cash_session_id),
                payment_method_label=_PAYMENT_METHOD_LABELS.get(
                    receipt.payment_method, receipt.payment_method.value
                ),
            )
            for receipt, invoice_number, customer_name_snapshot in rows
        ]

        by_cashier = [
            CashierPaymentTotalDTO(
                user_id=user_id, cashier_name=users_by_id.get(user_id, "—"), total=cashier_total
            )
            for user_id, cashier_total in cashier_totals
            if user_id is not None
        ]

        return DailyPaymentSummaryDTO(total=total, entries=entries, by_cashier=by_cashier)

    def get_invoice_for_sale(self, sale_id: int) -> InvoiceDTO | None:
        with session_scope() as session:
            invoice = BillingRepository(session).get_by_sale_id(sale_id)
            return _to_dto(invoice) if invoice is not None else None

    def list_invoices(self, limit: int = 100) -> list[InvoiceDTO]:
        with session_scope() as session:
            return [_to_dto(i) for i in BillingRepository(session).list_all(limit)]
