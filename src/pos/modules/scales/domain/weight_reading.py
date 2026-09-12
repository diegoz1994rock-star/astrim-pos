"""Lógica pura de dominio para pesaje: conversión de unidades, clasificación
de una lectura y detección de estabilidad — funciones sin estado (o con
estado explícito y aislado, en el caso de `StabilityTracker`) usadas tanto
por una lectura real como por el adaptador simulador: un peso simulado pasa
por exactamente el mismo camino que uno real (mismo principio que
`scan_parsing.normalize_scan` en barcode_scanners)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from pos.modules.scales.domain.enums import UnitOfMeasure, WeightReadingStatus

# Factores exactos de conversión a gramos (base), como `Decimal` — nunca
# `float`, para no acumular error en pesos con hasta 3-4 decimales.
_GRAMS_PER_UNIT: dict[UnitOfMeasure, Decimal] = {
    UnitOfMeasure.G: Decimal("1"),
    UnitOfMeasure.KG: Decimal("1000"),
    UnitOfMeasure.LB: Decimal("453.59237"),
    UnitOfMeasure.OZ: Decimal("28.349523125"),
}


def convert_weight(
    value: Decimal, from_unit: UnitOfMeasure, to_unit: UnitOfMeasure
) -> Decimal:
    """Convierte un peso entre kg/g/lb/oz con precisión exacta en `Decimal`."""
    if from_unit is to_unit:
        return value
    grams = value * _GRAMS_PER_UNIT[from_unit]
    return grams / _GRAMS_PER_UNIT[to_unit]


def classify_reading(
    gross: Decimal,
    *,
    min_weight: Decimal | None = None,
    max_weight: Decimal | None = None,
) -> WeightReadingStatus | None:
    """Clasifica el contenido de una lectura ya convertida a la unidad de
    trabajo. Devuelve `None` cuando el peso es plausible y la clasificación
    final depende de la estabilidad (ver `StabilityTracker`), o el estado
    correspondiente cuando hay una anomalía de contenido (negativo/cero/
    fuera del rango del producto) que no tiene sentido evaluar por
    estabilidad."""
    if gross < 0:
        return WeightReadingStatus.NEGATIVE
    if gross == 0:
        return WeightReadingStatus.ZERO
    if min_weight is not None and gross < min_weight:
        return WeightReadingStatus.OUT_OF_RANGE
    if max_weight is not None and gross > max_weight:
        return WeightReadingStatus.OUT_OF_RANGE
    return None


@dataclass
class StabilityTracker:
    """Determina si el peso se mantuvo dentro de `tolerance` durante al
    menos `min_stable_seconds` continuos. Vive en memoria por dispositivo
    (ver `ScaleReadService`), igual patrón que el diccionario de debounce de
    `BarcodeReadService` — no se persiste, se reinicia con cada sesión de
    pesaje."""

    tolerance: Decimal
    min_stable_seconds: Decimal
    _stable_since: datetime | None = field(default=None, repr=False)
    _last_value: Decimal | None = field(default=None, repr=False)

    def reset(self) -> None:
        self._stable_since = None
        self._last_value = None

    def push(self, value: Decimal, *, now: datetime | None = None) -> bool:
        """Registra una nueva lectura y devuelve si el peso está estable
        en este momento."""
        now = now or datetime.now(UTC)
        if self._last_value is None or abs(value - self._last_value) > self.tolerance:
            self._stable_since = now
        self._last_value = value
        if self._stable_since is None:
            return False
        elapsed = Decimal(str((now - self._stable_since).total_seconds()))
        return elapsed >= self.min_stable_seconds
