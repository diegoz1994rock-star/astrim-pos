"""Servidor de sincronización embebido: FastAPI + un único endpoint WebSocket.

Protocolo, siempre iniciado por el cliente (el servidor nunca empuja datos
por su cuenta — ver el docstring de `SyncService` sobre el alcance de esta
versión, "casi tiempo real" vía sondeo, no push instantáneo):

1. Cliente conecta y envía ``{"type": "hello", "station_name": str,
   "app_version": str opcional}``.
2. Servidor responde ``{"type": "hello_ack", "station_id": int}`` y marca la
   estación como en línea. También registra la conexión viva (IP/puerto/
   versión, ver `connection_registry.py`) para la tabla "Clientes
   conectados" del panel.
3. En bucle, mientras dure la conexión:
   - Cliente envía ``{"type": "pull", "since": "<iso8601>"}``; servidor
     responde ``{"type": "backlog", "entries": [...]}`` con todo lo
     ocurrido después de `since` que no se originó en el propio cliente.
   - Cliente envía ``{"type": "push", "entries": [...], "latency_ms":
     float opcional}`` con sus eventos locales nuevos y la latencia que él
     mismo midió en su último round-trip; servidor los aplica de forma
     idempotente, actualiza el registro de conexión y responde
     ``{"type": "push_ack", "count": int}``.
4. Al desconectar, el servidor marca la estación como fuera de línea y
   quita la conexión del registro en memoria.

Cada conexión/desconexión/error se registra también en `SyncEventLog`
(consola de eventos del panel) — nunca en silencio.

Esta misma app también monta, bajo `/api/v1`, la API HTTP de negocio para
clientes remotos (Android/tablet — ver `api/router.py`) — mismo puerto,
mismo proceso, protegida por `api/middleware.py::AuthMiddleware`."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from pos.modules.auth.application.authentication_service import AuthenticationService
from pos.modules.bre_b_payments.application.breb_payment_service import BreBPaymentService
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.kitchen.application.kitchen_service import KitchenService
from pos.modules.nequi_payments.application.nequi_payment_service import NequiPaymentService
from pos.modules.products.application.category_service import CategoryManagementService
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.qr_payments.application.qr_payment_service import QrPaymentService
from pos.modules.restaurant.application.restaurant_service import RestaurantService
from pos.modules.sales.application.sale_service import SalesService
from pos.modules.sync.application.audit_formatter import format_audit_entry
from pos.modules.sync.application.dto import SyncLogEntryDTO
from pos.modules.sync.application.sync_service import SyncService
from pos.modules.sync.domain.enums import SyncLogStatus
from pos.modules.sync.server.api.errors import install_domain_error_handler
from pos.modules.sync.server.api.middleware import AuthMiddleware
from pos.modules.sync.server.api.router import create_api_router
from pos.modules.sync.server.connection_registry import ConnectionRegistry
from pos.modules.sync.server.event_log import SyncEventLog
from pos.modules.users.application.user_management_service import UserManagementService

logger = logging.getLogger(__name__)

PROBE_STATION_NAME = "__probe__"
"""Nombre reservado que usa `ws_client.py::probe_websocket` para el
diagnóstico "Probar servidor"/"Probar conexión WebSocket" — una conexión
con este nombre nunca se registra como estación ni aparece en "Clientes
conectados": es solo un ping de un solo uso, no debe ensuciar el catálogo
de estaciones conocidas con una fila falsa."""


def _entry_to_wire(entry: Any) -> dict[str, Any]:
    return {
        "event_type": entry.event_type,
        "entity_type": entry.entity_type,
        "entity_uuid": entry.entity_uuid,
        "payload_json": entry.payload_json,
        "origin_station_name": entry.origin_station_name,
        "created_at": entry.created_at.isoformat(),
    }


def _describe_wire_entry(wire_entry: dict[str, Any], *, origin_station_name: str) -> str:
    """Reutiliza el mismo formateador legible de Auditoría (ver
    `application/audit_formatter.py`) para que la consola de eventos
    muestre "Venta #123 completada" en vez de un genérico "evento
    recibido" — nunca un mensaje sin sentido para el usuario."""
    temp_entry = SyncLogEntryDTO(
        id=0,
        event_type=wire_entry["event_type"],
        entity_type=wire_entry["entity_type"],
        entity_uuid=wire_entry["entity_uuid"],
        payload_json=wire_entry["payload_json"],
        status=SyncLogStatus.APPLIED,
        origin_station_name=origin_station_name,
        created_at=datetime.fromisoformat(wire_entry["created_at"]),
        applied_at=None,
    )
    return format_audit_entry(temp_entry)


