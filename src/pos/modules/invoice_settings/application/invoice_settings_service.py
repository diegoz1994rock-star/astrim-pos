"""Caso de uso de configuración de factura — lectura/escritura de la fila
única de configuración que `billing.pdf_renderer` usa para armar el PDF."""

from __future__ import annotations

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.invoice_settings.application import template_style_codec
from pos.modules.invoice_settings.application.content_items import CONTENT_KEYS
from pos.modules.invoice_settings.application.dto import InvoiceSettingsDTO
from pos.modules.invoice_settings.domain.enums import PaperSize
from pos.modules.invoice_settings.infrastructure.models import InvoiceSettings
from pos.modules.invoice_settings.infrastructure.repository import InvoiceSettingsRepository


def _normalize_content_order(raw: str | None) -> list[str]:
    """Convierte lo persistido en una permutación válida de `CONTENT_KEYS`
    siempre — nunca puede quedar mal formado a la salida, sin importar qué
    quedó guardado (incluyendo un `content_order` de una versión anterior
    con claves que ya no existen en `CONTENT_KEYS`, como `company`/
    `items_table`/`subtotal`/`discount`/`tax`/`total`, que pasaron a tener
    posición fija en vez de ser reordenables — ver `content_items.py`): se
    descartan las claves que ya no existen y se agregan al final las que
    falten (por ejemplo si `CONTENT_KEYS` gana una clave nueva a futuro) —
    así el resultado es siempre exactamente `set(CONTENT_KEYS)`, y el
    próximo "Guardar" ya persiste el valor corregido.

    Causa raíz del bug histórico "El orden de contenido de la factura está
    incompleto o corrupto" al guardar sin haber tocado nada: `CONTENT_KEYS`
    cambiaba de tamaño en un release y la fila ya existente en la base de
    datos quedaba con un `content_order` de otro tamaño — nadie lo
    normalizaba al leerlo, así que se cargaba tal cual en el formulario y,
    al guardar sin cambios, `update_settings` comparaba ese conjunto viejo
    contra el `CONTENT_KEYS` vigente y siempre fallaba."""
    stored = raw.split(",") if raw else []
    known = set(CONTENT_KEYS)
    kept = list(dict.fromkeys(key for key in stored if key in known))
    missing = [key for key in CONTENT_KEYS if key not in kept]
    return kept + missing


def _to_dto(settings: InvoiceSettings) -> InvoiceSettingsDTO:
    order = _normalize_content_order(settings.content_order)
    return InvoiceSettingsDTO(
        company_name=settings.company_name,
        company_nit=settings.company_nit,
        company_address=settings.company_address,
        company_city=settings.company_city,
        company_phone=settings.company_phone,
        company_email=settings.company_email,
        company_website=settings.company_website,
        logo_path=settings.logo_path,
        paper_size=settings.paper_size,
        custom_width_mm=settings.custom_width_mm,
        custom_height_mm=settings.custom_height_mm,
        orientation=settings.orientation,
        margin_top_mm=settings.margin_top_mm,
        margin_right_mm=settings.margin_right_mm,
        margin_bottom_mm=settings.margin_bottom_mm,
        margin_left_mm=settings.margin_left_mm,
        base_font_size_pt=settings.base_font_size_pt,
        printer_name=settings.printer_name,
        show_logo=settings.show_logo,
        show_customer=settings.show_customer,
        show_cashier=settings.show_cashier,
        show_register=settings.show_register,
        show_date=settings.show_date,
        show_time=settings.show_time,
        show_discounts=settings.show_discounts,
        show_taxes=settings.show_taxes,
        show_total=settings.show_total,
        show_qr=settings.show_qr,
        show_barcode=settings.show_barcode,
        show_closing_message=settings.show_closing_message,
        show_social_media=settings.show_social_media,
        show_return_policy=settings.show_return_policy,
        content_order=order,
        closing_message=settings.closing_message,
        social_media=settings.social_media,
        return_policy=settings.return_policy,
        template=template_style_codec.decode_template(settings.template_config_json),
    )


class InvoiceSettingsService:
    def get_settings(self) -> InvoiceSettingsDTO:
        with session_scope() as session:
            return _to_dto(InvoiceSettingsRepository(session).get_or_create())

    def update_settings(self, settings: InvoiceSettingsDTO) -> InvoiceSettingsDTO:
        name = settings.company_name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre de la empresa es obligatorio.")
        if set(settings.content_order) != set(CONTENT_KEYS):
            raise BusinessRuleViolationError(
                "El orden de contenido de la factura está incompleto o corrupto."
            )
        settings = InvoiceSettingsDTO(**{**settings.__dict__, "company_name": name})
        template_config_json = template_style_codec.encode_template(settings.template)
        with session_scope() as session:
            repo = InvoiceSettingsRepository(session)
            record = repo.get_or_create()
            repo.update_from_dto(record, settings, template_config_json)
            return _to_dto(record)

    @staticmethod
    def paper_sizes() -> list[PaperSize]:
        return list(PaperSize)
