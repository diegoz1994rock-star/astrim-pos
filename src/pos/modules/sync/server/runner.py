"""Arranca/detiene el servidor de sincronización embebido en un hilo aparte.

La app de escritorio (PySide6) tiene su propio bucle de eventos (Qt) en el
hilo principal; `uvicorn.Server.run()` es bloqueante y necesita su propio
bucle asyncio, así que corre en un hilo daemon dedicado — mismo patrón que
`BackupScheduler` (APScheduler) para el módulo de Backups.

`start()` nunca es "fire-and-forget": espera (con timeout acotado) una
confirmación real de que Uvicorn quedó escuchando (`uvicorn.Server.started`,
puesto en `True` por el propio arranque interno de Uvicorn) antes de
devolver el control, y captura cualquier excepción de arranque (puerto
ocupado, error de bind) para reportarla — nunca la deja morir en silencio
dentro del hilo daemon."""

from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.request

import uvicorn

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
from pos.modules.sync.application.dto import DiagnosticStepDTO, ServerProbeResultDTO
from pos.modules.sync.application.sync_service import SyncService
from pos.modules.sync.domain.enums import SyncStationStatus
from pos.modules.sync.infrastructure.local_network import get_local_ip
from pos.modules.sync.infrastructure.ws_client import probe_websocket
from pos.modules.sync.server.app import create_sync_app
from pos.modules.sync.server.connection_registry import ConnectionRegistry
from pos.modules.sync.server.event_log import SyncEventLog
from pos.modules.users.application.user_management_service import UserManagementService

_START_TIMEOUT_SECONDS = 10.0
"""El primer arranque de Uvicorn en un proceso puede tardar bastante más
que los siguientes (importa FastAPI/h11/httptools la primera vez) — la
espera no cuesta nada en el caso normal (el bucle vuelve apenas
`server.started` se pone en `True`), así que el margen extra solo importa
para ese primer arranque frío o para un fallo real."""
_START_POLL_INTERVAL_SECONDS = 0.05
_PROBE_HOST = "127.0.0.1"
"""Host usado para autodiagnosticarse (`probe()`) — siempre loopback, sin
importar en qué interfaz escucha el servidor (`host="0.0.0.0"` no es una
dirección de destino válida), para que el chequeo no dependa de la
configuración de red/firewall de la LAN."""


class SyncServerStartError(Exception):
    """El servidor no pudo confirmar que quedó escuchando (puerto ocupado,
    fallo de bind, excepción de arranque de Uvicorn, timeout) — ver
    `SyncServer.start()`, nunca se traga en silencio."""


def _check_port_available(port: int) -> str | None:
    """`None` si el puerto está libre; un mensaje de error si ya hay algo
    escuchando ahí — chequeo previo *no invasivo* (solo intenta conectar,
    nunca hace `bind`), para un diagnóstico honesto y rápido ("puerto
    ocupado") sin interferir con el bind real de Uvicorn justo después.

    Deliberadamente NO usa bind-y-cierre-inmediato: hacerlo demostró
    causar una carrera real (el puerto quedaba en un estado transitorio
    que hacía fallar el bind de Uvicorn momentos después, detectado por
    los tests end-to-end)."""
    try:
        with socket.create_connection((_PROBE_HOST, port), timeout=0.2):
            return f"El puerto {port} ya está en uso (otro proceso está escuchando ahí)."
    except OSError:
        return None


