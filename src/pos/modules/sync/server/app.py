"""Servidor de sincronización embebido: FastAPI + un único endpoint WebSocket.

Protocolo, siempre iniciado por el cliente (el servidor nunca empuja datos
por su cuenta — ver el docstring de `SyncService` sobre el alcance de esta
versión, "casi tiempo real" vía sondeo, no push instantáneo):

1. Cliente conecta y envía ``{"type": "hello", "station_name": str}``.
2. Servidor responde ``{"type": "hello_ack", "station_id": int}`` y marca la
   estación como en línea.
3. En bucle, mientras dure la conexión:
   - Cliente envía ``{"type": "pull", "since": "<iso8601>"}``; servidor
     responde ``{"type": "backlog", "entries": [...]}`` con todo lo
     ocurrido después de `since` que no se originó en el propio cliente.
   - Cliente envía ``{"type": "push", "entries": [...]}`` con sus eventos
     locales nuevos; servidor los aplica de forma idempotente y responde
     ``{"type": "push_ack", "count": int}``.
4. Al desconectar, el servidor marca la estación como fuera de línea.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from pos.modules.sync.application.sync_service import SyncService

logger = logging.getLogger(__name__)


def _entry_to_wire(entry: Any) -> dict[str, Any]:
    return {
        "event_type": entry.event_type,
        "entity_type": entry.entity_type,
        "entity_uuid": entry.entity_uuid,
        "payload_json": entry.payload_json,
        "origin_station_name": entry.origin_station_name,
        "created_at": entry.created_at.isoformat(),
    }


def create_sync_app(sync_service: SyncService) -> FastAPI:
    app = FastAPI(title="POS Sync Server", docs_url=None, redoc_url=None)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.websocket("/ws/sync")
    async def ws_sync(websocket: WebSocket) -> None:
        await websocket.accept()
        station_name: str | None = None
        try:
            hello_raw = await websocket.receive_text()
            hello = json.loads(hello_raw)
            if hello.get("type") != "hello":
                await websocket.close(code=4000, reason="Se esperaba un mensaje 'hello'.")
                return
            station_name = str(hello["station_name"])
            station = await asyncio.to_thread(sync_service.register_peer_station, station_name)
            await websocket.send_text(json.dumps({"type": "hello_ack", "station_id": station.id}))

            while True:
                raw = await websocket.receive_text()
                message = json.loads(raw)
                message_type = message.get("type")

                if message_type == "pull":
                    since = datetime.fromisoformat(message["since"])
                    entries = await asyncio.to_thread(
                        sync_service.list_since_excluding_station,
                        since=since,
                        excluded_station_name=station_name,
                    )
                    wire_entries = [_entry_to_wire(e) for e in entries]
                    await websocket.send_text(
                        json.dumps({"type": "backlog", "entries": wire_entries})
                    )
                elif message_type == "push":
                    for wire_entry in message.get("entries", []):
                        await asyncio.to_thread(
                            sync_service.record_remote_event,
                            event_type=wire_entry["event_type"],
                            entity_type=wire_entry["entity_type"],
                            entity_uuid=wire_entry["entity_uuid"],
                            payload_json=wire_entry["payload_json"],
                            origin_station_name=wire_entry["origin_station_name"],
                            created_at=datetime.fromisoformat(wire_entry["created_at"]),
                        )
                    await websocket.send_text(
                        json.dumps({"type": "push_ack", "count": len(message.get("entries", []))})
                    )
                else:
                    logger.warning("Mensaje de sincronización desconocido: %r", message_type)
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception("Error en la conexión de sincronización con %r", station_name)
        finally:
            if station_name is not None:
                await asyncio.to_thread(sync_service.mark_station_offline, station_name)

    return app
