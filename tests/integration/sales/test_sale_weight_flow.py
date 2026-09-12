"""Prueba de integración del flujo completo de venta por peso: báscula
Simulador (sin hardware real) → lectura estable vía `ScaleReadService` →
`SalesService.complete_sale` con esa cantidad → cálculo precio×peso,
descuento exacto de inventario (sin redondeo), y rechazo de peso fuera del
rango mínimo/máximo del producto — cierra el círculo pedido explícitamente:
"todo el flujo... aunque no tengas una báscula física conectada"."""

from __future__ import annotations

import time
from decimal import Decimal

import pytest

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.products.domain.enums import ProductType, SaleUnit
from pos.modules.sales.application.dto import SaleItemInput, SalePaymentInput
from pos.modules.sales.domain.enums import PaymentMethod
from pos.modules.scales.application.scale_read_service import ScaleReadService
from pos.modules.scales.application.scale_service import ScaleService
from pos.modules.scales.domain.enums import WeightEntrySource
from tests.integration.sales.conftest import SalesFixtures

_SETTLE_SLEEP_SECONDS = 0.06


def _create_weight_product(sales_env: SalesFixtures, **overrides):
    kwargs = {
        "sku": "PESO-CARNE",
        "name": "Carne molida",
        "description": None,
        "category_id": None,
        "product_type": ProductType.SIMPLE,
        "unit_price": Decimal("20000"),  # por kg
        "cost_price": Decimal("12000"),
        "unit_of_measure": "kg",
        "track_inventory": True,
        "sale_unit": SaleUnit.WEIGHT,
    }
    kwargs.update(overrides)
    product_service = ProductManagementService(sales_env.event_bus)
    return product_service.create_product(**kwargs)


def _read_stable_weight_from_simulator(
    scale_service: ScaleService, read_service: ScaleReadService, device_id: int
) -> Decimal:
    for _ in range(15):
        reading = read_service.read(device_id=device_id)
        if reading.is_stable:
            return reading.net_weight
        time.sleep(_SETTLE_SLEEP_SECONDS)
    raise AssertionError("la báscula simulada no se estabilizó a tiempo")


def test_weight_product_sale_end_to_end_via_simulator_scale(sales_env: SalesFixtures) -> None:
    product_service = ProductManagementService(sales_env.event_bus)
    scale_service = ScaleService(sales_env.event_bus)
    read_service = ScaleReadService(scale_service, product_service)
    device = scale_service.create_device(
        name="Báscula Simulador", kind="simulator", min_stable_seconds=Decimal("0.05"),
    )
    scale_service.set_simulator_target_weight(device.id, Decimal("2.350"))

    product = _create_weight_product(sales_env)
    sales_env.inventory_service.register_entry(
        product_id=product.id,
        warehouse_id=sales_env.warehouse_id,
        quantity=Decimal("50.000"),
        reason="Stock inicial carne",
        created_by_user_id=None,
    )

    # Nunca se le pide al cajero escribir el peso: viene de la báscula.
    weight = _read_stable_weight_from_simulator(scale_service, read_service, device.id)
    assert weight == Decimal("2.350")

    preview = sales_env.sales_service.preview_sale(
        [SaleItemInput(product_id=product.id, quantity=weight)]
    )
    expected_subtotal = Decimal("2.350") * Decimal("20000")
    assert preview.subtotal == expected_subtotal
    assert preview.items[0].sale_unit is SaleUnit.WEIGHT
    assert preview.items[0].unit_of_measure == "kg"

    sale = sales_env.sales_service.complete_sale(
        items=[
            SaleItemInput(
                product_id=product.id,
                quantity=weight,
                weight_entry_source=WeightEntrySource.SCALE,
            )
        ],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=preview.total)],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    assert sale.items[0].quantity == Decimal("2.350")
    assert sale.items[0].sale_unit is SaleUnit.WEIGHT
    assert sale.items[0].unit_of_measure == "kg"
    assert sale.items[0].weight_entry_source is WeightEntrySource.SCALE
    assert sale.total == expected_subtotal

    remaining = sales_env.inventory_service.get_available_quantity(
        product.id, sales_env.warehouse_id
    )
    # Descuento exacto: 50.000 - 2.350 = 47.650, nunca redondeado.
    assert remaining == Decimal("47.650")


def test_sale_rejects_weight_below_product_minimum(sales_env: SalesFixtures) -> None:
    product = _create_weight_product(sales_env, min_weight=Decimal("0.500"))
    sales_env.inventory_service.register_entry(
        product_id=product.id,
        warehouse_id=sales_env.warehouse_id,
        quantity=Decimal("10.000"),
        reason="Stock",
        created_by_user_id=None,
    )

    with pytest.raises(BusinessRuleViolationError, match="mínimo"):
        sales_env.sales_service.complete_sale(
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("0.100"))],
            payments=[
                SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("2000"))
            ],
            cash_session_id=sales_env.cash_session_id,
            warehouse_id=sales_env.warehouse_id,
            created_by_user_id=sales_env.user_id,
        )


def test_sale_rejects_weight_above_product_maximum(sales_env: SalesFixtures) -> None:
    product = _create_weight_product(sales_env, max_weight=Decimal("5.000"))
    sales_env.inventory_service.register_entry(
        product_id=product.id,
        warehouse_id=sales_env.warehouse_id,
        quantity=Decimal("50.000"),
        reason="Stock",
        created_by_user_id=None,
    )

    with pytest.raises(BusinessRuleViolationError, match="máximo"):
        sales_env.sales_service.complete_sale(
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("8.000"))],
            payments=[
                SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("160000"))
            ],
            cash_session_id=sales_env.cash_session_id,
            warehouse_id=sales_env.warehouse_id,
            created_by_user_id=sales_env.user_id,
        )


def test_unit_sale_product_snapshot_is_unit(sales_env: SalesFixtures) -> None:
    """Un producto normal (por unidad) sigue guardando el snapshot
    correcto — no todo se vuelve "peso" por accidente."""
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("3"))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("3000"))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    assert sale.items[0].sale_unit is SaleUnit.UNIT
    assert sale.items[0].weight_entry_source is None


def test_weight_sale_with_manual_entry_source_persists_it(sales_env: SalesFixtures) -> None:
    """Sin báscula conectada, `ScaleWeightDialog` cae a peso manual (ver
    `scale_weight_dialog.py`) — el origen manual debe quedar guardado en el
    ítem igual que el automático, para trazabilidad en Historial."""
    product = _create_weight_product(sales_env)
    sales_env.inventory_service.register_entry(
        product_id=product.id,
        warehouse_id=sales_env.warehouse_id,
        quantity=Decimal("10.000"),
        reason="Stock inicial",
        created_by_user_id=None,
    )

    sale = sales_env.sales_service.complete_sale(
        items=[
            SaleItemInput(
                product_id=product.id,
                quantity=Decimal("1.500"),
                weight_entry_source=WeightEntrySource.MANUAL,
            )
        ],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("30000"))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    assert sale.items[0].weight_entry_source is WeightEntrySource.MANUAL
