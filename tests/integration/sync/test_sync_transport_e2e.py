"""Prueba de extremo a extremo del transporte de sincronización: un
servidor real (FastAPI + WebSocket, sin mocks) corriendo en un **proceso
de Python separado** contra su propia base de datos SQLite, y un cliente
que le habla por el protocolo real de pull/push definido en
`sync/server/app.py`. Ver el docstring de `_server_process.py` sobre por
qué hace falta un subproceso en vez de dos fixtures en el mismo proceso.
"""

from __future__ import annotations

import contextlib
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
from websockets.sync.client import connect

_HELPER_SCRIPT = Path(__file__).parent / "_server_process.py"
_SRC_DIR = Path(__file__).resolve().parents[3] / "src"
_EPOCH = "1970-01-01T00:00:00+00:00"
_TERMINATED_OK_CODES = (0, None, 1) if sys.platform == "win32" else (0, None, -15)
"""Códigos de salida esperados tras `process.terminate()` — nunca indican
un crash real, solo cómo el SO reporta "lo matamos nosotros": en POSIX,
un proceso no manejado que recibe SIGTERM sale con -15; en Windows,
`TerminateProcess` (lo que `Popen.terminate()` usa ahí) siempre reporta 1,
nunca -15 (esa señal ni existe en Windows) — sin esto, cada prueba fallaba
acá aunque el servidor real hubiera arrancado y respondido bien."""


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_health(port: int, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"http://127.0.0.1:{port}/health", timeout=0.5)
            if response.status_code == 200:
                return
        except httpx.HTTPError as error:
            last_error = error
        time.sleep(0.1)
    raise TimeoutError(f"El servidor de sincronización no respondió a tiempo: {last_error}")


@contextlib.contextmanager
def _run_server_station(db_path: Path, station_name: str, *, seed_event: bool):
    port = _free_port()
    args = [
        sys.executable,
        str(_HELPER_SCRIPT),
        "--db-path",
        str(db_path),
        "--station-name",
        station_name,
        "--port",
        str(port),
    ]
    if seed_event:
        args.append("--seed-event")
    process = subprocess.Popen(
        args,
        env={**os.environ, "PYTHONPATH": str(_SRC_DIR)},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for_health(port)
        yield port
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        if process.returncode not in _TERMINATED_OK_CODES:
            output = process.stdout.read() if process.stdout else ""
            raise AssertionError(f"El proceso servidor falló: {output}")


def _dump_log(db_path: Path, station_name: str) -> list[dict]:
    result = subprocess.run(
        [
            sys.executable,
            str(_HELPER_SCRIPT),
            "--db-path",
            str(db_path),
            "--station-name",
            station_name,
            "--dump",
        ],
        env={**os.environ, "PYTHONPATH": str(_SRC_DIR)},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_client_pulls_backlog_seeded_by_remote_server(tmp_path: Path) -> None:
    server_db = tmp_path / "server.db"

    with (
        _run_server_station(server_db, "Estación Servidor", seed_event=True) as port,
        connect(f"ws://127.0.0.1:{port}/ws/sync", open_timeout=5) as websocket,
    ):
        websocket.send(json.dumps({"type": "hello", "station_name": "Estación Cliente"}))
        hello_ack = json.loads(websocket.recv())
        assert hello_ack["type"] == "hello_ack"

        websocket.send(json.dumps({"type": "pull", "since": _EPOCH}))
        backlog = json.loads(websocket.recv())

    assert backlog["type"] == "backlog"
    assert len(backlog["entries"]) == 1
    entry = backlog["entries"][0]
    assert entry["event_type"] == "ProductCreatedEvent"
    assert entry["origin_station_name"] == "Estación Servidor"
    payload = json.loads(entry["payload_json"])
    assert payload["sku"] == "SKU-1"


def test_pull_excludes_events_originated_by_the_requesting_station(tmp_path: Path) -> None:
    server_db = tmp_path / "server.db"

    with (
        _run_server_station(server_db, "Estación Servidor", seed_event=True) as port,
        connect(f"ws://127.0.0.1:{port}/ws/sync", open_timeout=5) as websocket,
    ):
        websocket.send(json.dumps({"type": "hello", "station_name": "Estación Servidor"}))
        websocket.recv()
        websocket.send(json.dumps({"type": "pull", "since": _EPOCH}))
        backlog = json.loads(websocket.recv())

    assert backlog["entries"] == []


def test_push_from_client_is_persisted_on_the_server_station(tmp_path: Path) -> None:
    server_db = tmp_path / "server.db"
    pushed_uuid = str(uuid.uuid4())

    with (
        _run_server_station(server_db, "Estación Servidor", seed_event=False) as port,
        connect(f"ws://127.0.0.1:{port}/ws/sync", open_timeout=5) as websocket,
    ):
        websocket.send(json.dumps({"type": "hello", "station_name": "Estación Cliente"}))
        websocket.recv()

        push_entry = {
            "event_type": "UserCreatedEvent",
            "entity_type": "users",
            "entity_uuid": pushed_uuid,
            "payload_json": json.dumps({"user_id": 1, "username": "cajero1"}),
            "origin_station_name": "Estación Cliente",
            "created_at": datetime.now(UTC).isoformat(),
        }
        websocket.send(json.dumps({"type": "push", "entries": [push_entry]}))
        ack = json.loads(websocket.recv())
        assert ack["type"] == "push_ack"
        assert ack["count"] == 1

    persisted = _dump_log(server_db, "Estación Servidor")
    assert len(persisted) == 1
    assert persisted[0]["entity_uuid"] == pushed_uuid
    assert persisted[0]["status"] == "applied"


def test_push_is_idempotent_across_separate_connections(tmp_path: Path) -> None:
    server_db = tmp_path / "server.db"
    pushed_uuid = str(uuid.uuid4())
    push_entry = {
        "event_type": "UserCreatedEvent",
        "entity_type": "users",
        "entity_uuid": pushed_uuid,
        "payload_json": "{}",
        "origin_station_name": "Estación Cliente",
        "created_at": datetime.now(UTC).isoformat(),
    }

    with _run_server_station(server_db, "Estación Servidor", seed_event=False) as port:
        for _ in range(2):
            with connect(f"ws://127.0.0.1:{port}/ws/sync", open_timeout=5) as websocket:
                websocket.send(json.dumps({"type": "hello", "station_name": "Estación Cliente"}))
                websocket.recv()
                websocket.send(json.dumps({"type": "push", "entries": [push_entry]}))
                websocket.recv()

    persisted = _dump_log(server_db, "Estación Servidor")
    assert len(persisted) == 1
