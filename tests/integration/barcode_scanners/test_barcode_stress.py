"""FASE 5 de la certificación: escaneos masivos/continuos contra
`BarcodeReadService` real (SQLite en archivo, no simulado) — verifica que
no haya bloqueos, pérdida de eventos, duplicados incorrectos ni
crecimiento de memoria sin límite, y que el tiempo se mantenga estable
incluso con miles de lecturas."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pos.core.events.bus import EventBus
from pos.modules.barcode_scanners.application.barcode_read_service import (
    _DEBOUNCE_ENTRY_MAX_AGE,
    BarcodeReadService,
)
from pos.modules.barcode_scanners.domain.enums import BarcodeReadSource
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.products.domain.enums import ProductType
from pos.modules.settings.application.business_settings_service import BusinessSettingsService

_MAX_ACCEPTABLE_AVERAGE_MS = 20.0
"""Cota deliberadamente generosa (>>que lo medido en desarrollo, ~0.7ms/
lectura): esto no mide "qué tan rápido es", mide "que nunca se vuelva
inaceptablemente lento" sin que la prueba sea frágil por el hardware
donde corra."""


def _make_service() -> tuple[BarcodeReadService, ProductManagementService]:
    product_service = ProductManagementService(EventBus())
    return (
        BarcodeReadService(BusinessSettingsService(EventBus()), product_service),
        product_service,
    )


def _register_catalog(product_service: ProductManagementService, count: int) -> list[str]:
    codes = []
    for index in range(count):
        product = product_service.create_product(
            sku=f"SKU-{index}",
            name=f"Producto {index}",
            description=None,
            category_id=None,
            product_type=ProductType.SIMPLE,
            unit_price=Decimal("10.00"),
            cost_price=Decimal("5.00"),
            unit_of_measure="unidad",
            track_inventory=True,
        )
        code = f"77{index:011d}"
        product_service.add_barcode(product.id, code)
        codes.append(code)
    return codes


def test_5000_unique_scans_complete_without_errors_within_a_stable_time_budget(
    sqlite_engine: None,
) -> None:
    service, product_service = _make_service()
    scan_count = 5000

    start = time.perf_counter()
    for index in range(scan_count):
        result = service.resolve_scan(f"9999{index:010d}", source=BarcodeReadSource.SALE)
        assert not result.ignored
        assert not result.found  # ninguno de estos códigos está registrado.
    elapsed = time.perf_counter() - start

    average_ms = (elapsed / scan_count) * 1000
    assert average_ms < _MAX_ACCEPTABLE_AVERAGE_MS, (
        f"Promedio de {average_ms:.3f} ms/lectura, por encima del límite aceptado"
    )


def test_1000_scans_of_a_real_catalog_never_lose_a_read_or_mismatch_a_product(
    sqlite_engine: None,
) -> None:
    """Simula una jornada con un catálogo de 50 productos y 1000 lecturas
    mezcladas (repetidas, secuenciales, algunas inexistentes) — cada
    resultado debe apuntar exactamente al producto correcto, nunca a otro
    ni perderse."""
    service, product_service = _make_service()
    codes = _register_catalog(product_service, 50)
    base = datetime(2026, 1, 1, 8, 0, 0, tzinfo=UTC)

    found_count = 0
    not_found_count = 0
    for index in range(1000):
        # Espaciado generoso (1s) para que el filtro de rebote nunca
        # interfiera con esta prueba — el rebote real ya está cubierto
        # aparte, acá se mide throughput/consistencia, no debounce.
        now = base + timedelta(seconds=index)
        if index % 7 == 0:
            result = service.resolve_scan("0000000000000", source=BarcodeReadSource.SALE, now=now)
            assert not result.found
            not_found_count += 1
        else:
            code = codes[index % len(codes)]
            result = service.resolve_scan(code, source=BarcodeReadSource.SALE, now=now)
            assert result.found
            assert result.product is not None
            assert code in result.product.barcodes
            found_count += 1

    assert found_count + not_found_count == 1000
    diagnostics = service.get_diagnostics()
    assert diagnostics.total_reads == 1000
    assert diagnostics.error_count == not_found_count


def test_debounce_dictionary_does_not_grow_without_bound_over_a_long_session(
    sqlite_engine: None,
) -> None:
    """Escanea miles de códigos distintos repartidos en el tiempo (una
    jornada larga simulada) y confirma que el diccionario de rebote en
    memoria se poda solo, en vez de acumular cada código escaneado alguna
    vez desde que arrancó el proceso — la fuga de memoria que existiría
    sin `_prune_stale_debounce_entries`."""
    service, _ = _make_service()
    base = datetime(2026, 1, 1, 8, 0, 0, tzinfo=UTC)
    prune_margin = _DEBOUNCE_ENTRY_MAX_AGE + timedelta(seconds=1)

    for index in range(300):
        # Cada lectura llega bastante más tarde que la ventana de poda de
        # la anterior — así cada una debería expulsar a la de antes del
        # diccionario en vez de acumularse.
        now = base + index * prune_margin
        service.resolve_scan(f"8888{index:010d}", source=BarcodeReadSource.SALE, now=now)
        assert len(service._last_read_at) <= 2, (
            f"El diccionario de rebote creció a {len(service._last_read_at)} "
            "entradas — no se está podando correctamente."
        )


def test_repeated_scans_within_the_debounce_window_are_never_double_counted(
    sqlite_engine: None,
) -> None:
    """Cientos de "rebotes" del mismo código, todos dentro de la ventana
    de 150 ms, deben colapsar en una sola lectura real registrada."""
    service, product_service = _make_service()
    codes = _register_catalog(product_service, 1)
    base = datetime(2026, 1, 1, 8, 0, 0, tzinfo=UTC)

    ignored_count = 0
    processed_count = 0
    for index in range(500):
        # 500 lecturas en 500ms — la mayoría cae dentro de los 150ms de
        # rebote desde la última lectura realmente procesada.
        now = base + timedelta(milliseconds=index)
        result = service.resolve_scan(codes[0], source=BarcodeReadSource.SALE, now=now)
        if result.ignored:
            ignored_count += 1
        else:
            processed_count += 1

    assert ignored_count > 0
    diagnostics = service.get_diagnostics()
    assert diagnostics.total_reads == processed_count
