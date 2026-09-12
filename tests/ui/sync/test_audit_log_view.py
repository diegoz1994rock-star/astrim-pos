"""Prueba de UI de `AuditLogView` (backend `offscreen`): la tabla se
puebla con la descripción legible ya calculada por el view model, no con
el `event_type` crudo ni el payload JSON."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

from pytestqt.qtbot import QtBot

from pos.modules.sync.application.dto import SyncLogEntryDTO
from pos.modules.sync.domain.enums import SyncLogStatus
from pos.modules.sync.presentation.audit_log_view import AuditLogView


def test_table_shows_readable_description(qtbot: QtBot) -> None:
    view = AuditLogView(Mock())
    qtbot.addWidget(view)

    entry = SyncLogEntryDTO(
        id=1,
        event_type="SaleCompletedEvent",
        entity_type="sales",
        entity_uuid="uuid-1",
        payload_json="{}",
        status=SyncLogStatus.PENDING,
        origin_station_name="Estación principal",
        created_at=datetime(2026, 7, 12, 10, 30, tzinfo=UTC),
        applied_at=None,
    )
    view._on_entries_loaded([(entry, "Venta #1 completada — $1.000")])

    assert view._table.rowCount() == 1
    assert view._table.item(0, 1).text() == "Venta #1 completada — $1.000"
    assert view._table.item(0, 2).text() == "SaleCompletedEvent"
    assert view._table.item(0, 3).text() == "Estación principal"


def test_refresh_button_reloads(qtbot: QtBot) -> None:
    view_model = Mock()
    view = AuditLogView(view_model)
    qtbot.addWidget(view)
    view_model.load.reset_mock()

    view._on_refresh_clicked()

    view_model.load.assert_called_once_with()
