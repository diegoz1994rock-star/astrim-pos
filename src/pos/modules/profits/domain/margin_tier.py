"""Clasificación de margen para los indicadores de color de la tabla
(verde = alta utilidad, amarillo = utilidad media, rojo = poca utilidad,
gris = sin movimiento). Umbrales nombrados y ajustables en un único lugar."""

from __future__ import annotations

from decimal import Decimal

from pos.modules.profits.domain.enums import MarginTier

HIGH_MARGIN_THRESHOLD_PCT = Decimal("30")
MEDIUM_MARGIN_THRESHOLD_PCT = Decimal("10")


def classify_margin(margin_pct: Decimal | None) -> MarginTier:
    """`None` representa "sin movimiento" o "N/D" (costo histórico no
    disponible) — en ambos casos se muestra como gris, nunca se aproxima."""
    if margin_pct is None:
        return MarginTier.NONE
    if margin_pct >= HIGH_MARGIN_THRESHOLD_PCT:
        return MarginTier.HIGH
    if margin_pct >= MEDIUM_MARGIN_THRESHOLD_PCT:
        return MarginTier.MEDIUM
    return MarginTier.LOW
