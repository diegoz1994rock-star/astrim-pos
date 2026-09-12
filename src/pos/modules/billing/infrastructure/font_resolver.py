"""Resolución de fuentes para el PDF (ReportLab) elegidas desde el editor
visual de plantillas de factura — nunca puede hacer fallar la generación
de un PDF: si la fuente pedida no está disponible en esta máquina, cae en
silencio a Helvetica (con una advertencia en el log), nunca lanza.

ReportLab trae embebidas, sin instalación adicional, las familias
Helvetica/Times-Roman/Courier (con sus variantes Bold/Oblique/BoldOblique)
— cualquier otra familia (p. ej. "Comic Sans MS") requiere encontrar un
archivo `.ttf/.ttc/.otf` real en el sistema operativo y registrarlo con
`pdfmetrics.registerFont`. Esa búsqueda depende de qué fuentes estén
instaladas en la máquina que genera el PDF, que no necesariamente es la
misma donde el administrador configuró la plantilla (por ejemplo, en una
tienda con el módulo de sincronización multi-estación) — por eso el
fallback silencioso a Helvetica es obligatorio, no opcional."""

from __future__ import annotations

import logging
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

_SAFE_ALIASES: dict[str, str] = {
    "helvetica": "Helvetica",
    "arial": "Helvetica",
    "sans-serif": "Helvetica",
    "times new roman": "Times-Roman",
    "times": "Times-Roman",
    "serif": "Times-Roman",
    "courier new": "Courier",
    "courier": "Courier",
    "monospace": "Courier",
}

_SAFE_BOLD_VARIANTS: dict[str, str] = {
    "Helvetica": "Helvetica-Bold",
    "Times-Roman": "Times-Bold",
    "Courier": "Courier-Bold",
}
_SAFE_ITALIC_VARIANTS: dict[str, str] = {
    "Helvetica": "Helvetica-Oblique",
    "Times-Roman": "Times-Italic",
    "Courier": "Courier-Oblique",
}
_SAFE_BOLD_ITALIC_VARIANTS: dict[str, str] = {
    "Helvetica": "Helvetica-BoldOblique",
    "Times-Roman": "Times-BoldItalic",
    "Courier": "Courier-BoldOblique",
}

_FONT_DIRECTORIES = [
    # macOS
    Path("/System/Library/Fonts"),
    Path("/System/Library/Fonts/Supplemental"),
    Path("/Library/Fonts"),
    Path.home() / "Library/Fonts",
    # Linux
    Path("/usr/share/fonts"),
    Path("/usr/local/share/fonts"),
    Path.home() / ".fonts",
    Path.home() / ".local/share/fonts",
    # Windows
    Path("C:/Windows/Fonts"),
]
_FONT_EXTENSIONS = (".ttf", ".ttc", ".otf")

_DEFAULT_FALLBACK = "Helvetica"

_registered_fonts: dict[str, str] = {}
_search_failed: set[str] = set()


def _find_font_file(family: str) -> Path | None:
    normalized = family.strip().lower().replace(" ", "")
    for directory in _FONT_DIRECTORIES:
        if not directory.is_dir():
            continue
        try:
            candidates = directory.rglob("*")
        except OSError:
            continue
        for candidate in candidates:
            if candidate.suffix.lower() not in _FONT_EXTENSIONS:
                continue
            candidate_name = candidate.stem.lower().replace(" ", "").replace("-", "")
            if normalized in candidate_name or candidate_name in normalized:
                return candidate
    return None


def _register_family(family: str) -> str | None:
    """Intenta registrar `family` como una fuente TTF real; devuelve el
    nombre interno de ReportLab si lo logra, o `None` si no se encontró un
    archivo real en esta máquina. Nunca lanza — cualquier error de
    lectura/registro del archivo se trata como "no encontrado"."""
    if family in _registered_fonts:
        return _registered_fonts[family]
    if family in _search_failed:
        return None

    font_file = _find_font_file(family)
    if font_file is None:
        _search_failed.add(family)
        return None

    try:
        pdfmetrics.registerFont(TTFont(family, str(font_file)))
    except Exception:
        logger.warning("No fue posible registrar la fuente %r (%s)", family, font_file)
        _search_failed.add(family)
        return None

    _registered_fonts[family] = family
    return family


def resolve_reportlab_font(family: str | None, *, bold: bool = False, italic: bool = False) -> str:
    """Devuelve un nombre de fuente que ReportLab puede usar de inmediato.
    Nunca lanza — en el peor caso devuelve `Helvetica` (o su variante
    negrilla/cursiva)."""
    if not family:
        family = _DEFAULT_FALLBACK

    safe_base = _SAFE_ALIASES.get(family.strip().lower())
    if safe_base:
        if bold and italic:
            return _SAFE_BOLD_ITALIC_VARIANTS.get(safe_base, safe_base)
        if bold:
            return _SAFE_BOLD_VARIANTS.get(safe_base, safe_base)
        if italic:
            return _SAFE_ITALIC_VARIANTS.get(safe_base, safe_base)
        return safe_base

    registered = _register_family(family)
    if registered is not None:
        return registered

    logger.warning(
        "La fuente %r configurada en la plantilla de factura no está instalada en "
        "esta máquina; se usa Helvetica como reemplazo al generar el PDF.",
        family,
    )
    if bold and italic:
        return _SAFE_BOLD_ITALIC_VARIANTS[_DEFAULT_FALLBACK]
    if bold:
        return _SAFE_BOLD_VARIANTS[_DEFAULT_FALLBACK]
    if italic:
        return _SAFE_ITALIC_VARIANTS[_DEFAULT_FALLBACK]
    return _DEFAULT_FALLBACK
