"""Caso de uso central de Ventas: completar y anular una venta.

Orquesta Productos (precios/impuestos), Inventario (descuento de stock),
Caja (movimiento de efectivo) y Clientes (cargo a crédito) como llamadas
directas síncronas — no eventos — porque todos esos efectos deben tener
éxito atómicamente junto con la venta (ver ARCHITECTURE.md §5b).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, NotFoundError
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.customers.infrastructure.models import CreditMovementType
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.products.domain.enums import SaleUnit
from pos.modules.products.infrastructure.product_repository import ProductRepository
from pos.modules.sales.application.dto import (
    CashierSalesTotalDTO,
    DailySalesTotalsDTO,
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
from pos.modules.sales.domain.payment_totals import cash_amount
from pos.modules.sales.infrastructure.models import Sale
from pos.modules.sales.infrastructure.repository import SaleRepository
from pos.modules.scales.domain.enums import WeightEntrySource
from pos.modules.taxes.infrastructure.repository import TaxRepository

_ROUNDING_TOLERANCE = Decimal("0.01")


@dataclass(frozen=True)
class _PricedLine:
    product_id: int
    product_name: str
    track_inventory: bool
    quantity: Decimal
    unit_price: Decimal
    unit_cost: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    line_total: Decimal
    note: str | None = None
    sale_unit: SaleUnit = SaleUnit.UNIT
    unit_of_measure: str = "unidad"
    weight_entry_source: WeightEntrySource | None = None


@dataclass(frozen=True)
class _PricedSale:
    lines: list[_PricedLine]
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal


def _price_items(
    product_repo: ProductRepository, tax_repo: TaxRepository, items: list[SaleItemInput]
) -> _PricedSale:
    """Calcula precios, descuentos e impuestos de cada línea. Función pura
    de lectura, reutilizada tanto por la vista previa del carrito como por
    `complete_sale` — una sola fuente de verdad para el cálculo de totales.

    El impuesto ya no se elige por producto: se suma la tasa de todos los
    impuestos activos (`TaxRepository.list_active`, administrados desde
    Administración → Impuestos) una sola vez por venta y se aplica a cada
    línea por igual. Si no hay ningún impuesto activo, la tasa es `0` y la
    venta/factura sale sin impuestos.
    """
    tax_rate = sum((tax.rate_percent for tax in tax_repo.list_active()), Decimal(0))

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
        if product.sale_unit is SaleUnit.WEIGHT:
            if product.min_weight is not None and item_input.quantity < product.min_weight:
                raise BusinessRuleViolationError(
                    f"El peso de '{product.name}' ({item_input.quantity} "
                    f"{product.unit_of_measure}) es menor al mínimo permitido "
                    f"({product.min_weight} {product.unit_of_measure})."
                )
            if product.max_weight is not None and item_input.quantity > product.max_weight:
                raise BusinessRuleViolationError(
                    f"El peso de '{product.name}' ({item_input.quantity} "
                    f"{product.unit_of_measure}) supera el máximo permitido "
                    f"({product.max_weight} {product.unit_of_measure})."
                )

        unit_price = product.unit_price
        line_subtotal = unit_price * item_input.quantity
        if item_input.discount_amount > line_subtotal:
            raise BusinessRuleViolationError(
                f"El descuento de '{product.name}' no puede superar el subtotal de la línea."
            )
        taxable_base = line_subtotal - item_input.discount_amount
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
                unit_price=unit_price,
                unit_cost=product.cost_price,
                discount_amount=item_input.discount_amount,
                tax_amount=line_tax,
                line_total=line_total,
                note=item_input.note,
                sale_unit=product.sale_unit,
                unit_of_measure=product.unit_of_measure,
                weight_entry_source=item_input.weight_entry_source,
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
                note=line.note,
                sale_unit=line.sale_unit,
                unit_of_measure=line.unit_of_measure,
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
        created_by_user_id=sale.created_by_user_id,
        cash_session_id=sale.cash_session_id,
        customer_name=sale.customer_name,
        customer_document=sale.customer_document,
        items=[
            SaleItemDTO(
                id=item.id,
                product_id=item.product_id,
                product_name=product_names[item.product_id],
                quantity=item.quantity,
                unit_price=item.unit_price,
                unit_cost=item.unit_cost,
                discount_amount=item.discount_amount,
                tax_amount=item.tax_amount,
                line_total=item.line_total,
                note=item.note,
                sale_unit=item.sale_unit,
                unit_of_measure=item.unit_of_measure,
                weight_entry_source=item.weight_entry_source,
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
            priced = _price_items(ProductRepository(session), TaxRepository(session), items)
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
        customer_name: str | None = None,
        customer_document: str | None = None,
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
            priced = _price_items(ProductRepository(session), TaxRepository(session), items)

        payments_total = sum((p.amount for p in payments), Decimal(0))
        if abs(payments_total - priced.total) > _ROUNDING_TOLERANCE:
            raise BusinessRuleViolationError(
                f"El total de los pagos ({payments_total}) no coincide "
                f"con el total de la venta ({priced.total})."
            )

        for line in priced.lines:
            if not line.track_inventory:
                continue
            available = self._inventory_service.get_total_available_quantity(line.product_id)
            if available < line.quantity:
                raise BusinessRuleViolationError(
                    f"Stock insuficiente para '{line.product_name}': "
                    f"disponible {available}, solicitado {line.quantity}."
                )

        cash_total = cash_amount(payments)
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
                customer_name=customer_name.strip() if customer_name else None,
                customer_document=customer_document.strip() if customer_document else None,
            )
            for line in priced.lines:
                sale_repo.add_item(
                    sale_id=sale.id,
                    product_id=line.product_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    unit_cost=line.unit_cost,
                    discount_amount=line.discount_amount,
                    tax_amount=line.tax_amount,
                    line_total=line.line_total,
                    note=line.note,
                    sale_unit=line.sale_unit,
                    unit_of_measure=line.unit_of_measure,
                    weight_entry_source=line.weight_entry_source,
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
        try:
            for line in priced.lines:
                if not line.track_inventory:
                    continue
                self._allocate_and_register_exit(
                    product_id=line.product_id,
                    preferred_warehouse_id=warehouse_id,
                    quantity=line.quantity,
                    reason=f"Venta #{sale_id}",
                    created_by_user_id=created_by_user_id,
                    sale_id=sale_id,
                )
        except BusinessRuleViolationError:
            """Una línea posterior puede fallar (ej. stock agotado por una
            venta concurrente entre el chequeo y esta descuenta) dejando la
            venta ya COMPLETED con solo parte del inventario descontado. Se
            repone exactamente lo que sí llegó a descontarse (vía el mismo
            desglose por referencia que usa `void_sale`) y se marca la venta
            como REFUNDED en vez de dejarla completada a medias — todavía no
            se registró ningún movimiento de caja/crédito en este punto."""
            exit_breakdown = self._inventory_service.get_exit_breakdown_by_reference(
                reference_document_type="sale", reference_document_id=sale_id
            )
            for product_id, allocations in exit_breakdown.items():
                for allocation_warehouse_id, allocation_quantity in allocations:
                    self._inventory_service.register_entry(
                        product_id=product_id,
                        warehouse_id=allocation_warehouse_id,
                        quantity=allocation_quantity,
                        reason=f"Reversión automática de venta #{sale_id} (fallo de inventario)",
                        created_by_user_id=created_by_user_id,
                    )
            with session_scope() as session:
                sale_repo = SaleRepository(session)
                failed_sale = sale_repo.get(sale_id)
                if failed_sale is not None:
                    sale_repo.set_status(failed_sale, SaleStatus.REFUNDED)
            raise
        if cash_total > 0:
            self._cash_register_service.register_sale_movement(
                cash_session_id=cash_session_id, amount=cash_total
            )

        with session_scope() as session:
            sale_with_details = SaleRepository(session).get_with_details(sale_id)
            assert sale_with_details is not None
            dto = _sale_dto(sale_with_details, session)

        self._event_bus.publish(
            SaleCompletedEvent(
                sale_id=sale_id,
                total=priced.total,
                customer_id=customer_id,
                created_by_user_id=created_by_user_id,
            )
        )
        return dto

    def _allocate_and_register_exit(
        self,
        *,
        product_id: int,
        preferred_warehouse_id: int,
        quantity: Decimal,
        reason: str,
        created_by_user_id: int | None,
        sale_id: int,
    ) -> None:
        """Reparte la salida entre bodegas cuando la preferida no alcanza:
        descuenta primero de `preferred_warehouse_id`, y si falta, de las
        demás bodegas del producto en el orden que ya expone
        `get_stock_detail`, hasta cubrir la cantidad — la venta ya fue
        validada contra el inventario general antes de llegar acá, así que
        siempre hay suficiente entre todas las bodegas."""
        remaining = quantity
        stock_detail = self._inventory_service.get_stock_detail(product_id)
        ordered = sorted(stock_detail, key=lambda s: s.warehouse_id != preferred_warehouse_id)
        for level in ordered:
            if remaining <= 0:
                break
            take = min(remaining, level.quantity)
            if take <= 0:
                continue
            self._inventory_service.register_exit(
                product_id=product_id,
                warehouse_id=level.warehouse_id,
                quantity=take,
                reason=reason,
                created_by_user_id=created_by_user_id,
                reference_document_type="sale",
                reference_document_id=sale_id,
            )
            remaining -= take

    def get_sale(self, sale_id: int) -> SaleDTO:
        with session_scope() as session:
            sale = SaleRepository(session).get_with_details(sale_id)
            if sale is None:
                raise NotFoundError(f"No existe la venta con id={sale_id}.")
            return _sale_dto(sale, session)

    def list_recent_sales(self, limit: int = 50) -> list[SaleDTO]:
        with session_scope() as session:
            return [_sale_dto(sale, session) for sale in SaleRepository(session).list_recent(limit)]

    def get_daily_totals(self, start: datetime, end: datetime) -> DailySalesTotalsDTO:
        """Ventas del día / Ventas por cajero (Ventas → Historial) — todo
        agregado en SQL (`SaleRepository.sum_completed_total`/
        `totals_by_cashier`), nunca recorriendo la lista de ventas."""
        with session_scope() as session:
            repo = SaleRepository(session)
            total = repo.sum_completed_total(start, end)
            by_cashier = [
                CashierSalesTotalDTO(user_id=user_id, total=cashier_total)
                for user_id, cashier_total in repo.totals_by_cashier(start, end)
                if user_id is not None
            ]
        return DailySalesTotalsDTO(total=total, by_cashier=by_cashier)

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
            cash_total = cash_amount(sale.payments)
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

        exit_breakdown = self._inventory_service.get_exit_breakdown_by_reference(
            reference_document_type="sale", reference_document_id=sale_id
        )
        """Repone cada cantidad a la(s) bodega(s) real(es) de donde salió
        (`_allocate_and_register_exit` puede repartir una misma línea entre
        varias) en vez de asumir que toda la venta salió de `warehouse_id` —
        de lo contrario una venta multi-bodega queda descuadrada al anular.
        `warehouse_id` solo se usa como respaldo para ventas anteriores a
        este fix, que no tienen movimientos con referencia registrada."""
        with session_scope() as session:
            product_repo = ProductRepository(session)
            for product_id, quantity in items_snapshot:
                product = product_repo.get(product_id)
                if product is None or not product.track_inventory:
                    continue
                allocations = exit_breakdown.get(product_id) or [(warehouse_id, quantity)]
                for allocation_warehouse_id, allocation_quantity in allocations:
                    self._inventory_service.register_entry(
                        product_id=product_id,
                        warehouse_id=allocation_warehouse_id,
                        quantity=allocation_quantity,
                        reason=f"Anulación de venta #{sale_id}",
                        created_by_user_id=created_by_user_id,
                    )

        if cash_total > 0 and cash_session_id is not None:
            self._cash_register_service.register_refund_movement(
                cash_session_id=cash_session_id,
                amount=cash_total,
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

        self._event_bus.publish(
            SaleVoidedEvent(sale_id=sale_id, reason=reason, voided_by_user_id=created_by_user_id)
        )
        return self.get_sale(sale_id)
