"""Acceso a datos de solo lectura para los reportes.

Consulta directamente los modelos de `sales`, `cash_register` y `customers`
— dependencia intencional y documentada en MODULES.md (Reportes depende de
Ventas, Inventario, Caja, Clientes, Usuarios), no una violación de
ARCHITECTURE.md §12b (esa convención es sobre columnas `ForeignKey`, no
sobre consultas de aplicación entre módulos con dependencia reconocida).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos.modules.cash_register.infrastructure.models import CashRegister, CashSession
from pos.modules.customers.infrastructure.models import Customer
from pos.modules.products.infrastructure.models import Product
from pos.modules.sales.domain.enums import SaleStatus
from pos.modules.sales.infrastructure.models import Sale, SaleItem

_NO_REGISTER_LABEL = "—"


def _day_bounds(day_from: date, day_to: date) -> tuple[datetime, datetime]:
    """Igual que `today_utc_bounds` (`core/database/base.py`) pero para un
    rango de días calendario arbitrario elegido en la UI: ancla cada día a
    medianoche **local**, no UTC, antes de convertir — de lo contrario, en
    UTC-5, un reporte de "hoy" excluye las últimas 5 horas de ventas reales
    de hoy e incluye las últimas 5 horas de ayer."""
    local_tz = datetime.now().astimezone().tzinfo
    start = datetime.combine(day_from, time.min, tzinfo=local_tz).astimezone(UTC)
    end = datetime.combine(day_to, time.max, tzinfo=local_tz).astimezone(UTC)
    return start, end


class ReportRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_sales_in_range(self, date_from: date, date_to: date) -> list[tuple[Sale, str, str]]:
        """(venta, nombre del cliente, nombre de la caja) — la caja se
        resuelve `Sale.cash_session_id -&gt; CashSession.cash_register_id ->
        CashRegister.name`, mismo camino de joins que `list_cash_sessions_in_range`."""
        start, end = _day_bounds(date_from, date_to)
        rows = self._session.execute(
            select(Sale, Customer.full_name, CashRegister.name)
            .outerjoin(Customer, Customer.id == Sale.customer_id)
            .outerjoin(CashSession, CashSession.id == Sale.cash_session_id)
            .outerjoin(CashRegister, CashRegister.id == CashSession.cash_register_id)
            .where(Sale.created_at >= start, Sale.created_at <= end)
            .order_by(Sale.created_at)
        )
        return [
            (row[0], row[1] or "(sin cliente)", row[2] or _NO_REGISTER_LABEL) for row in rows
        ]

    def list_cash_sessions_in_range(
        self, date_from: date, date_to: date
    ) -> list[tuple[CashSession, str]]:
        start, end = _day_bounds(date_from, date_to)
        rows = self._session.execute(
            select(CashSession, CashRegister.name)
            .join(CashRegister, CashRegister.id == CashSession.cash_register_id)
            .where(CashSession.opened_at >= start, CashSession.opened_at <= end)
            .order_by(CashSession.opened_at)
        )
        return [(row[0], row[1]) for row in rows]

    def product_sales_in_range(
        self, date_from: date, date_to: date
    ) -> list[tuple[str, str, Decimal, Decimal]]:
        """(sku, nombre, cantidad_vendida, ingreso) por producto, solo ventas
        completadas (excluye anuladas)."""
        start, end = _day_bounds(date_from, date_to)
        rows = self._session.execute(
            select(
                Product.sku,
                Product.name,
                func.sum(SaleItem.quantity),
                func.sum(SaleItem.line_total),
            )
            .join(SaleItem, SaleItem.product_id == Product.id)
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
            .group_by(Product.id)
            .order_by(func.sum(SaleItem.line_total).desc())
        )
        return [(row[0], row[1], row[2], row[3]) for row in rows]

    def product_profit_in_range(self, date_from: date, date_to: date) -> Decimal:
        """Ganancia = Σ cantidad_vendida × (precio_de_venta_de_esa_línea −
        costo_actual_del_catálogo), solo ventas completadas — alimenta las
        tarjetas "Ganancias del día"/"Ganancias del mes" del Dashboard. El
        costo sale del catálogo (no se guarda histórico por línea), el
        precio es el realmente cobrado en cada venta (`SaleItem.unit_price`)."""
        start, end = _day_bounds(date_from, date_to)
        result = self._session.execute(
            select(func.sum(SaleItem.quantity * (SaleItem.unit_price - Product.cost_price)))
            .join(Product, Product.id == SaleItem.product_id)
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
        ).scalar()
        return result if result is not None else Decimal(0)

    def sale_totals_rows(self, date_from: date, date_to: date) -> list[tuple[datetime, Decimal]]:
        """(fecha de la venta, total) crudo para el rango — base de las
        gráficas de ventas por día/mes; el agrupamiento se hace en Python
        (`ReportsService`) para no depender de una función de fecha
        específica de un motor de base de datos (SQLite/Postgres/MySQL)."""
        start, end = _day_bounds(date_from, date_to)
        rows = self._session.execute(
            select(Sale.created_at, Sale.total).where(
                Sale.created_at >= start, Sale.created_at <= end
            )
        )
        return [(row[0], row[1]) for row in rows]

    def sale_item_profit_rows(
        self, date_from: date, date_to: date
    ) -> list[tuple[datetime, Decimal]]:
        """(fecha de la venta, ganancia de esa línea) crudo, solo ventas
        completadas — base de las gráficas de ganancias por día/mes, mismo
        criterio que `product_profit_in_range` pero sin colapsar el total."""
        start, end = _day_bounds(date_from, date_to)
        rows = self._session.execute(
            select(
                Sale.created_at, SaleItem.quantity * (SaleItem.unit_price - Product.cost_price)
            )
            .join(Product, Product.id == SaleItem.product_id)
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
        )
        return [(row[0], row[1]) for row in rows]
