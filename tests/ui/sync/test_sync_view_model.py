"""Pruebas de `SyncViewModel` con `SyncTransport` simulado (`Mock`)."""

from __future__ import annotations

from unittest.mock import Mock

from pytestqt.qtbot import QtBot

from pos.modules.sync.application.dto import (
    DiagnosticStepDTO,
    ServerProbeResultDTO,
    SyncStatusDTO,
    WebSocketProbeResultDTO,
)
from pos.modules.sync.domain.enums import SyncMode
from pos.modules.sync.presentation import sync_view_model as sync_view_model_module
from pos.modules.sync.presentation.sync_view_model import SyncViewModel
from pos.modules.sync.server.runner import SyncServerStartError


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
        uptime_seconds=12.0,
        last_error=None,
        sent_count=0,
        received_count=0,
        failed_count=0,
        connections_count=0,
        auto_start_enabled=True,
    )
    defaults.update(overrides)
    return SyncStatusDTO(**defaults)


def _make_view_model() -> tuple[SyncViewModel, Mock]:
    transport = Mock()
    transport.sync_service.get_status.return_value = _status()
    transport.sync_service.get_mode.return_value = SyncMode.PRIMARY
    transport.sync_service.list_stations.return_value = []
    transport.sync_service.list_recent.return_value = []
    transport.local_ip = "192.168.1.50"
    transport.websocket_url = "ws://192.168.1.50:8765/ws/sync"
    transport.uptime_seconds = 12.0
    transport.last_error = None
    transport.list_connections.return_value = []
    transport.list_recent_events.return_value = []
    transport.server.is_running = False
    transport.client.is_connected = False
    view_model = SyncViewModel(transport)
    return view_model, transport


def test_refresh_emits_status_and_lists(qtbot: QtBot) -> None:
    view_model, transport = _make_view_model()
    statuses = []
    view_model.status_changed.connect(statuses.append)

    view_model.refresh_now()

    transport.sync_service.get_status.assert_called_once_with(
        running=False,
        connected=False,
        local_ip="192.168.1.50",
        websocket_url="ws://192.168.1.50:8765/ws/sync",
        uptime_seconds=12.0,
        last_error=None,
        connections_count=0,
    )
    assert len(statuses) == 1


def test_start_server_starts_when_mode_is_primary(qtbot: QtBot) -> None:
    view_model, transport = _make_view_model()
    transport.sync_service.get_mode.return_value = SyncMode.PRIMARY
    transport.server.is_running = False
    infos = []
    view_model.info_occurred.connect(infos.append)

    view_model.start_server()

    transport.server.start.assert_called_once()
    assert infos == ["Servidor iniciado correctamente."]


def test_start_server_does_nothing_when_mode_is_not_primary(qtbot: QtBot) -> None:
    view_model, transport = _make_view_model()
    transport.sync_service.get_mode.return_value = SyncMode.CLIENT
    infos = []
    view_model.info_occurred.connect(infos.append)

    view_model.start_server()

    transport.server.start.assert_not_called()
    assert len(infos) == 1


def test_start_server_reports_start_error(qtbot: QtBot) -> None:
    view_model, transport = _make_view_model()
    transport.sync_service.get_mode.return_value = SyncMode.PRIMARY
    transport.server.is_running = False
    transport.server.start.side_effect = SyncServerStartError("El puerto 8765 ya está en uso.")
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.start_server()

    assert errors == ["No fue posible iniciar el servidor: El puerto 8765 ya está en uso."]


def test_stop_server_stops_when_running(qtbot: QtBot) -> None:
    view_model, transport = _make_view_model()
    transport.server.is_running = True

    view_model.stop_server()

    transport.server.stop.assert_called_once()


def test_stop_server_does_nothing_when_not_running(qtbot: QtBot) -> None:
    view_model, transport = _make_view_model()
    transport.server.is_running = False

    view_model.stop_server()

    transport.server.stop.assert_not_called()


def test_sync_now_forces_a_cycle_when_client_connected(qtbot: QtBot) -> None:
    view_model, transport = _make_view_model()
    transport.sync_service.get_mode.return_value = SyncMode.CLIENT
    transport.client.is_connected = True

    view_model.sync_now()

    transport.client.sync_now.assert_called_once()


def test_sync_now_is_a_noop_message_when_primary(qtbot: QtBot) -> None:
    view_model, transport = _make_view_model()
    transport.sync_service.get_mode.return_value = SyncMode.PRIMARY
    infos = []
    view_model.info_occurred.connect(infos.append)

    view_model.sync_now()

    transport.client.sync_now.assert_not_called()
    assert len(infos) == 1


def test_test_server_emits_diagnostic_result_and_success_message(qtbot: QtBot) -> None:
    view_model, transport = _make_view_model()
    result = ServerProbeResultDTO(
        success=True, steps=(DiagnosticStepDTO("Puerto escuchando", True, None),)
    )
    transport.server.probe.return_value = result
    results = []
    infos = []
    view_model.diagnostic_result.connect(results.append)
    view_model.info_occurred.connect(infos.append)

    view_model.test_server()

    assert results == [result]
    assert infos == ["Servidor funcionando correctamente."]


def test_test_server_emits_error_with_failed_step(qtbot: QtBot) -> None:
    view_model, transport = _make_view_model()
    result = ServerProbeResultDTO(
        success=False,
        steps=(DiagnosticStepDTO("Puerto escuchando", False, "El puerto 8765 no responde."),),
    )
    transport.server.probe.return_value = result
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.test_server()

    assert errors == ["Falló 'Puerto escuchando': El puerto 8765 no responde."]


def test_test_websocket_emits_diagnostic_result_using_peer_url(qtbot: QtBot, monkeypatch) -> None:
    view_model, transport = _make_view_model()
    transport.sync_service.get_peer_url.return_value = "ws://192.168.1.10:8765/ws/sync"
    result = WebSocketProbeResultDTO(success=True, detail="El WebSocket respondió.", latency_ms=8.0)
    captured_urls: list[str] = []

    def fake_probe_websocket(url: str) -> WebSocketProbeResultDTO:
        captured_urls.append(url)
        return result

    monkeypatch.setattr(sync_view_model_module, "probe_websocket", fake_probe_websocket)
    results = []
    view_model.diagnostic_result.connect(results.append)

    view_model.test_websocket()

    assert captured_urls == ["ws://192.168.1.10:8765/ws/sync"]
    assert results == [result]


def test_set_auto_start_persists_the_setting(qtbot: QtBot) -> None:
    view_model, transport = _make_view_model()

    view_model.set_auto_start(False)

    transport.sync_service.set_auto_start_enabled.assert_called_once_with(False)
