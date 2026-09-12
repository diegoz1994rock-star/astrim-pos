"""Acceso a datos de configuración de factura — siempre una sola fila (id=1)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from pos.modules.invoice_settings.application.dto import InvoiceSettingsDTO
from pos.modules.invoice_settings.infrastructure.models import InvoiceSettings

_SINGLETON_ID = 1


class InvoiceSettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create(self) -> InvoiceSettings:
        settings = self._session.get(InvoiceSettings, _SINGLETON_ID)
        if settings is None:
            settings = InvoiceSettings(id=_SINGLETON_ID)
            self._session.add(settings)
            self._session.flush()
        return settings

    def update_from_dto(
        self, settings: InvoiceSettings, dto: InvoiceSettingsDTO, template_config_json: str
    ) -> None:
        settings.company_name = dto.company_name
        settings.company_nit = dto.company_nit
        settings.company_address = dto.company_address
        settings.company_city = dto.company_city
        settings.company_phone = dto.company_phone
        settings.company_email = dto.company_email
        settings.company_website = dto.company_website
        settings.logo_path = dto.logo_path
        settings.paper_size = dto.paper_size
        settings.custom_width_mm = dto.custom_width_mm
        settings.custom_height_mm = dto.custom_height_mm
        settings.orientation = dto.orientation
        settings.margin_top_mm = dto.margin_top_mm
        settings.margin_right_mm = dto.margin_right_mm
        settings.margin_bottom_mm = dto.margin_bottom_mm
        settings.margin_left_mm = dto.margin_left_mm
        settings.base_font_size_pt = dto.base_font_size_pt
        settings.printer_name = dto.printer_name
        settings.show_logo = dto.show_logo
        settings.show_customer = dto.show_customer
        settings.show_cashier = dto.show_cashier
        settings.show_register = dto.show_register
        settings.show_date = dto.show_date
        settings.show_time = dto.show_time
        settings.show_discounts = dto.show_discounts
        settings.show_taxes = dto.show_taxes
        settings.show_total = dto.show_total
        settings.show_qr = dto.show_qr
        settings.show_barcode = dto.show_barcode
        settings.show_closing_message = dto.show_closing_message
        settings.show_social_media = dto.show_social_media
        settings.show_return_policy = dto.show_return_policy
        settings.content_order = ",".join(dto.content_order)
        settings.closing_message = dto.closing_message
        settings.social_media = dto.social_media
        settings.return_policy = dto.return_policy
        settings.template_config_json = template_config_json
        self._session.flush()
