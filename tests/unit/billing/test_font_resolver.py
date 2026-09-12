"""Pruebas puras de `resolve_reportlab_font` — nunca debe lanzar, sin
importar qué fuente se pida; una fuente no instalada en esta máquina cae
en Helvetica."""

from __future__ import annotations

from pos.modules.billing.infrastructure.font_resolver import resolve_reportlab_font


def test_none_family_resolves_to_helvetica() -> None:
    assert resolve_reportlab_font(None) == "Helvetica"


def test_arial_alias_resolves_to_helvetica() -> None:
    assert resolve_reportlab_font("Arial") == "Helvetica"
    assert resolve_reportlab_font("arial") == "Helvetica"


def test_times_new_roman_alias_resolves_to_times_roman() -> None:
    assert resolve_reportlab_font("Times New Roman") == "Times-Roman"


def test_courier_new_alias_resolves_to_courier() -> None:
    assert resolve_reportlab_font("Courier New") == "Courier"


def test_safe_alias_bold_variant() -> None:
    assert resolve_reportlab_font("Arial", bold=True) == "Helvetica-Bold"
    assert resolve_reportlab_font("Times New Roman", bold=True) == "Times-Bold"


def test_safe_alias_italic_variant() -> None:
    assert resolve_reportlab_font("Arial", italic=True) == "Helvetica-Oblique"


def test_safe_alias_bold_italic_variant() -> None:
    assert resolve_reportlab_font("Arial", bold=True, italic=True) == "Helvetica-BoldOblique"


def test_unknown_font_family_falls_back_to_helvetica_without_raising() -> None:
    result = resolve_reportlab_font("Definitely Not A Real Font XYZ 12345")

    assert result == "Helvetica"


def test_unknown_font_family_bold_falls_back_to_helvetica_bold() -> None:
    result = resolve_reportlab_font("Definitely Not A Real Font XYZ 12345", bold=True)

    assert result == "Helvetica-Bold"
