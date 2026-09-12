"""Pruebas de integración de los códigos de barras de producto contra
SQLite real: alta/edición/eliminación, unicidad global, la única fuente de
verdad que usa Ventas (`find_product_by_barcode`) y que `list_products()`
trae los códigos sin duplicar consultas."""

from __future__ import annotations

import threading
from decimal import Decimal

import pytest

from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.products.application.product_service import (
    MAX_BARCODE_LENGTH,
    ProductManagementService,
)
from pos.modules.products.domain.enums import ProductType
from pos.modules.products.infrastructure.product_repository import ProductRepository


def _create_simple(service: ProductManagementService, sku: str, name: str):
    return service.create_product(
        sku=sku,
        name=name,
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("10.00"),
        cost_price=Decimal("5.00"),
        unit_of_measure="unidad",
        track_inventory=True,
    )


def test_add_barcode_and_list_barcodes(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    product = _create_simple(service, "SKU-1", "Martillo 5K")

    service.add_barcode(product.id, "7701234567890")

    barcodes = service.list_barcodes(product.id)
    assert [b.code for b in barcodes] == ["7701234567890"]


def test_product_can_have_multiple_barcodes(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    product = _create_simple(service, "SKU-1", "Martillo 5K")

    service.add_barcode(product.id, "7701234567890")
    service.add_barcode(product.id, "7709876543210")

    barcodes = service.list_barcodes(product.id)
    assert [b.code for b in barcodes] == ["7701234567890", "7709876543210"]


def test_add_barcode_rejects_empty_code(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    product = _create_simple(service, "SKU-1", "Martillo 5K")

    with pytest.raises(BusinessRuleViolationError):
        service.add_barcode(product.id, "   ")


def test_add_barcode_raises_not_found_for_an_unknown_product(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())

    with pytest.raises(NotFoundError):
        service.add_barcode(9999, "7701234567890")


def test_update_barcode_rejects_empty_code(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    product = _create_simple(service, "SKU-1", "Martillo 5K")
    barcode = service.add_barcode(product.id, "7701234567890")

    with pytest.raises(BusinessRuleViolationError):
        service.update_barcode(barcode.id, "   ")


def test_update_barcode_translates_a_database_level_conflict_into_a_friendly_error(
    sqlite_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = ProductManagementService(EventBus())
    owner = _create_simple(service, "SKU-1", "Martillo 5K")
    service.add_barcode(owner.id, "7701234567890")
    other = _create_simple(service, "SKU-2", "Destornillador")
    other_barcode = service.add_barcode(other.id, "1112223334445")

    monkeypatch.setattr(ProductRepository, "get_barcode_by_code", lambda self, code: None)

    with pytest.raises(ConflictError):
        service.update_barcode(other_barcode.id, "7701234567890")


def test_get_product_names_returns_names_for_the_given_ids(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    martillo = _create_simple(service, "SKU-1", "Martillo 5K")
    destornillador = _create_simple(service, "SKU-2", "Destornillador")
    _create_simple(service, "SKU-3", "Sin usar")

    names = service.get_product_names([martillo.id, destornillador.id])

    assert names == {martillo.id: "Martillo 5K", destornillador.id: "Destornillador"}


def test_get_product_names_with_no_ids_returns_an_empty_dict(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())

    assert service.get_product_names([]) == {}


def test_add_barcode_rejects_duplicate_across_products(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    martillo = _create_simple(service, "SKU-1", "Martillo 5K")
    _create_simple(service, "SKU-2", "Destornillador")
    service.add_barcode(martillo.id, "7701234567890")

    other = _create_simple(service, "SKU-3", "Otro producto")

    with pytest.raises(ConflictError, match="Martillo 5K"):
        service.add_barcode(other.id, "7701234567890")


def test_add_barcode_error_message_names_owner_and_sku(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    martillo = _create_simple(service, "SKU-1", "Martillo 5K")
    service.add_barcode(martillo.id, "7701234567890")
    other = _create_simple(service, "SKU-2", "Otro producto")

    with pytest.raises(ConflictError, match="SKU-1"):
        service.add_barcode(other.id, "7701234567890")


def test_find_product_by_barcode_resolves_the_right_product(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    _create_simple(service, "SKU-1", "Martillo 5K")
    destornillador = _create_simple(service, "SKU-2", "Destornillador")
    service.add_barcode(destornillador.id, "7709876543210")

    found = service.find_product_by_barcode("7709876543210")

    assert found is not None
    assert found.id == destornillador.id
    assert found.sku == "SKU-2"


def test_find_product_by_barcode_returns_none_when_unknown(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())

    assert service.find_product_by_barcode("0000000000000") is None


def test_remove_barcode(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    product = _create_simple(service, "SKU-1", "Martillo 5K")
    barcode = service.add_barcode(product.id, "7701234567890")

    service.remove_barcode(barcode.id)

    assert service.list_barcodes(product.id) == []
    assert service.find_product_by_barcode("7701234567890") is None


def test_update_barcode_changes_the_code_in_place(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    product = _create_simple(service, "SKU-1", "Martillo 5K")
    barcode = service.add_barcode(product.id, "7701234567890")

    service.update_barcode(barcode.id, "7709999999999")

    barcodes = service.list_barcodes(product.id)
    assert [b.code for b in barcodes] == ["7709999999999"]
    assert service.find_product_by_barcode("7701234567890") is None
    assert service.find_product_by_barcode("7709999999999") is not None


def test_update_barcode_rejects_duplicate_owned_by_another_product(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    martillo = _create_simple(service, "SKU-1", "Martillo 5K")
    service.add_barcode(martillo.id, "7701234567890")
    destornillador = _create_simple(service, "SKU-2", "Destornillador")
    own_barcode = service.add_barcode(destornillador.id, "7709876543210")

    with pytest.raises(ConflictError):
        service.update_barcode(own_barcode.id, "7701234567890")


def test_update_barcode_unknown_id_raises_not_found(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())

    with pytest.raises(NotFoundError):
        service.update_barcode(9999, "7701234567890")


def test_find_barcode_conflict_excludes_own_barcode_id(sqlite_engine: None) -> None:
    """Al "modificar" un código sin cambiarlo, no debe reportarse a sí
    mismo como un conflicto (ver `AddBarcodeDialog`, modo edición)."""
    service = ProductManagementService(EventBus())
    product = _create_simple(service, "SKU-1", "Martillo 5K")
    barcode = service.add_barcode(product.id, "7701234567890")

    conflict = service.find_barcode_conflict("7701234567890", exclude_barcode_id=barcode.id)

    assert conflict is None


def test_find_barcode_conflict_reports_owner_without_exclusion(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    product = _create_simple(service, "SKU-1", "Martillo 5K")
    service.add_barcode(product.id, "7701234567890")

    conflict = service.find_barcode_conflict("7701234567890")

    assert conflict is not None
    assert conflict.sku == "SKU-1"


def test_list_products_includes_barcodes_without_extra_calls(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    product = _create_simple(service, "SKU-1", "Martillo 5K")
    service.add_barcode(product.id, "7701234567890")
    service.add_barcode(product.id, "7709876543210")
    _create_simple(service, "SKU-2", "Sin código")

    products = service.list_products()

    by_sku = {p.sku: p for p in products}
    assert by_sku["SKU-1"].barcodes == ("7701234567890", "7709876543210")
    assert by_sku["SKU-2"].barcodes == ()


def test_deleting_product_cascades_to_its_barcodes(sqlite_engine: None) -> None:
    """`ProductBarcode.product_id` tiene `ondelete=CASCADE` — pero el
    borrado de producto en esta app es lógico (`is_deleted`), así que el
    código sigue existiendo (comportamiento correcto: el producto sigue
    en la base para historial/auditoría)."""
    service = ProductManagementService(EventBus())
    product = _create_simple(service, "SKU-1", "Martillo 5K")
    service.add_barcode(product.id, "7701234567890")

    service.delete_product(product.id)

    assert service.find_product_by_barcode("7701234567890") is not None


def test_generate_unique_barcode_returns_a_free_valid_ean13(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())

    code = service.generate_unique_barcode()

    assert len(code) == 13
    assert code.isdigit()
    assert service.find_product_by_barcode(code) is None


def test_generate_unique_barcode_retries_on_collision(
    sqlite_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nunca puede repetirse: si el candidato generado ya existe, se
    descarta y se genera otro — se fuerza la colisión reemplazando el
    generador para probar el reintento real, no simulado."""
    service = ProductManagementService(EventBus())
    product = _create_simple(service, "SKU-1", "Martillo 5K")
    service.add_barcode(product.id, "1111111111117")

    candidates = iter(["1111111111117", "2222222222224"])
    monkeypatch.setattr(
        "pos.modules.products.application.product_service.generate_ean13_candidate",
        lambda: next(candidates),
    )

    code = service.generate_unique_barcode()

    assert code == "2222222222224"


def test_generate_unique_barcode_raises_after_exhausting_attempts(
    sqlite_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = ProductManagementService(EventBus())
    product = _create_simple(service, "SKU-1", "Martillo 5K")
    service.add_barcode(product.id, "1111111111117")
    monkeypatch.setattr(
        "pos.modules.products.application.product_service.generate_ean13_candidate",
        lambda: "1111111111117",
    )

    with pytest.raises(BusinessRuleViolationError):
        service.generate_unique_barcode()


def test_add_barcode_rejects_a_code_longer_than_the_limit(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    product = _create_simple(service, "SKU-1", "Martillo 5K")

    with pytest.raises(BusinessRuleViolationError):
        service.add_barcode(product.id, "1" * (MAX_BARCODE_LENGTH + 1))


def test_update_barcode_rejects_a_code_longer_than_the_limit(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    product = _create_simple(service, "SKU-1", "Martillo 5K")
    barcode = service.add_barcode(product.id, "7701234567890")

    with pytest.raises(BusinessRuleViolationError):
        service.update_barcode(barcode.id, "9" * (MAX_BARCODE_LENGTH + 1))


def test_add_barcode_translates_a_database_level_conflict_into_a_friendly_error(
    sqlite_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simula exactamente la condición de carrera real: el chequeo previo
    en aplicación no ve el conflicto (porque la otra transacción todavía
    no había confirmado cuando se hizo la lectura), pero la restricción
    UNIQUE de la base de datos sí lo detiene — el resultado debe ser el
    mismo `ConflictError` de siempre, nunca una excepción cruda de
    SQLAlchemy."""
    service = ProductManagementService(EventBus())
    owner = _create_simple(service, "SKU-1", "Martillo 5K")
    service.add_barcode(owner.id, "7701234567890")
    other = _create_simple(service, "SKU-2", "Destornillador")

    monkeypatch.setattr(ProductRepository, "get_barcode_by_code", lambda self, code: None)

    with pytest.raises(ConflictError):
        service.add_barcode(other.id, "7701234567890")


def test_add_barcode_under_real_concurrent_writes_only_one_succeeds(
    sqlite_engine: None,
) -> None:
    """Prueba de concurrencia real (no simulada): dos hilos, cada uno con
    su propia sesión de base de datos, intentan registrar EXACTAMENTE el
    mismo código para productos distintos al mismo tiempo — sincronizados
    con una barrera para forzar que ambos pasen su chequeo de duplicado
    antes de que cualquiera de los dos inserte. Exactamente uno debe tener
    éxito; el otro debe recibir `ConflictError`, nunca un error crudo ni un
    duplicado silencioso en la base de datos."""
    service = ProductManagementService(EventBus())
    product_a = _create_simple(service, "SKU-A", "Producto A")
    product_b = _create_simple(service, "SKU-B", "Producto B")
    code = "7701234567890"

    barrier = threading.Barrier(2)
    original_get_barcode_by_code = ProductRepository.get_barcode_by_code

    def _synchronized_check(self: ProductRepository, lookup_code: str):
        result = original_get_barcode_by_code(self, lookup_code)
        barrier.wait(timeout=5)
        return result

    results: dict[str, object] = {}

    def _attempt(name: str, product_id: int) -> None:
        try:
            service.add_barcode(product_id, code)
            results[name] = "success"
        except ConflictError:
            results[name] = "conflict"
        except Exception as error:  # pragma: no cover - solo si algo va mal de verdad
            results[name] = error

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(ProductRepository, "get_barcode_by_code", _synchronized_check)
        thread_a = threading.Thread(target=_attempt, args=("a", product_a.id))
        thread_b = threading.Thread(target=_attempt, args=("b", product_b.id))
        thread_a.start()
        thread_b.start()
        thread_a.join(timeout=10)
        thread_b.join(timeout=10)

    assert sorted(results.values(), key=str) == ["conflict", "success"]
    assert service.find_product_by_barcode(code) is not None
    winner_id = product_a.id if results["a"] == "success" else product_b.id
    assert service.find_product_by_barcode(code).id == winner_id
