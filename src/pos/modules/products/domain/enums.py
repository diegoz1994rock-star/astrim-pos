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


class SaleUnit(enum.Enum):
    """Cómo se vende un producto — reemplaza la heurística de texto sobre
    `unit_of_measure` que existía antes (ver `sale_view.py`, ya eliminada):
    ahora es un campo explícito y obligatorio, no una adivinanza."""

    UNIT = "unit"
    """Por unidad: cantidad × precio, como martillo, varilla, taladro."""
    WEIGHT = "weight"
    """Por peso: se pesa en báscula (o se ingresa manualmente) y se cobra
    peso × precio por kilogramo, como papa, cebolla, carne."""
