"""Enumeraciones de dominio del módulo de Ganancias."""

from __future__ import annotations

import enum


class DateRangePreset(enum.Enum):
    """Una por cada pestaña superior del módulo. Cada valor únicamente
    determina qué rango de fechas resuelve `resolve_range()` — toda la
    lógica de consulta/cálculo posterior es exactamente la misma para las
    6 pestañas."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"


class ProfitSortOption(enum.Enum):
    """Las 8 opciones de ordenamiento pedidas para el selector "Ordenar por",
    más `FIRST_SALE_ASC` (orden por defecto): la tabla debe verse
    cronológicamente ordenada (primera venta más antigua primero) antes de
    que el usuario elija otro criterio, para que el análisis por período
    tenga sentido de lectura."""

    FIRST_SALE_ASC = "first_sale_asc"
    MOST_SOLD = "most_sold"
    LEAST_SOLD = "least_sold"
    HIGHEST_PROFIT = "highest_profit"
    LOWEST_PROFIT = "lowest_profit"
    HIGHEST_REVENUE = "highest_revenue"
    HIGHEST_QUANTITY = "highest_quantity"
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"


class MarginTier(enum.Enum):
    """Clasificación de un producto según su margen, para los indicadores
    de color de la tabla (verde/amarillo/rojo/gris)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"