def _check_tcp_listening(port: int, *, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((_PROBE_HOST, port), timeout=timeout):
            return True
    except OSError:
        return False


def _check_http_health(port: int, *, timeout: float = 2.0) -> tuple[bool, str | None]:
    url = f"http://{_PROBE_HOST}:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
            body = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, f"No se pudo conectar a {url}: {exc}"
    if body.get("status") != "ok":
        return False, f"Respuesta inesperada de {url}: {body!r}"
    return True, None


class SyncServer:
    def __init__(
        self,
        sync_service: SyncService,
        *,
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
        host: str = "0.0.0.0",
        event_log: SyncEventLog | None = None,
        connection_registry: ConnectionRegistry | None = None,
    ) -> None:
        self._sync_service = sync_service
        self._auth_service = auth_service
        self._product_service = product_service
        self._category_service = category_service
        self._sales_service = sales_service
        self._inventory_service = inventory_service
        self._cash_register_service = cash_register_service
        self._kitchen_service = kitchen_service
        self._customer_service = customer_service
        self._user_service = user_service
        self._restaurant_service = restaurant_service
        self._qr_payment_service = qr_payment_service
        self._nequi_payment_service = nequi_payment_service
        self._breb_payment_service = breb_payment_service
        self._host = host
        self.event_log = event_log or SyncEventLog()
        self.connection_registry = connection_registry or ConnectionRegistry()
        self._thread: threading.Thread | None = None
        self._server: uvicorn.Server | None = None
        self._start_error: Exception | None = None
        self._started_at: float | None = None

    @property
    def is_running(self) -> bool:
        return (
            self._thread is not None
            and self._thread.is_alive()
            and self._server is not None
            and self._server.started
        )

    @property
    def port(self) -> int:
        return self._sync_service.get_server_port()

    @property
    def local_ip(self) -> str:
        return get_local_ip()

    @property
    def websocket_url(self) -> str:
        return f"ws://{self.local_ip}:{self.port}/ws/sync"

    @property
    def uptime_seconds(self) -> float | None:
        if not self.is_running or self._started_at is None:
            return None
        return time.monotonic() - self._started_at

    @property
    def last_start_error(self) -> str | None:
        return str(self._start_error) if self._start_error is not None else None

    def list_connections(self) -> list:
        return self.connection_registry.list_connections()

    @property
    def connections_count(self) -> int:
        return len(self.connection_registry)

    def start(self) -> None:
        """No-op si ya está corriendo (llamar dos veces es seguro). Lanza
        `SyncServerStartError` con el motivo real si no logra confirmar
        que quedó escuchando dentro de `_START_TIMEOUT_SECONDS`."""
        if self.is_running:
            return
        self._start_error = None
        port = self.port

        port_error = _check_port_available(port)
        if port_error is not None:
            self.event_log.log(f"No fue posible iniciar el servidor: {port_error}")
            raise SyncServerStartError(port_error)

        self.event_log.log(f"Iniciando servidor en el puerto {port}…")
        app = create_sync_app(
            self._sync_service,
            self.event_log,
            self.connection_registry,
            self._auth_service,
            self._product_service,
            self._category_service,
            self._sales_service,
            self._inventory_service,
            self._cash_register_service,
            self._kitchen_service,
            self._customer_service,
            self._user_service,
            self._restaurant_service,
            self._qr_payment_service,
            self._nequi_payment_service,
            self._breb_payment_service,
        )
        # `log_config=None`: por defecto Uvicorn llama a
        # `logging.config.dictConfig(...)` con su propio formatter
        # coloreado (`uvicorn.logging.DefaultFormatter`), que decide si usar
        # color llamando a `sys.stdout.isatty()` — en el `.exe` empaquetado
        # sin consola (`console=False` en `installer/pos.spec`) Windows deja
        # `sys.stdout`/`sys.stderr` en `None` (mismo comportamiento que
        # `pythonw.exe`, no una redirección a NUL), así que esa llamada
        # revienta con `AttributeError: 'NoneType' object has no attribute
        # 'isatty'`, que `dictConfig` reempaqueta como
        # `ValueError: Unable to configure formatter 'default'`. La app ya
        # tiene su propio logging centralizado (`pos.core.logging.config
        # .setup_logging`, aplicado una vez en `bootstrap_core`) que escribe
        # a archivo — dejar que Uvicorn reconfigure el logging global además
        # de eso siempre fue redundante para un servidor embebido en un
        # hilo; con `log_config=None` sus loggers (`uvicorn`, `uvicorn
        # .error`, `uvicorn.access`) simplemente propagan al logger raíz ya
        # configurado, sin tocar `sys.stdout`/`sys.stderr` para nada.
        config = uvicorn.Config(
            app, host=self._host, port=port, log_level="warning", log_config=None
        )
        server = uvicorn.Server(config)
        self._server = server

        def _run() -> None:
            try:
                server.run()
            except SystemExit:
                # Uvicorn reporta un fallo de bind con `sys.exit(...)`
                # internamente (ver `uvicorn.server.Server.startup`) en vez
                # de dejar propagar el `OSError` original — `SystemExit` no
                # hereda de `Exception`, así que hace falta capturarlo
                # aparte para no perder la señal de que el arranque falló.
                self._start_error = RuntimeError(
                    "Uvicorn no pudo iniciar (revisa que el puerto esté disponible)."
                )
            except Exception as exc:  # noqa: BLE001 - se reporta al hilo llamador, no se traga
                self._start_error = exc

        thread = threading.Thread(target=_run, daemon=True, name="sync-server")
        self._thread = thread
        thread.start()

        deadline = time.monotonic() + _START_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if server.started:
                self._started_at = time.monotonic()
                self.event_log.log(f"Servidor escuchando en {self.websocket_url}")
                self._sync_service.mark_local_station_online()
                return
            if not thread.is_alive():
                break
            time.sleep(_START_POLL_INTERVAL_SECONDS)

        error = self._start_error or RuntimeError("El servidor no confirmó su arranque a tiempo.")
        self.event_log.log(f"No fue posible iniciar el servidor: {error}")
        self._thread = None
        self._server = None
        raise SyncServerStartError(str(error))

    def stop(self) -> None:
        if self._server is None or self._thread is None:
            return
        self._server.should_exit = True
        self._thread.join(timeout=5)
        self._thread = None
        self._server = None
        self._started_at = None
        self.connection_registry.clear()
        self._sync_service.mark_local_station_offline()
        self.event_log.log("Servidor detenido")

    def probe(self) -> ServerProbeResultDTO:
        """"Probar servidor": corre en orden los mismos chequeos reales que
        un administrador haría a mano, deteniéndose en el primer paso que
        falla — nunca un genérico "algo salió mal"."""
        steps: list[DiagnosticStepDTO] = []
        port = self.port

        listening = _check_tcp_listening(port)
        steps.append(
            DiagnosticStepDTO(
                "Puerto escuchando",
                listening,
                None if listening else f"El puerto {port} no responde conexiones TCP.",
            )
        )
        if not listening:
            return ServerProbeResultDTO(False, tuple(steps))

        health_ok, health_detail = _check_http_health(port)
        steps.append(DiagnosticStepDTO("FastAPI respondiendo (/health)", health_ok, health_detail))
        if not health_ok:
            return ServerProbeResultDTO(False, tuple(steps))

        ws_result = probe_websocket(f"ws://{_PROBE_HOST}:{port}/ws/sync")
        steps.append(
            DiagnosticStepDTO(
                "WebSocket /ws/sync respondiendo", ws_result.success, ws_result.detail
            )
        )
        if not ws_result.success:
            return ServerProbeResultDTO(False, tuple(steps))

        local_station = self._sync_service.get_local_station()
        station_online = (
            local_station is not None and local_station.status is SyncStationStatus.ONLINE
        )
        offline_detail = "La fila de esta estación sigue marcada fuera de línea."
        steps.append(
            DiagnosticStepDTO(
                "Estación local registrada como en línea",
                station_online,
                None if station_online else offline_detail,
            )
        )

        return ServerProbeResultDTO(all(step.passed for step in steps), tuple(steps))
