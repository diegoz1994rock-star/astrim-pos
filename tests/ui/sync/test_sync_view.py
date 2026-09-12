"""Pruebas de UI de `SyncView` (backend `offscreen`) con `SyncViewModel`
simulado (`Mock`): panel de estado, botones de control, y las tablas/
listas nuevas (clientes conectados, diagnóstico, consola de eventos)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

from pytestqt.qtbot import QtBot

from pos.modules.sync.application.dto import (
    DiagnosticStepDTO,
    ServerProbeResultDTO,
    SyncConnectionDTO,
    SyncEventLogLineDTO,
    SyncStationDTO,
    SyncStatusDTO,
)
from pos.modules.sync.domain.enums import SyncMode, SyncStationStatus
from pos.modules.sync.presentation.sync_view import SyncView


def _status(**overrides: object) -> SyncStatusDTO:
    defaults: dict[str, object] = dict(
        mode=SyncMode.PRIMARY,
        local_station_name="Caja 1",
        peer_url=None,
        server_port=8765,
        running=True,
        connected=False,
        pending_outbound_count=0,
        local_ip="192.168.1.50",
        websocket_url="ws://192.168.1.50:8765/ws/sync",
        uptime_seconds=90.0,
        last_error=None,
        sent_count=0,
        received_count=0,
        failed_count=0,
        connections_count=0,
        auto_start_enabled=True,
    )
    defaults.update(overrides)
    return SyncStatusDTO(**defaults)


def _connection(name: str, latency_ms: float | None = 10.0) -> SyncConnectionDTO:
    return SyncConnectionDTO(
        station_name=name,
        ip="192.168.1.20",
        port=54321,
        connected_at=datetime.now(UTC),
        last_sync_at=datetime.now(UTC),
        app_version="0.1.0",
        latency_ms=latency_ms,
    )


def _station(name: str, *, status: SyncStationStatus = SyncStationStatus.ONLINE) -> SyncStationDTO:
    return SyncStationDTO(
        id=1, name=name, is_primary=False, status=status, last_seen_at=datetime.now(UTC)
    )


def _make_view(qtbot: QtBot) -> SyncView:
    view = SyncView(Mock())
    qtbot.addWidget(view)
    return view


def test_status_changed_shows_online_badge_when_server_running(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._on_status_changed(_status(mode=SyncMode.PRIMARY, running=True))

    assert "EN LÍNEA" in view._status_badge._label.text()
    assert view._info_ip_label.text() == "192.168.1.50"
    assert view._info_url_label.text() == "ws://192.168.1.50:8765/ws/sync"
    assert view._current_url == "ws://192.168.1.50:8765/ws/sync"


def test_status_changed_shows_stopped_badge_when_server_not_running(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._on_status_changed(_status(mode=SyncMode.PRIMARY, running=False, last_error=None))

    assert "DETENIDO" in view._status_badge._label.text()


def test_status_changed_shows_error_badge_when_last_start_failed(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._on_status_changed(
        _status(mode=SyncMode.PRIMARY, running=False, last_error="El puerto 8765 ya está en uso.")
    )

    assert "Error al iniciar" in view._status_badge._label.text()


def test_status_changed_shows_connected_badge_in_client_mode(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._on_status_changed(_status(mode=SyncMode.CLIENT, running=False, connected=True))

    assert "Conectado" in view._status_badge._label.text()


def test_status_changed_shows_disabled_badge(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._on_status_changed(_status(mode=SyncMode.DISABLED))

    assert "deshabilitada" in view._status_badge._label.text()


def test_start_button_calls_view_model(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._start_button.click()

    view._view_model.start_server.assert_called_once()


def test_stop_button_calls_view_model(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._stop_button.click()

    view._view_model.stop_server.assert_called_once()


def test_copy_url_button_copies_current_url_to_clipboard(qtbot: QtBot) -> None:
    from PySide6.QtWidgets import QApplication

    view = _make_view(qtbot)
    view._on_status_changed(_status(websocket_url="ws://192.168.1.50:8765/ws/sync"))

    view._copy_url_button.click()

    assert QApplication.clipboard().text() == "ws://192.168.1.50:8765/ws/sync"


def test_connections_loaded_populates_table_and_average_latency(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._on_connections_loaded([_connection("Caja 2", 10.0), _connection("Caja 3", 20.0)])

    assert view._connections_table.rowCount() == 2
    assert view._connections_table.item(0, 0).text() == "Caja 2"
    assert view._stat_latency_label.text() == "15 ms"


def test_disconnected_stat_excludes_local_and_connected_stations(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_status_changed(_status(local_station_name="Caja 1"))
    view._on_stations_loaded(
        [_station("Caja 1"), _station("Caja 2"), _station("Caja 3")]
    )

    view._on_connections_loaded([_connection("Caja 2")])

    # "Caja 1" es la propia estación (excluida), "Caja 2" está conectada
    # ahora mismo, solo "Caja 3" cuenta como desconectada.
    assert view._stat_disconnected_clients_label.text() == "1"


def test_events_loaded_populates_console(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._on_events_loaded(
        [SyncEventLogLineDTO(occurred_at=datetime.now(UTC), message="Servidor iniciado")]
    )

    assert view._event_console.count() == 1
    assert "Servidor iniciado" in view._event_console.item(0).text()


def test_diagnostic_result_shows_each_step(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    result = ServerProbeResultDTO(
        success=False,
        steps=(
            DiagnosticStepDTO("Puerto escuchando", True, None),
            DiagnosticStepDTO("FastAPI respondiendo (/health)", False, "No se pudo conectar."),
        ),
    )

    view._on_diagnostic_result(result)

    assert view._diagnostics_list.count() == 2
    assert "✓" in view._diagnostics_list.item(0).text()
    assert "✗" in view._diagnostics_list.item(1).text()
