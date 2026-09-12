"""Pruebas de `format_audit_entry`: traduce entradas de `sync_log` a texto
legible, con un fallback seguro para tipos de evento desconocidos o
payloads malformados."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from pos.modules.sync.application.audit_formatter import format_audit_entry
from pos.modules.sync.application.dto import SyncLogEntryDTO
from pos.modules.sync.domain.enums import SyncLogStatus

_NOW = datetime(2026, 7, 12, tzinfo=UTC)


def _entry(event_type: str, payload: dict[str, object]) -> SyncLogEntryDTO:
    return SyncLogEntryDTO(
        id=1,
        event_type=event_type,
        entity_type="sales",
        entity_uuid="uuid-1",
        payload_json=json.dumps(payload),
        status=SyncLogStatus.PENDING,
        origin_station_name="Estación principal",
        created_at=_NOW,
        applied_at=None,
    )


def test_sale_completed_with_user() -> None:
    entry = _entry(
        "SaleCompletedEvent",
        {"sale_id": 42, "total": "45000.00", "customer_id": None, "created_by_user_id": 7},
    )
    assert format_audit_entry(entry) == "Venta #42 completada — $45.000 (usuario #7)"


def test_sale_completed_without_user() -> None:
    entry = _entry(
        "SaleCompletedEvent",
        {"sale_id": 42, "total": "45000.00", "customer_id": None, "created_by_user_id": None},
    )
    assert format_audit_entry(entry) == "Venta #42 completada — $45.000"


def test_sale_voided_with_reason_and_user() -> None:
    entry = _entry(
        "SaleVoidedEvent",
        {"sale_id": 42, "reason": "Cliente se arrepintió", "voided_by_user_id": 3},
    )
    assert (
        format_audit_entry(entry)
        == "Venta #42 anulada — motivo: Cliente se arrepintió (usuario #3)"
    )


def test_cash_session_closed_with_difference() -> None:
    entry = _entry("CashSessionClosedEvent", {"cash_session_id": 5, "difference": "-2000.00"})
    assert format_audit_entry(entry) == "Turno de caja #5 cerrado — diferencia -$2.000"


def test_stock_level_changed_below_minimum() -> None:
    entry = _entry(
        "StockLevelChangedEvent",
        {"product_id": 9, "warehouse_id": 1, "new_quantity": "2.000", "is_below_minimum": True},
    )
    assert format_audit_entry(entry) == "Stock del producto #9 actualizado a 2.000 (bajo mínimo)"


def test_unknown_event_type_falls_back_to_raw_name() -> None:
    entry = _entry("SomeFutureEvent", {"anything": "goes"})
    assert format_audit_entry(entry) == "SomeFutureEvent"


def test_malformed_payload_falls_back_to_raw_name() -> None:
    entry = SyncLogEntryDTO(
        id=1,
        event_type="SaleCompletedEvent",
        entity_type="sales",
        entity_uuid="uuid-1",
        payload_json="not valid json",
        status=SyncLogStatus.PENDING,
        origin_station_name="Estación principal",
        created_at=_NOW,
        applied_at=None,
    )
    assert format_audit_entry(entry) == "SaleCompletedEvent"


@pytest.mark.parametrize(
    ("event_type", "payload", "expected"),
    [
        ("CashSessionOpenedEvent", {"cash_session_id": 1}, "Turno de caja #1 abierto"),
        ("UserStatusChangedEvent", {"user_id": 2, "is_active": False}, "Usuario #2 desactivado"),
        (
            "ProductStatusChangedEvent",
            {"product_id": 3, "is_active": True},
            "Producto #3 activado",
        ),
    ],
)
def test_other_known_event_types(event_type: str, payload: dict[str, object], expected: str) -> None:
    assert format_audit_entry(_entry(event_type, payload)) == expected
