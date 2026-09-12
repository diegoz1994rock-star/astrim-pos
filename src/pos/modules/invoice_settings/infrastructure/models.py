"""Modelo SQLAlchemy de configuración de factura — fila única (id=1),
mismo patrón de "una sola fila de configuración" que otras tablas de
ajustes del sistema."""

from __future__ import annotations

from sqlalchemy import Boolean, Enum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import Base, TimestampMixin
from pos.modules.invoice_settings.application.content_items import CONTENT_KEYS
from pos.modules.invoice_settings.domain.enums import Orientation, PaperSize

_DEFAULT_CONTENT_ORDER = ",".join(CONTENT_KEYS)


class InvoiceSettings(Base, TimestampMixin):
    __tablename__ = "invoice_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_name: Mapped[str] = mapped_column(String(150), default="Mi Negocio", nullable=False)
    company_nit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    company_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    company_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    company_email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    company_website: Mapped[str | None] = mapped_column(String(200), nullable=True)
    logo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    paper_size: Mapped[PaperSize] = mapped_column(
        Enum(PaperSize, native_enum=False), default=PaperSize.LETTER, nullable=False
    )
    custom_width_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    custom_height_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    orientation: Mapped[Orientation] = mapped_column(
        Enum(Orientation, native_enum=False), default=Orientation.PORTRAIT, nullable=False
    )
    margin_top_mm: Mapped[float] = mapped_column(Float, default=8.0, nullable=False)
    margin_right_mm: Mapped[float] = mapped_column(Float, default=8.0, nullable=False)
    margin_bottom_mm: Mapped[float] = mapped_column(Float, default=8.0, nullable=False)
    margin_left_mm: Mapped[float] = mapped_column(Float, default=8.0, nullable=False)
    base_font_size_pt: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    printer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    show_logo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    show_customer: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_cashier: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_register: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_date: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_time: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_discounts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_taxes: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_total: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_qr: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    show_barcode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    show_closing_message: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    show_social_media: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    show_return_policy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content_order: Mapped[str] = mapped_column(
        String(500), default=_DEFAULT_CONTENT_ORDER, nullable=False
    )
    """Claves de `content_items.CONTENT_KEYS` separadas por coma, en el
    orden de impresión elegido en Administración → Configuración de factura."""
    closing_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    social_media: Mapped[str | None] = mapped_column(Text, nullable=True)
    return_policy: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Overrides visuales del editor de plantillas (JSON, ver
    `application/template_style_codec.py`) — `NULL` significa "sin
    personalización", renderiza igual que antes del editor visual."""
