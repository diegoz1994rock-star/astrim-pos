"""Formato de valores monetarios y de fecha/hora, consistente en toda la app.

Convención local (peso colombiano): "." como separador de miles, "," como
separador decimal — y los decimales solo se muestran si el valor tiene
centavos reales, para no ensuciar cifras redondas con ",00"."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal


def format_datetime_local(value: datetime, fmt: str) -> str:
    """Único punto de conversión UTC → hora local para mostrar en pantalla.

    Toda columna `UTCDateTime` se guarda y se lee siempre en UTC (ver
    `core/database/types.py::UTCDateTime`) — formatearla directamente sin
    convertir primero muestra la hora equivocada (bug real: un abono hecho
    a las 10:09 AM hora local aparecía como "15:09"). `.astimezone()` sin
    argumento convierte al huso horario del sistema operativo. Ventas
    (`sales_history_view.py`) e Historial de abonos
    (`customer_history_dialog.py`) llaman esta misma función — así nunca
    pueden divergir en cómo muestran fecha/hora."""
    return value.astimezone().strftime(fmt)


def format_currency(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.01"))
    sign = "-" if quantized < 0 else ""
    quantized = abs(quantized)

    integer_part = int(quantized)
    cents = int((quantized - integer_part) * 100)

    integer_text = f"{integer_part:,}".replace(",", ".")
    if cents:
        return f"{sign}{integer_text},{cents:02d}"
    return f"{sign}{integer_text}"


def format_file_size(size_bytes: int) -> str:
    """Tamaño de archivo legible (KB/MB/GB), usado en la pantalla de
    Backups. Base 1024, con un decimal salvo en bytes."""
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
