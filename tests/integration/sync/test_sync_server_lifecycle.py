"""Pruebas de integración del ciclo de vida real de `SyncServer` en el
mismo proceso (a diferencia de `test_sync_transport_e2e.py`, que verifica
el protocolo entre dos procesos/bases de datos separadas, necesario para
probar dos estaciones reales) — acá se prueba, contra un servidor
Uvicorn/FastAPI real bindeado a un puerto real:

- que `start()` confirma de verdad que quedó escuchando (no fire-and-forget);
- que detecta un puerto ocupado y lo reporta con un error claro;
- que la estación local queda `ONLINE`/`OFFLINE` según corresponda (el bug
  raíz de "Fuera de línea" para siempre);
- que "Probar servidor"/"Probar conexión WebSocket" funcionan contra un
  servidor real;
- que el registro de conexiones vivas refleja un handshake real (IP,
  versión, latencia reportada por el cliente)."""

from __future__ import annotations

import json
import socket
import time

import pytest
from websockets.sync.client import connect

from pos.modules.sync.domain.enums import SyncStationStatus
from pos.modules.sync.infrastructure.ws_client import probe_websocket
from pos.modules.sync.server.runner import SyncServer, SyncServerStartError
from tests.integration.sync.conftest import SyncFixtures


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _make_server(sync_env: SyncFixtures) -> SyncServer:
    sync_env.service.set_server_port(_free_port())
    return SyncServer(
        sync_env.service,
        auth_service=sync_env.auth_service,
        product_service=sync_env.product_service,
        category_service=sync_env.category_service,
        sales_service=sync_env.sales_service,
        inventory_service=sync_env.inventory_service,
        cash_register_service=sync_env.cash_register_service,
        kitchen_service=sync_env.kitchen_service,
        customer_service=sync_env.customer_service,
        user_service=sync_env.user_service,
        restaurant_service=sync_env.restaurant_service,
        qr_payment_service=sync_env.qr_payment_service,
        nequi_payment_service=sync_env.nequi_payment_service,
        breb_payment_service=sync_env.breb_payment_service,
        host="127.0.0.1",
    )


def test_start_confirms_real_listening_and_marks_local_station_online(
    sync_env: SyncFixtures,
) -> None:
    server = _make_server(sync_env)

    server.start()
    try:
        assert server.is_running is True
        local = sync_env.service.get_local_station()
        assert local is not None
        assert local.status is SyncStationStatus.ONLINE
    finally:
        server.stop()

    assert server.is_running is False
    offline = sync_env.service.get_local_station()
    assert offline is not None
    assert offline.status is SyncStationStatus.OFFLINE


def test_start_raises_a_clear_error_when_the_port_is_already_in_use(
    sync_env: SyncFixtures,
) -> None:
    port = _free_port()
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("0.0.0.0", port))
    blocker.listen(1)
    try:
        sync_env.service.set_server_port(port)
        server = SyncServer(
            sync_env.service,
            auth_service=sync_env.auth_service,
            product_service=sync_env.product_service,
            category_service=sync_env.category_service,
            sales_service=sync_env.sales_service,
            inventory_service=sync_env.inventory_service,
            cash_register_service=sync_env.cash_register_service,
            kitchen_service=sync_env.kitchen_service,
            customer_service=sync_env.customer_service,
            user_service=sync_env.user_service,
            restaurant_service=sync_env.restaurant_service,
            qr_payment_service=sync_env.qr_payment_service,
            nequi_payment_service=sync_env.nequi_payment_service,
            breb_payment_service=sync_env.breb_payment_service,
            host="127.0.0.1",
        )

        with pytest.raises(SyncServerStartError, match="en uso"):
            server.start()

        assert server.is_running is False
    finally:
        blocker.close()


def test_probe_reports_success_against_a_real_running_server(sync_env: SyncFixtures) -> None:
    server = _make_server(sync_env)
    server.start()
    try:
        result = server.probe()
    finally:
        server.stop()

    assert result.success is True
    assert all(step.passed for step in result.steps)
    assert len(result.steps) == 4


def test_probe_websocket_measures_a_real_round_trip(sync_env: SyncFixtures) -> None:
    server = _make_server(sync_env)
    server.start()
    try:
        url = f"ws://127.0.0.1:{sync_env.service.get_server_port()}/ws/sync"
        result = probe_websocket(url)
    finally:
        server.stop()

    assert result.success is True
    assert result.latency_ms is not None
    assert result.latency_ms >= 0


def test_probe_websocket_does_not_register_a_fake_station(sync_env: SyncFixtures) -> None:
    """El nombre reservado `__probe__` (ver `server/app.py`) nunca debe
    ensuciar el catálogo de estaciones conocidas."""
    server = _make_server(sync_env)
    server.start()
    try:
        url = f"ws://127.0.0.1:{sync_env.service.get_server_port()}/ws/sync"
        result = probe_websocket(url)
        assert result.success is True
        names = [s.name for s in sync_env.service.list_stations()]
    finally:
        server.stop()

    assert "__probe__" not in names


def test_connection_registry_reflects_a_real_client_handshake(sync_env: SyncFixtures) -> None:
    server = _make_server(sync_env)
    server.start()
    try:
        url = f"ws://127.0.0.1:{sync_env.service.get_server_port()}/ws/sync"
        with connect(url, open_timeout=5) as websocket:
            websocket.send(
                json.dumps(
                    {"type": "hello", "station_name": "Cliente E2E", "app_version": "9.9.9"}
                )
            )
            websocket.recv()

            connections = server.list_connections()
            assert len(connections) == 1
            assert connections[0].station_name == "Cliente E2E"
            assert connections[0].app_version == "9.9.9"
            assert connections[0].ip == "127.0.0.1"
            assert connections[0].latency_ms is None

            websocket.send(json.dumps({"type": "push", "entries": [], "latency_ms": 42.5}))
            websocket.recv()

            connections = server.list_connections()
            assert connections[0].latency_ms == 42.5

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and server.list_connections():
            time.sleep(0.05)
        assert server.list_connections() == []
    finally:
        server.stop()
