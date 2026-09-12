"""Resolución de rango de fechas para cada pestaña de Ganancias.

Única fuente de verdad para las 6 pestañas (Diario/Semanal/Mensual/
Trimestral/Semestral/Anual, ver `DateRangePreset`) — cada pestaña de la
UI le pasa un preset distinto a esta misma función y reutiliza 100% del
resto de la lógica de consulta/cálculo, tal como pide el requerimiento
("no repetir código. Cambia únicamente el rango de consulta")."""

from __future__ import annotations

import calendar
from datetime import date

from pos.modules.profits.domain.enums import DateRangePreset


def _last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def resolve_range(preset: DateRangePreset, reference_date: date) -> tuple[date, date]:
    """Devuelve `(fecha_desde, fecha_hasta)` (ambas inclusive) para el
    período que contiene `reference_date` bajo el `preset` dado."""
    if preset is DateRangePreset.DAILY:
        return reference_date, reference_date

    if preset is DateRangePreset.WEEKLY:
        start = reference_date.fromordinal(reference_date.toordinal() - reference_date.weekday())
        end = start.fromordinal(start.toordinal() + 6)
        return start, end

    if preset is DateRangePreset.MONTHLY:
        last_day = _last_day_of_month(reference_date.year, reference_date.month)
        start = reference_date.replace(day=1)
        end = reference_date.replace(day=last_day)
        return start, end

    if preset is DateRangePreset.QUARTERLY:
        quarter_index = (reference_date.month - 1) // 3
        start_month = quarter_index * 3 + 1
        end_month = start_month + 2
        last_day = _last_day_of_month(reference_date.year, end_month)
        start = date(reference_date.year, start_month, 1)
        end = date(reference_date.year, end_month, last_day)
        return start, end

    if preset is DateRangePreset.SEMIANNUAL:
        if reference_date.month <= 6:
            return date(reference_date.year, 1, 1), date(reference_date.year, 6, 30)
        return date(reference_date.year, 7, 1), date(reference_date.year, 12, 31)

    if preset is DateRangePreset.ANNUAL:
        return date(reference_date.year, 1, 1), date(reference_date.year, 12, 31)

    raise ValueError(f"DateRangePreset no soportado: {preset}")
