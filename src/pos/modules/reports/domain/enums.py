"""Enumeraciones de dominio del módulo de reportes."""

from __future__ import annotations

import enum


class ReportFormat(enum.Enum):
    """Formato de exportación (PROJECT_SPEC.md, "REPORTES": todos exportables
    a PDF y Excel)."""

    PDF = "pdf"
    EXCEL = "excel"
