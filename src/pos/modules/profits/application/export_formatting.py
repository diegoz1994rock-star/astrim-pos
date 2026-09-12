"""Representación en texto de una fila de Ganancias — capa de aplicación,
sin dependencia de Qt, para que la reutilicen tanto el modelo de tabla de
`presentation/profits_table_model.py` como la exportación PDF/Excel de
`ProfitsService`, sin duplicar la lista de 19 columnas ni el orden de
valores en dos lugares."""

from __future__ import annotations

from decimal import Decimal

from pos.modules.products.domain.enums import SaleUnit
from pos.modules.profits.application.dto import ProductProfitRowDTO
from pos.shared_ui.formatting import format_currency

_NA = "N/D"

PRODUCT_ROW_COLUMNS = [
    "Código",
    "Categoría",
    "Producto",
    "Cantidad vendida",
    "Precio prom. compra",
    "Precio prom. venta",
    "Costo total",
    "Ingreso total",
    "Ganancia total",
    "Margen %",
    "N.º facturas",
    "Primera venta",
    "Última venta",
    "Stock actual",
    "Proveedor",
    "Usuario que más vendió",
    "Precio mínimo",
    "Precio máximo",
    "Utilidad/unidad",
]

MARGIN_COLUMN_INDEX = 9


def _money(value) -> str:  # noqa: ANN001
    return _NA if value is None else format_currency(value)


def format_quantity(value: Decimal, sale_unit: SaleUnit | None) -> str:
    """Formatea una cantidad física (nunca monetaria): `sale_unit` decide el
    formato, no un formateador único para todo. `SaleUnit.UNIT` siempre es
    entero (martillos, destornilladores, cajas — nunca tiene sentido un
    decimal). `SaleUnit.WEIGHT` (o `None`, cuando la cantidad agrega
    productos de unidades mixtas, ej. por categoría) conserva solo los
    decimales realmente presentes — nunca ceros de relleno del `Numeric`
    de la columna (`sale_items.quantity`/`stock_levels.quantity` son
    `Numeric(14, 3)`, por lo que un `Decimal` como `Decimal('61.000')` trae
    3 decimales aunque el valor real sea un entero)."""
    if sale_unit is SaleUnit.UNIT:
        return str(int(value))
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def product_row_to_strings(row: ProductProfitRowDTO) -> list[str]:
    return [
        row.code,
        row.category_name,
        row.product_name,
        format_quantity(row.quantity_sold, row.sale_unit),
        _money(row.avg_purchase_price),
        _money(row.avg_sale_price),
        _money(row.total_cost),
        _money(row.total_revenue),
        _money(row.total_profit),
        _NA if row.margin_pct is None else f"{row.margin_pct:g}%",
        str(row.invoice_count),
        row.first_sale_at.astimezone().strftime("%Y-%m-%d %H:%M"),
        row.last_sale_at.astimezone().strftime("%Y-%m-%d %H:%M"),
        format_quantity(row.current_stock, row.sale_unit),
        row.supplier_name,
        row.top_seller_name,
        _money(row.min_sale_price),
        _money(row.max_sale_price),
        _money(row.avg_profit_per_unit),
    ]
