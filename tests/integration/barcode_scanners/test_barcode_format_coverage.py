"""FASE 3 de la certificación: prueba, uno por uno, que el camino real de
venta (`BarcodeReadService.resolve_scan`) reconoce cualquier formato que
un lector HID pueda entregar — EAN-13, EAN-8, UPC-A, UPC-E, Code 39,
Code 128, ISBN-13/ISBN-10, numérico, alfanumérico, largo, corto, con
espacios y con caracteres invisibles. El almacenamiento es deliberadamente
agnóstico de formato (`ProductBarcode.code`, `String(64)` sin validar
checksum/longitud) — lo que se certifica acá es que NINGÚN formato real se
pierde o se rechaza al guardarlo y volver a leerlo."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from pos.core.events.bus import EventBus
from pos.modules.barcode_scanners.application.barcode_read_service import BarcodeReadService
from pos.modules.barcode_scanners.domain.enums import BarcodeReadSource, BarcodeSymbology
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.products.domain.enums import ProductType
from pos.modules.settings.application.business_settings_service import BusinessSettingsService


def _make_service() -> tuple[BarcodeReadService, ProductManagementService]:
    product_service = ProductManagementService(EventBus())
    return (
        BarcodeReadService(BusinessSettingsService(EventBus()), product_service),
        product_service,
    )


def _register(product_service: ProductManagementService, code: str, name: str) -> int:
    product = product_service.create_product(
        sku=f"SKU-{abs(hash(code))}",
        name=name,
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("10.00"),
        cost_price=Decimal("5.00"),
        unit_of_measure="unidad",
        track_inventory=True,
    )
    product_service.add_barcode(product.id, code)
    return product.id


@pytest.mark.parametrize(
    ("code", "expected_symbology"),
    [
        pytest.param("7701234567890", BarcodeSymbology.EAN13, id="EAN-13"),
        pytest.param("40123455", BarcodeSymbology.EAN8, id="EAN-8"),
        pytest.param("036000291452", BarcodeSymbology.UPC_A, id="UPC-A"),
        pytest.param("012345", BarcodeSymbology.UPC_E, id="UPC-E (6 dígitos, 0 inicial)"),
        pytest.param("9780306406157", BarcodeSymbology.EAN13, id="ISBN-13 (Bookland EAN)"),
        pytest.param("ABC-123-XYZ", BarcodeSymbology.CODE128, id="Code 39/128 alfanumérico"),
        pytest.param("A1", BarcodeSymbology.CODE128, id="alfanumérico muy corto"),
    ],
)
def test_resolve_scan_finds_the_product_for_every_supported_format(
    sqlite_engine: None, code: str, expected_symbology: BarcodeSymbology
) -> None:
    service, product_service = _make_service()
    product_id = _register(product_service, code, f"Producto {code}")

    result = service.resolve_scan(code, source=BarcodeReadSource.SALE)

    assert result.found
    assert result.product is not None
    assert result.product.id == product_id
    assert result.symbology is expected_symbology


def test_resolve_scan_finds_an_isbn10_style_code_with_check_letter(sqlite_engine: None) -> None:
    """ISBN-10 no es EAN — no se declara "certero" como ninguna simbología
    conocida (cae a CODE128, honesto), pero se guarda y se reconoce por
    texto exacto igual que cualquier otro código, con la 'X' final
    incluida."""
    service, product_service = _make_service()
    code = "080442957X"
    product_id = _register(product_service, code, "Libro")

    result = service.resolve_scan(code, source=BarcodeReadSource.SALE)

    assert result.found
    assert result.product.id == product_id


def test_resolve_scan_finds_a_purely_numeric_internal_code(sqlite_engine: None) -> None:
    service, product_service = _make_service()
    product_id = _register(product_service, "123456", "Producto interno")

    result = service.resolve_scan("123456", source=BarcodeReadSource.SALE)

    assert result.found
    assert result.product.id == product_id


def test_resolve_scan_finds_a_very_long_code_up_to_the_column_limit(sqlite_engine: None) -> None:
    service, product_service = _make_service()
    long_code = "GS1-" + "9" * 55  # 59 caracteres, dentro del límite de 64.
    product_id = _register(product_service, long_code, "Caja mayorista")

    result = service.resolve_scan(long_code, source=BarcodeReadSource.SALE)

    assert result.found
    assert result.product.id == product_id


def test_resolve_scan_finds_a_single_character_code(sqlite_engine: None) -> None:
    service, product_service = _make_service()
    product_id = _register(product_service, "9", "Producto de código mínimo")

    result = service.resolve_scan("9", source=BarcodeReadSource.SALE)

    assert result.found
    assert result.product.id == product_id


def test_resolve_scan_trims_surrounding_whitespace_before_matching(sqlite_engine: None) -> None:
    """Un lector que agregue un espacio de más (o el propio SO) no debe
    impedir el match — el mismo `normalize_scan` que usa Ventas."""
    service, product_service = _make_service()
    product_id = _register(product_service, "7701234567890", "Martillo")

    result = service.resolve_scan("  7701234567890  ", source=BarcodeReadSource.SALE)

    assert result.found
    assert result.product.id == product_id


def test_resolve_scan_strips_embedded_control_characters_before_matching(
    sqlite_engine: None,
) -> None:
    """Cubre CR/LF/CRLF/Tab si llegaran como caracteres literales dentro
    del texto (en vez de como pulsaciones de tecla reales) — nunca deben
    quedar pegados al código ni impedir el match."""
    service, product_service = _make_service()
    product_id = _register(product_service, "7701234567890", "Martillo")
    base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)

    variants = (
        "7701234567890\r",
        "7701234567890\n",
        "7701234567890\r\n",
        "7701234567890\t",
        "\t7701234567890",
    )
    for index, raw in enumerate(variants):
        # Cada variante se separa más allá de la ventana de rebote — de lo
        # contrario el propio filtro de doble lectura (correcto) las vería
        # como el mismo código repetido demasiado rápido, que es justo lo
        # que se espera que haga, no un defecto de esta prueba.
        result = service.resolve_scan(
            raw, source=BarcodeReadSource.SALE, now=base + timedelta(seconds=index)
        )
        assert result.found, f"No se encontró el producto para la variante {raw!r}"
        assert result.product.id == product_id
