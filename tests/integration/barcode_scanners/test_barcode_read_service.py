"""Pruebas de integración de `BarcodeReadService` contra SQLite real: el
módulo centralizado que usan Ventas, "Probar lector" y Diagnóstico —
resolver una lectura, filtrar rebote de doble lectura, respetar el
interruptor global, registrar cada evento y agregar diagnóstico."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pos.core.events.bus import EventBus
from pos.modules.barcode_scanners.application.barcode_read_service import BarcodeReadService
from pos.modules.barcode_scanners.application.dto import BarcodeSettingsDTO
from pos.modules.barcode_scanners.domain.enums import BarcodeReadSource
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.products.domain.enums import ProductType
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.modules.settings.infrastructure.models import SettingValueType


def _create_product_with_barcode(
    service: ProductManagementService, code: str, name: str = "Martillo"
):
    product = service.create_product(
        sku=f"SKU-{code}",
        name=name,
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("10.00"),
        cost_price=Decimal("5.00"),
        unit_of_measure="unidad",
        track_inventory=True,
    )
    service.add_barcode(product.id, code)
    return product


def _make_service() -> BarcodeReadService:
    return BarcodeReadService(
        BusinessSettingsService(EventBus()), ProductManagementService(EventBus())
    )


def test_resolve_scan_finds_an_existing_product(sqlite_engine: None) -> None:
    service = _make_service()
    product = _create_product_with_barcode(service._product_service, "7701234567890")

    result = service.resolve_scan("7701234567890", source=BarcodeReadSource.SALE)

    assert result.found
    assert result.product is not None
    assert result.product.id == product.id
    assert not result.ignored


def test_resolve_scan_reports_unknown_code(sqlite_engine: None) -> None:
    service = _make_service()

    result = service.resolve_scan("0000000000000", source=BarcodeReadSource.SALE)

    assert not result.found
    assert result.product is None
    assert not result.ignored


def test_resolve_scan_ignores_a_duplicate_read_within_the_debounce_window(
    sqlite_engine: None,
) -> None:
    service = _make_service()
    _create_product_with_barcode(service._product_service, "7701234567890")
    base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)

    first = service.resolve_scan(
        "7701234567890", source=BarcodeReadSource.SALE, now=base
    )
    second = service.resolve_scan(
        "7701234567890",
        source=BarcodeReadSource.SALE,
        now=base + timedelta(milliseconds=50),
    )

    assert not first.ignored
    assert second.ignored
    assert "duplicada" in (second.reason or "").lower()


def test_resolve_scan_processes_the_same_code_again_after_the_debounce_window(
    sqlite_engine: None,
) -> None:
    service = _make_service()
    _create_product_with_barcode(service._product_service, "7701234567890")
    base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)

    service.resolve_scan("7701234567890", source=BarcodeReadSource.SALE, now=base)
    later = service.resolve_scan(
        "7701234567890",
        source=BarcodeReadSource.SALE,
        now=base + timedelta(milliseconds=500),
    )

    assert not later.ignored
    assert later.found


def test_resolve_scan_does_not_debounce_two_different_codes(sqlite_engine: None) -> None:
    """Escaneos rápidos consecutivos de productos distintos (Coca-Cola,
    Coca-Cola, Arroz...) nunca deben perderse — el rebote solo aplica al
    MISMO código repetido."""
    service = _make_service()
    _create_product_with_barcode(service._product_service, "1111111111111", "Coca-Cola")
    _create_product_with_barcode(service._product_service, "2222222222222", "Arroz")
    base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)

    first = service.resolve_scan("1111111111111", source=BarcodeReadSource.SALE, now=base)
    second = service.resolve_scan(
        "2222222222222",
        source=BarcodeReadSource.SALE,
        now=base + timedelta(milliseconds=10),
    )

    assert not first.ignored
    assert not second.ignored


def test_resolve_scan_respects_a_custom_debounce_window(sqlite_engine: None) -> None:
    service = _make_service()
    _create_product_with_barcode(service._product_service, "7701234567890")
    service.save_settings(
        BarcodeSettingsDTO(
            reader_enabled=True, auto_enter_enabled=True, duplicate_debounce_ms=1000,
            sound_on_success=True, sound_on_not_found=True, show_visual_notification=True,
        )
    )
    base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)

    service.resolve_scan("7701234567890", source=BarcodeReadSource.SALE, now=base)
    still_within = service.resolve_scan(
        "7701234567890",
        source=BarcodeReadSource.SALE,
        now=base + timedelta(milliseconds=800),
    )

    assert still_within.ignored


def test_resolve_scan_is_ignored_when_the_reader_is_disabled(sqlite_engine: None) -> None:
    service = _make_service()
    _create_product_with_barcode(service._product_service, "7701234567890")
    service.save_settings(
        BarcodeSettingsDTO(
            reader_enabled=False, auto_enter_enabled=True, duplicate_debounce_ms=150,
            sound_on_success=True, sound_on_not_found=True, show_visual_notification=True,
        )
    )

    result = service.resolve_scan("7701234567890", source=BarcodeReadSource.SALE)

    assert result.ignored
    assert "desactivado" in (result.reason or "").lower()


def test_resolve_scan_records_found_and_not_found_reads_with_context(sqlite_engine: None) -> None:
    service = _make_service()
    product = _create_product_with_barcode(service._product_service, "7701234567890")

    service.resolve_scan(
        "7701234567890",
        source=BarcodeReadSource.SALE,
        user_id=1,
        username="Diego",
        cash_register_id=2,
        cash_register_name="Caja 1",
    )
    service.resolve_scan("0000000000000", source=BarcodeReadSource.SALE)

    entries = service.list_recent_reads()
    assert len(entries) == 2
    found_entry = next(e for e in entries if e.code == "7701234567890")
    not_found_entry = next(e for e in entries if e.code == "0000000000000")
    assert found_entry.found
    assert found_entry.product_id == product.id
    assert found_entry.product_name == product.name
    assert found_entry.username == "Diego"
    assert found_entry.cash_register_name == "Caja 1"
    assert not not_found_entry.found
    assert not_found_entry.product_id is None


def test_get_diagnostics_aggregates_counts_and_last_read(sqlite_engine: None) -> None:
    service = _make_service()
    _create_product_with_barcode(service._product_service, "7701234567890")
    base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)

    service.resolve_scan("7701234567890", source=BarcodeReadSource.SALE, now=base)
    service.resolve_scan(
        "0000000000000",
        source=BarcodeReadSource.SALE,
        now=base + timedelta(seconds=2),
    )

    diagnostics = service.get_diagnostics()

    assert diagnostics.total_reads == 2
    assert diagnostics.error_count == 1
    assert diagnostics.last_code == "0000000000000"
    assert diagnostics.average_interval_ms == 2000.0
    assert diagnostics.has_recent_activity is False


def test_get_diagnostics_reports_no_activity_when_nothing_was_read(sqlite_engine: None) -> None:
    service = _make_service()

    diagnostics = service.get_diagnostics()

    assert diagnostics.total_reads == 0
    assert diagnostics.last_code is None
    assert diagnostics.average_interval_ms is None
    assert diagnostics.has_recent_activity is False


def test_get_diagnostics_detects_recent_activity(sqlite_engine: None) -> None:
    service = _make_service()
    _create_product_with_barcode(service._product_service, "7701234567890")

    service.resolve_scan("7701234567890", source=BarcodeReadSource.SALE)

    diagnostics = service.get_diagnostics()

    assert diagnostics.has_recent_activity is True


def test_resolve_scan_ignores_input_that_normalizes_to_an_empty_code(sqlite_engine: None) -> None:
    service = _make_service()

    result = service.resolve_scan("   \t  ", source=BarcodeReadSource.SALE)

    assert result.ignored
    assert result.found is False
    assert "vacío" in (result.reason or "").lower()


def test_resolve_scan_ignores_a_code_longer_than_the_maximum(sqlite_engine: None) -> None:
    service = _make_service()

    result = service.resolve_scan("9" * 65, source=BarcodeReadSource.SALE)

    assert result.ignored
    assert "largo" in (result.reason or "").lower()
    diagnostics = service.get_diagnostics()
    assert diagnostics.total_reads == 0, "un código descartado por longitud no debe registrarse"


def test_get_settings_falls_back_to_default_debounce_when_the_stored_value_is_corrupt(
    sqlite_engine: None,
) -> None:
    """Cubre el caso de una configuración dañada (edición manual de la
    base, migración futura, etc.) — `get_settings` nunca debe lanzar una
    excepción por esto, cae al valor por defecto."""
    settings = BusinessSettingsService(EventBus())
    settings.set_value("barcode_duplicate_debounce_ms", "no-es-un-numero", SettingValueType.STRING)
    service = BarcodeReadService(settings, ProductManagementService(EventBus()))

    result_settings = service.get_settings()

    assert result_settings.duplicate_debounce_ms == 150
