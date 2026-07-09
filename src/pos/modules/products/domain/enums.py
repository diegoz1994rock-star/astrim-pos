"""Enumeraciones de dominio del módulo de productos."""

from __future__ import annotations

import enum


class ProductType(enum.Enum):
    """Tipo de producto, según PROJECT_SPEC.md (inventario profesional)."""

    SIMPLE = "simple"
    """Producto simple: se vende y se descuenta de inventario tal cual."""
    COMPOUND = "compound"
    """Producto compuesto: tiene una receta de insumos (ver `RecipeItem`)."""
    COMBO = "combo"
    """Combo: agrupa otros productos vendidos como una sola línea (ver `ComboItem`)."""
