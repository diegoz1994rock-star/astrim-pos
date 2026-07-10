"""Caso de uso central de Ventas: completar y anular una venta.

Orquesta Productos (precios/impuestos), Inventario (descuento de stock),
Caja (movimiento de efectivo) y Clientes (cargo a crédito) como llamadas
directas síncronas — no eventos — porque todos esos efectos deben tener
éxito atómicamente junto con la venta (ver ARCHITECTURE.md §5b).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, NotFoundError
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.customers.infrastructure.models import CreditMovementType
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.products.infrastructure.product_repository import ProductRepository
from pos.modules.sales.application.dto import (
    SaleDTO,
    SaleItemDTO,
    SaleItemInput,
    SalePaymentDTO,
    SalePaymentInput,
    SalePreviewDTO,
    SalePreviewLineDTO,
)
from pos.modules.sales.domain.enums import PaymentMethod, SaleStatus, SaleType
from pos.modules.sales.domain.events import SaleCompletedEvent, SaleVoidedEvent
from pos.modules.sales.infrastructure.models import Sale
from pos.modules.sales.infrastructure.repository import SaleRepository

_ROUNDING_TOLERANCE = Decimal("0.01")


@dataclass(frozen=True)
class _PricedLine:
    product_id: int
    product_name: str
    track_inventory: bool
    quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class _PricedSale:
    lines: list[_PricedLine]
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal


def _price_items(product_repo: ProductRepository, items: list[SaleItemInput]) -> _PricedSale:
    """Calcula precios, descuentos e impuestos de cada línea. Función pura
    de lectura, reutilizada tanto por la vista previa del carrito como por
    `complete_sale` — una sola fuente de verdad para el cálculo de totales.
    """
    lines: list[_PricedLine] = []
    subtotal = Decimal(0)
    discount_total = Decimal(0)
    tax_total = Decimal(0)

    for item_input in items:
        if item_input.quantity <= 0:
            raise BusinessRuleViolationError("La cantidad de cada línea debe ser mayor que cero.")
        product = product_repo.get(item_input.product_id)
        if product is None:
            raise NotFoundError(f"No existe el producto con id={item_input.product_id}.")
        if not product.is_active:
            raise BusinessRuleViolationError(f"El producto '{product.name}' no está activo.")

        line_subtotal = product.unit_price * item_input.quantity
        if item_input.discount_amount > line_subtotal:
            raise BusinessRuleViolationError(
                f"El descuento de '{product.name}' no puede superar el subtotal de la línea."
            )
        taxable_base = line_subtotal - item_input.discount_amount
        tax_rate = sum(
            (tax.rate_percent for tax in product_repo.get_taxes_for_product(product.id)),
            Decimal(0),
        )
        line_tax = (taxable_base * tax_rate / Decimal(100)).quantize(Decimal("0.01"))
        line_total = taxable_base + line_tax

        subtotal += line_subtotal
        discount_total += item_input.discount_amount
        tax_total += line_tax

        lines.append(
            _PricedLine(
                product_id=product.id,
                product_name=product.name,
                track_inventory=product.track_inventory,
                quantity=item_input.quantity,
                unit_price=product.unit_price,
                discount_amount=item_input.discount_amount,
                tax_amount=line_tax,
                line_total=line_total,
            )
        )

    total = subtotal - discount_total + tax_total
    return _PricedSale(
        lines=lines,
        subtotal=subtotal,
        discount_total=discount_total,
        tax_total=tax_total,
        total=total,
    )


def _preview_dto(priced: _PricedSale) -> SalePreviewDTO:
    return SalePreviewDTO(
        subtotal=priced.subtotal,
        discount_total=priced.discount_total,
        tax_total=priced.tax_total,
        total=priced.total,
        items=[
            SalePreviewLineDTO(
                product_id=line.product_id,
                product_name=line.product_name,
                quantity=line.quantity,
                unit_price=line.unit_price,
                discount_amount=line.discount_amount,
                tax_amount=line.tax_amount,
                line_total=line.line_total,
            )
            for line in priced.lines
        ],
    )


def _sale_dto(sale: Sale, session: Session) -> SaleDTO:
    product_repo = ProductRepository(session)
    product_names: dict[int, str] = {}
    for item in sale.items:
        if item.product_id not in product_names:
            product = product_repo.get(item.product_id)
            product_names[item.product_id] = product.name if product is not None else "?"

    return SaleDTO(
        id=sale.id,
        status=sale.status,
        sale_type=sale.sale_type,
        customer_id=sale.customer_id,
        subtotal=sale.subtotal,
        discount_total=sale.discount_total,
        tax_total=sale.tax_total,
        total=sale.total,
        created_at=sale.created_at,
        items=[
            SaleItemDTO(
                id=item.id,
                product_id=item.product_id,
                product_name=product_names[item.product_id],
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount_amount=item.discount_amount,
                tax_amount=item.tax_amount,
                line_total=item.line_total,
            )
            for item in sale.items
        ],
        payments=[
            SalePaymentDTO(
                id=payment.id,
                payment_method=payment.payment_method,
                amount=payment.amount,
                reference=payment.reference,
            )
            for payment in sale.payments
        ],
    )


class SalesService:
    def __init__(
        self,
        event_bus: EventBus,
        inventory_service: InventoryService,
        cash_register_service: CashRegisterService,
        customer_service: CustomerManagementService,
    ) -> None:
        self._event_bus = event_bus
        self._inventory_service = inventory_service
        self._cash_register_service = cash_register_service
        self._customer_service = customer_service

    def preview_sale(self, items: list[SaleItemInput]) -> SalePreviewDTO:
        """Calcula subtotal/descuentos/impuestos/total sin persistir nada,
        para que la UI del carrito muestre el total en tiempo real."""
        with session_scope() as session:
            priced = _price_items(ProductRepository(session), items)
            return _preview_dto(priced)

    def complete_sale(
        self,
        *,
        items: list[SaleItemInput],
        payments: list[SalePaymentInput],
        cash_session_id: int,
        warehouse_id: int,
        customer_id: int | None = None,
        sale_type: SaleType = SaleType.COUNTER,
        created_by_user_id: int | None = None,
    ) -> SaleDTO:
        if not items:
            raise BusinessRuleViolationError("La venta debe tener al menos un producto.")
        if not payments:
            raise BusinessRuleViolationError("La venta debe tener al menos un medio de pago.")

        credit_payments = [p for p in payments if p.payment_method is PaymentMethod.CUSTOMER_CREDIT]
        if credit_payments and customer_id is None:
            raise BusinessRuleViolationError("Un pago a crédito requiere seleccionar un cliente.")

        self._cash_register_service.require_open_session(cash_session_id)

        # --- Paso 1: calcular líneas y validar stock disponible (solo lectura) ---
        with session_scope() as session:
            priced = _price_items(ProductRepository(session), items)

        payments_total = sum((p.amount for p in payments), Decimal(0))
        if abs(payments_total - priced.total) > _ROUNDING_TOLERANCE:
            raise BusinessRuleViolationError(
                f"El total de los pagos ({payments_total}) no coincide "
                f"con el total de la venta ({priced.total})."
            )

        for line in priced.lines:
            if not line.track_inventory:
                continue
            available = self._inventory_service.get_available_quantity(
                line.product_id, warehouse_id
            )
            if available < line.quantity:
                raise BusinessRuleViolationError(
                    f"Stock insuficiente para '{line.product_name}': "
                    f"disponible {available}, solicitado {line.quantity}."
                )

        cash_amount = sum(
            (p.amount for p in payments if p.payment_method is PaymentMethod.CASH), Decimal(0)
        )
        credit_amount = sum((p.amount for p in credit_payments), Decimal(0))
        if credit_amount > 0:
            # Valida el cupo disponible antes de mutar nada (ver ARCHITECTURE.md §5b).
            self._customer_service.register_credit_movement(
                customer_id=customer_id,  # type: ignore[arg-type]
                movement_type=CreditMovementType.CHARGE,
                amount=credit_amount,
                reference=None,
                created_by_user_id=created_by_user_id,
            )

        # --- Paso 2: persistir la venta ---
        with session_scope() as session:
            sale_repo = SaleRepository(session)
            sale = sale_repo.create_sale(
                customer_id=customer_id,
                cash_session_id=cash_session_id,
                sale_type=sale_type,
                created_by_user_id=created_by_user_id,
            )
            for line in priced.lines:
                sale_repo.add_item(
                    sale_id=sale.id,
                    product_id=line.product_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    discount_amount=line.discount_amount,
                    tax_amount=line.tax_amount,
                    line_total=line.line_total,
                )
            for payment in payments:
                sale_repo.add_payment(
                    sale_id=sale.id,
                    payment_method=payment.payment_method,
                    amount=payment.amount,
                    reference=payment.reference,
                )
            sale_repo.update_totals(
                sale,
                subtotal=priced.subtotal,
                discount_total=priced.discount_total,
                tax_total=priced.tax_total,
                total=priced.total,
            )
            sale_repo.set_status(sale, SaleStatus.COMPLETED)
            sale_id = sale.id

        # --- Paso 3: efectos críticos en otros módulos (orden: menos a más reversible) ---
        for line in priced.lines:
            if not line.track_inventory:
                continue
            self._inventory_service.register_exit(
                product_id=line.product_id,
                warehouse_id=warehouse_id,
                quantity=line.quantity,
                reason=f"Venta #{sale_id}",
                created_by_user_id=created_by_user_id,
            )
        if cash_amount > 0:
            self._cash_register_service.register_sale_movement(
                cash_session_id=cash_session_id, amount=cash_amount
            )

        with session_scope() as session:
            sale_with_details = SaleRepository(session).get_with_details(sale_id)
            assert sale_with_details is not None
            dto = _sale_dto(sale_with_details, session)

        self._event_bus.publish(
            SaleCompletedEvent(sale_id=sale_id, total=priced.total, customer_id=customer_id)
        )
        return dto

    def get_sale(self, sale_id: int) -> SaleDTO:
        with session_scope() as session:
            sale = SaleRepository(session).get_with_details(sale_id)
            if sale is None:
                raise NotFoundError(f"No existe la venta con id={sale_id}.")
            return _sale_dto(sale, session)

    def list_recent_sales(self, limit: int = 50) -> list[SaleDTO]:
        with session_scope() as session:
            return [_sale_dto(sale, session) for sale in SaleRepository(session).list_recent(limit)]

    def void_sale(
        self, *, sale_id: int, warehouse_id: int, reason: str | None, created_by_user_id: int | None
    ) -> SaleDTO:
        """Anula una venta completada: revierte stock, efectivo y crédito."""
        with session_scope() as session:
            sale_repo = SaleRepository(session)
            sale = sale_repo.get_with_details(sale_id)
            if sale is None:
                raise NotFoundError(f"No existe la venta con id={sale_id}.")
            if sale.status is not SaleStatus.COMPLETED:
                raise BusinessRuleViolationError("Solo se pueden anular ventas completadas.")

            items_snapshot = [(item.product_id, item.quantity) for item in sale.items]
            cash_amount = sum(
                (p.amount for p in sale.payments if p.payment_method is PaymentMethod.CASH),
                Decimal(0),
            )
            credit_amount = sum(
                (
                    p.amount
                    for p in sale.payments
                    if p.payment_method is PaymentMethod.CUSTOMER_CREDIT
                ),
                Decimal(0),
            )
            customer_id = sale.customer_id
            cash_session_id = sale.cash_session_id

            sale_repo.set_status(sale, SaleStatus.REFUNDED)

        with session_scope() as session:
            product_repo = ProductRepository(session)
            for product_id, quantity in items_snapshot:
                product = product_repo.get(product_id)
                if product is not None and product.track_inventory:
                    self._inventory_service.register_entry(
                        product_id=product_id,
                        warehouse_id=warehouse_id,
                        quantity=quantity,
                        reason=f"Anulación de venta #{sale_id}",
                        created_by_user_id=created_by_user_id,
                    )

        if cash_amount > 0 and cash_session_id is not None:
            self._cash_register_service.register_refund_movement(
                cash_session_id=cash_session_id,
                amount=cash_amount,
                reason=f"Anulación de venta #{sale_id}",
            )
        if credit_amount > 0 and customer_id is not None:
            self._customer_service.register_credit_movement(
                customer_id=customer_id,
                movement_type=CreditMovementType.PAYMENT,
                amount=credit_amount,
                reference=f"Anulación de venta #{sale_id}",
                created_by_user_id=created_by_user_id,
            )

        self._event_bus.publish(SaleVoidedEvent(sale_id=sale_id, reason=reason))
        return self.get_sale(sale_id)
