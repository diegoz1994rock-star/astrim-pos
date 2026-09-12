"""Pruebas de integración de InvoiceSettingsService contra SQLite real:
la fila única se crea sola con valores por defecto, y guardar valida
nombre de empresa y orden de contenido completo."""

from __future__ import annotations

from dataclasses import replace

import pytest

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.invoice_settings.application.content_items import CONTENT_KEYS
from pos.modules.invoice_settings.application.invoice_settings_service import (
    InvoiceSettingsService,
)
from pos.modules.invoice_settings.domain.enums import Orientation, PaperSize
from pos.modules.invoice_settings.domain.template_style import ElementStyle, TemplateConfig
from pos.modules.invoice_settings.infrastructure.repository import InvoiceSettingsRepository


def test_get_settings_creates_default_row(sqlite_engine: None) -> None:
    service = InvoiceSettingsService()

    settings = service.get_settings()

    assert settings.company_name == "Mi Negocio"
    assert settings.paper_size is PaperSize.LETTER
    assert settings.content_order == list(CONTENT_KEYS)
    assert settings.show_total is True
    assert settings.show_logo is False
    assert settings.orientation is Orientation.PORTRAIT
    assert settings.margin_top_mm == 8.0
    assert settings.margin_right_mm == 8.0
    assert settings.margin_bottom_mm == 8.0
    assert settings.margin_left_mm == 8.0
    assert settings.base_font_size_pt == 10
    assert settings.custom_width_mm is None
    assert settings.custom_height_mm is None


def test_update_settings_persists_fields(sqlite_engine: None) -> None:
    service = InvoiceSettingsService()
    current = service.get_settings()

    updated = service.update_settings(
        replace(
            current,
            company_name="Ferretería El Tornillo",
            company_nit="900123456",
            paper_size=PaperSize.TICKET_80,
            show_logo=True,
            show_qr=True,
        )
    )

    assert updated.company_name == "Ferretería El Tornillo"
    assert updated.company_nit == "900123456"
    assert updated.paper_size is PaperSize.TICKET_80
    assert updated.show_logo is True
    assert updated.show_qr is True

    reloaded = service.get_settings()
    assert reloaded.company_name == "Ferretería El Tornillo"
    assert reloaded.paper_size is PaperSize.TICKET_80


def test_update_settings_persists_margins_orientation_font_and_custom_size(
    sqlite_engine: None,
) -> None:
    service = InvoiceSettingsService()
    current = service.get_settings()

    updated = service.update_settings(
        replace(
            current,
            paper_size=PaperSize.CUSTOM,
            custom_width_mm=100.0,
            custom_height_mm=150.0,
            orientation=Orientation.LANDSCAPE,
            margin_top_mm=5.0,
            margin_right_mm=6.0,
            margin_bottom_mm=7.0,
            margin_left_mm=9.0,
            base_font_size_pt=12,
        )
    )

    assert updated.paper_size is PaperSize.CUSTOM
    assert updated.custom_width_mm == 100.0
    assert updated.custom_height_mm == 150.0
    assert updated.orientation is Orientation.LANDSCAPE
    assert updated.margin_top_mm == 5.0
    assert updated.margin_right_mm == 6.0
    assert updated.margin_bottom_mm == 7.0
    assert updated.margin_left_mm == 9.0
    assert updated.base_font_size_pt == 12

    reloaded = service.get_settings()
    assert reloaded.custom_width_mm == 100.0
    assert reloaded.orientation is Orientation.LANDSCAPE
    assert reloaded.base_font_size_pt == 12


def test_update_settings_rejects_empty_company_name(sqlite_engine: None) -> None:
    service = InvoiceSettingsService()
    current = service.get_settings()

    with pytest.raises(BusinessRuleViolationError):
        service.update_settings(replace(current, company_name="   "))


def test_update_settings_rejects_incomplete_content_order(sqlite_engine: None) -> None:
    service = InvoiceSettingsService()
    current = service.get_settings()

    with pytest.raises(BusinessRuleViolationError):
        service.update_settings(replace(current, content_order=["logo", "qr"]))


def test_update_settings_persists_reordered_content(sqlite_engine: None) -> None:
    service = InvoiceSettingsService()
    current = service.get_settings()
    reordered = list(reversed(CONTENT_KEYS))

    updated = service.update_settings(replace(current, content_order=reordered))

    assert updated.content_order == reordered


def test_get_settings_defaults_to_empty_template(sqlite_engine: None) -> None:
    settings = InvoiceSettingsService().get_settings()

    assert settings.template == TemplateConfig()


