"""DTO del módulo de configuración de factura (fila única de configuración)."""

from __future__ import annotations

from dataclasses import dataclass, field

from pos.modules.invoice_settings.application.content_items import CONTENT_KEYS
from pos.modules.invoice_settings.domain.enums import Orientation, PaperSize
from pos.modules.invoice_settings.domain.template_style import TemplateConfig


@dataclass(frozen=True)
class InvoiceSettingsDTO:
    company_name: str = "Mi Negocio"
    company_nit: str | None = None
    company_address: str | None = None
    company_city: str | None = None
    company_phone: str | None = None
    company_email: str | None = None
    company_website: str | None = None
    logo_path: str | None = None
    paper_size: PaperSize = PaperSize.LETTER
    custom_width_mm: float | None = None
    custom_height_mm: float | None = None
    """Solo se usan cuando `paper_size is PaperSize.CUSTOM` — ancho/alto en
    mm definidos a mano por el usuario o tomados de un tamaño reportado por
    el driver de una impresora instalada."""
    orientation: Orientation = Orientation.PORTRAIT
    margin_top_mm: float = 8.0
    margin_right_mm: float = 8.0
    margin_bottom_mm: float = 8.0
    margin_left_mm: float = 8.0
    base_font_size_pt: int = 10
    printer_name: str | None = None
    show_logo: bool = False
    show_customer: bool = True
    show_cashier: bool = True
    show_register: bool = True
    show_date: bool = True
    show_time: bool = True
    show_discounts: bool = True
    show_taxes: bool = True
    show_total: bool = True
    show_qr: bool = False
    show_barcode: bool = False
    show_closing_message: bool = False
    show_social_media: bool = False
    show_return_policy: bool = False
    content_order: list[str] = field(default_factory=lambda: list(CONTENT_KEYS))
    closing_message: str | None = None
    social_media: str | None = None
    return_policy: str | None = None
    template: TemplateConfig = field(default_factory=TemplateConfig)
    """Overrides visuales del editor de plantillas (fuente/color/alineación
    por elemento, estilo de tablas, tamaño/alineación de imágenes). Vacío
    por defecto — sin esto, `build_layout_plan` rinde exactamente igual
    que antes de que existiera el editor visual (ver `domain/layout_plan.py`
    y `application/template_style_codec.py`)."""