def create_sync_app(
    sync_service: SyncService,
    event_log: SyncEventLog,
    registry: ConnectionRegistry,
    auth_service: AuthenticationService,
    product_service: ProductManagementService,
    category_service: CategoryManagementService,
    sales_service: SalesService,
    inventory_service: InventoryService,
    cash_register_service: CashRegisterService,
    kitchen_service: KitchenService,
    customer_service: CustomerManagementService,
    user_service: UserManagementService,
    restaurant_service: RestaurantService,
    qr_payment_service: QrPaymentService,
    nequi_payment_service: NequiPaymentService,
    breb_payment_service: BreBPaymentService,
) -> FastAPI:
    app = FastAPI(
        title="ASTRIM POS API",
        description=(
            "API HTTP de negocio del sistema POS — pensada para clientes "
            "remotos (Android, tablet, futuras apps de escritorio). Ver "
            "API.md en la raíz del repositorio para la referencia completa."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    install_domain_error_handler(app)
    app.add_middleware(AuthMiddleware, auth_service=auth_service)
    app.include_router(
        create_api_router(
            auth_service,
            product_service,
            category_service,
            sales_service,
            inventory_service,
            cash_register_service,
            kitchen_service,
            customer_service,
            user_service,
            restaurant_service,
            qr_payment_service,
            nequi_payment_service,
            breb_payment_service,
        )
    )

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
            is_probe = station_name == PROBE_STATION_NAME

            if is_probe:
                await websocket.send_text(json.dumps({"type": "hello_ack", "station_id": 0}))
                return

            app_version = hello.get("app_version")
            client_address = websocket.client
            client_ip = client_address.host if client_address is not None else "?"
            client_port = client_address.port if client_address is not None else 0

            station = await asyncio.to_thread(sync_service.register_peer_station, station_name)
            registry.register(
                station_name=station_name, ip=client_ip, port=client_port, app_version=app_version
            )
            event_log.log(f"Cliente conectado: {station_name} ({client_ip})")
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
                    registry.touch(station_name)
                    await websocket.send_text(
                        json.dumps({"type": "backlog", "entries": wire_entries})
                    )
                elif message_type == "push":
                    wire_entries = message.get("entries", [])
                    for wire_entry in wire_entries:
                        await asyncio.to_thread(
                            sync_service.record_remote_event,
                            event_type=wire_entry["event_type"],
                            entity_type=wire_entry["entity_type"],
                            entity_uuid=wire_entry["entity_uuid"],
                            payload_json=wire_entry["payload_json"],
                            origin_station_name=wire_entry["origin_station_name"],
                            created_at=datetime.fromisoformat(wire_entry["created_at"]),
                        )
                        event_log.log(
                            f"{_describe_wire_entry(wire_entry, origin_station_name=station_name)} "
                            f"(recibido de {station_name})"
                        )
                    latency_ms = message.get("latency_ms")
                    if isinstance(latency_ms, int | float):
                        registry.update_latency(station_name, float(latency_ms))
                    else:
                        registry.touch(station_name)
                    await websocket.send_text(
                        json.dumps({"type": "push_ack", "count": len(wire_entries)})
                    )
                else:
                    logger.warning("Mensaje de sincronización desconocido: %r", message_type)
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.exception("Error en la conexión de sincronización con %r", station_name)
            if station_name != PROBE_STATION_NAME:
                event_log.log(f"Error de sincronización con {station_name or '?'}: {exc}")
        finally:
            if station_name is not None and station_name != PROBE_STATION_NAME:
                await asyncio.to_thread(sync_service.mark_station_offline, station_name)
                registry.unregister(station_name)
                event_log.log(f"Cliente desconectado: {station_name}")

    return app