def test_update_settings_persists_and_reloads_template_overrides(sqlite_engine: None) -> None:
    service = InvoiceSettingsService()
    current = service.get_settings()
    template = TemplateConfig(
        element_styles={
            "company_name": ElementStyle(
                font_family="Times New Roman", font_size_pt=18, color_hex="#123456", bold=True
            )
        },
        show_grid=True,
    )

    service.update_settings(replace(current, template=template))
    reloaded = service.get_settings()

    assert reloaded.template.show_grid is True
    assert reloaded.template.element_styles["company_name"].font_family == "Times New Roman"
    assert reloaded.template.element_styles["company_name"].font_size_pt == 18
    assert reloaded.template.element_styles["company_name"].color_hex == "#123456"
    assert reloaded.template.element_styles["company_name"].bold is True


def _seed_stale_content_order(raw_value: str) -> None:
    """Escribe `content_order` directamente en la fila, sin pasar por
    `InvoiceSettingsService` (que ya valida) — simula datos persistidos por
    una versión anterior del código, antes de que `CONTENT_KEYS` cambiara."""
    with session_scope() as session:
        record = InvoiceSettingsRepository(session).get_or_create()
        record.content_order = raw_value


def test_get_settings_normalizes_legacy_content_order_with_removed_keys(
    sqlite_engine: None,
) -> None:
    """Reproduce el bug real: `content_order` persistido con claves que ya
    no existen en `CONTENT_KEYS` debe normalizarse solo al leer, no
    explotar ni arrastrar las claves viejas. `company`/`items_table`/
    `subtotal`/`discount`/`tax`/`total` pasaron a tener posición fija (ya
    no son claves de `content_order`, ver `content_items.py`), así que
    cualquier fila guardada por una versión anterior con esas 6 claves (o
    con las variantes aún más antiguas `discounts`/`taxes`, plurales) debe
    perderlas al normalizar, sin que eso cuente como dato corrupto."""
    _seed_stale_content_order(
        "company,logo,customer,cashier,register,date,time,items_table,subtotal,"
        "discounts,taxes,discount,tax,total,"
        "qr,barcode,closing_message,social_media,return_policy"
    )
    service = InvoiceSettingsService()

    settings = service.get_settings()

    assert set(settings.content_order) == set(CONTENT_KEYS)
    for removed_key in ("company", "items_table", "subtotal", "discounts", "taxes",
                        "discount", "tax", "total"):
        assert removed_key not in settings.content_order
    # el orden relativo de las claves válidas se conserva
    assert settings.content_order.index("logo") < settings.content_order.index("customer")
    assert settings.content_order.index("qr") < settings.content_order.index("barcode")


def test_get_settings_normalizes_pre_template_editor_order_unchanged(
    sqlite_engine: None,
) -> None:
    """Filas guardadas antes del editor visual de plantillas nunca tuvieron
    `company`/`items_table`/`subtotal`/`discount`/`tax`/`total` en
    `content_order` (siempre se imprimieron en una posición fija, y lo
    siguen haciendo — ver `content_items.py`/`layout_plan.py`): a
    diferencia del bug histórico donde `CONTENT_KEYS` sí las incluyó por un
    tiempo (ver `test_get_settings_normalizes_legacy_content_order_with_
    removed_keys`), un `content_order` de esta forma ya coincide
    exactamente con `CONTENT_KEYS` vigente y no necesita ninguna
    reparación — se conserva tal cual, sin reordenar nada."""
    stored = (
        "logo,customer,cashier,register,date,time,"
        "qr,barcode,closing_message,social_media,return_policy"
    )
    _seed_stale_content_order(stored)
    service = InvoiceSettingsService()

    settings = service.get_settings()

    assert settings.content_order == stored.split(",")


def test_saving_after_loading_legacy_content_order_no_longer_raises(
    sqlite_engine: None,
) -> None:
    """El escenario exacto reportado: abrir la pantalla (que carga la fila
    vieja), no tocar nada, y Guardar — antes lanzaba "El orden de contenido
    de la factura está incompleto o corrupto"."""
    _seed_stale_content_order(
        "logo,customer,cashier,register,date,time,discounts,taxes,total,"
        "qr,barcode,closing_message,social_media,return_policy"
    )
    service = InvoiceSettingsService()
    loaded = service.get_settings()

    updated = service.update_settings(loaded)

    assert set(updated.content_order) == set(CONTENT_KEYS)

    reloaded = service.get_settings()
    assert set(reloaded.content_order) == set(CONTENT_KEYS)


def test_get_settings_appends_new_content_keys_missing_from_legacy_order(
    sqlite_engine: None,
) -> None:
    """Caso simétrico: si `CONTENT_KEYS` ganara una clave nueva a futuro,
    una fila vieja que no la tenga debe completarse, no fallar."""
    _seed_stale_content_order("logo,customer")

    settings = InvoiceSettingsService().get_settings()

    assert set(settings.content_order) == set(CONTENT_KEYS)
    assert settings.content_order[0] == "logo"
    assert settings.content_order[1] == "customer"
