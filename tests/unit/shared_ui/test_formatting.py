"""Pruebas de `format_currency` (separador de miles ".", separador decimal
"," solo cuando hay centavos reales) y `format_datetime_local` (conversión
UTC → hora local antes de formatear — corrige el bug real de hora
reportado en Ventas/Historial de abonos)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from pos.shared_ui.formatting import format_currency, format_datetime_local


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("20000.00"), "20.000"),
        (Decimal("22000.00"), "22.000"),
        (Decimal("22000.50"), "22.000,50"),
        (Decimal("1250000.00"), "1.250.000"),
        (Decimal("0.00"), "0"),
        (Decimal("999.99"), "999,99"),
        (Decimal("-500.00"), "-500"),
        (Decimal("45000.00"), "45.000"),
        (Decimal("100"), "100"),
        (Decimal("100.1"), "100,10"),
    ],
)
def test_format_currency(value: Decimal, expected: str) -> None:
    assert format_currency(value) == expected


def test_format_datetime_local_is_consistent_regardless_of_source_offset() -> None:
    """El mismo instante absoluto, representado con dos `tzinfo` distintos
    de origen (UTC vs. UTC-5), debe formatearse EXACTAMENTE igual — prueba
    que la función convierte de verdad al huso horario local del sistema
    en vez de simplemente reusar los números de reloj del valor de
    entrada (que es justo el bug real: mostrar la hora UTC cruda sin
    convertir, ej. "15:09" en vez de "10:09")."""
    utc_value = datetime(2026, 1, 1, 15, 9, tzinfo=UTC)
    bogota_equivalent = utc_value.astimezone(timezone(timedelta(hours=-5)))

    assert bogota_equivalent.hour == 10  # mismo instante, otra representación de reloj
    assert format_datetime_local(utc_value, "%H:%M") == format_datetime_local(
        bogota_equivalent, "%H:%M"
    )


def test_format_datetime_local_does_not_echo_raw_utc_wall_clock() -> None:
    """Si el sistema de pruebas no está en UTC, formatear en local NUNCA
    debe coincidir con simplemente `strftime` sobre el valor UTC crudo —
    exactamente el patrón que causaba el bug."""
    utc_value = datetime(2026, 1, 1, 15, 9, tzinfo=UTC)
    raw_utc_text = utc_value.strftime("%H:%M")
    local_text = format_datetime_local(utc_value, "%H:%M")

    if datetime.now().astimezone().utcoffset() != timedelta(0):
        assert local_text != raw_utc_text
