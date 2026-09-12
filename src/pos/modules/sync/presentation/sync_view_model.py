"""View model del panel de Sincronización — centro de administración real
del transporte (servidor/cliente WebSocket), no solo un formulario de
configuración: cada acción (iniciar/detener/reiniciar/sincronizar/probar)
llama al método real correspondiente de `SyncTransport`/`SyncServer`/
`SyncClient` y refleja su resultado real, nunca un estado simulado."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from pos.modules.sync.application.sync_transport import SyncTransport
from pos.modules.sync.domain.enums import SyncMode
from pos.modules.sync.infrastructure.ws_client import probe_websocket
from pos.modules.sync.server.runner import SyncServerStartError

_STATUS_REFRESH_MS = 2000


class SyncViewModel(QObject):
    status_changed = Signal(object)
    """Emite `SyncStatusDTO`."""
    stations_loaded = Signal(list)
    history_loaded = Signal(list)
    connections_loaded = Signal(list)
    """Emite `list[SyncConnectionDTO]` — "Clientes conectados"."""
    events_loaded = Signal(list)
    """Emite `list[SyncEventLogLineDTO]` — consola de eventos."""
    diagnostic_result = Signal(object)
    """Emite `ServerProbeResultDTO` o `WebSocketProbeResultDTO` al terminar
    "Probar servidor"/"Probar conexión WebSocket"."""
    error_occurred = Signal(str)
    info_occurred = Signal(str)

    def __init__(self, transport: SyncTransport, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._transport = transport
        self._sync_service = transport.sync_service
        self._timer = QTimer(self)
        self._timer.setInterval(_STATUS_REFRESH_MS)
        self._timer.timeout.connect(self._refresh)

    def start_refreshing(self) -> None:
        """Comienza a refrescar el estado periódicamente mientras el panel
        está visible. El transporte en sí (servidor/cliente) ya se arrancó
        al iniciar la app (`main.py`) si el modo configurado y la opción
        de inicio automático lo requieren — este método no lo vuelve a
        arrancar."""
        self._refresh()
        self._timer.start()

    def stop_refreshing(self) -> None:
        self._timer.stop()

    def refresh_now(self) -> None:
        self._refresh()

    # -- Configuración ---------------------------------------------------

    def set_mode(self, mode: SyncMode) -> None:
        self._sync_service.set_mode(mode)
        try:
            self._transport.apply_mode(mode)
        except SyncServerStartError as error:
            self.error_occurred.emit(f"No se pudo aplicar el modo '{mode.value}': {error}")
        else:
            self.info_occurred.emit(f"Modo de sincronización: {mode.value}.")
        self._refresh()

    def set_local_station_name(self, name: str) -> None:
        if not name.strip():
            self.error_occurred.emit("El nombre de la estación no puede estar vacío.")
            return
        self._sync_service.set_local_station_name(name.strip())
        self._refresh()

    def set_peer_url(self, url: str) -> None:
        self._sync_service.set_peer_url(url.strip())
        self._refresh()

    def set_server_port(self, port: int) -> None:
        self._sync_service.set_server_port(port)
        if self._transport.server.is_running:
            try:
                self._transport.apply_mode(SyncMode.PRIMARY)
            except SyncServerStartError as error:
                self.error_occurred.emit(
                    f"No se pudo reiniciar el servidor en el puerto {port}: {error}"
                )
        self._refresh()

    def set_auto_start(self, enabled: bool) -> None:
        self._sync_service.set_auto_start_enabled(enabled)
        self._refresh()

    # -- Control del servidor ---------------------------------------------

    def start_server(self) -> None:
        if self._sync_service.get_mode() is not SyncMode.PRIMARY:
            self.info_occurred.emit(
                "El modo actual no es 'Servidor principal'. Cambia el modo para iniciar el "
                "servidor en esta estación."
            )
            return
        if self._transport.server.is_running:
            self.info_occurred.emit("El servidor ya está en línea.")
            return
        try:
            self._transport.server.start()
        except SyncServerStartError as error:
            self.error_occurred.emit(f"No fue posible iniciar el servidor: {error}")
        else:
            self.info_occurred.emit("Servidor iniciado correctamente.")
        self._refresh()

    def stop_server(self) -> None:
        if not self._transport.server.is_running:
            self.info_occurred.emit("El servidor no está corriendo.")
            return
        self._transport.server.stop()
        self.info_occurred.emit("Servidor detenido.")
        self._refresh()

    def restart_server(self) -> None:
        if self._sync_service.get_mode() is not SyncMode.PRIMARY:
            self.info_occurred.emit(
                "El modo actual no es 'Servidor principal'. Cambia el modo para reiniciar el "
                "servidor en esta estación."
            )
            return
        try:
            self._transport.restart()
        except SyncServerStartError as error:
            self.error_occurred.emit(f"No fue posible reiniciar el servidor: {error}")
        else:
            self.info_occurred.emit("Servidor reiniciado correctamente.")
        self._refresh()

    def sync_now(self) -> None:
        mode = self._sync_service.get_mode()
        if mode is SyncMode.CLIENT:
            if not self._transport.client.is_connected:
                self.info_occurred.emit("No hay conexión activa con el servidor principal todavía.")
                return
            self._transport.client.sync_now()
            self.info_occurred.emit("Sincronización solicitada.")
        elif mode is SyncMode.PRIMARY:
            self.info_occurred.emit(
                "Esta estación es el servidor: son los clientes los que inician cada "
                "sincronización, no hay nada que forzar desde aquí."
            )
        else:
            self.info_occurred.emit("La sincronización está deshabilitada para esta estación.")
        self._refresh()

    # -- Diagnóstico --------------------------------------------------------

    def test_server(self) -> None:
        result = self._transport.server.probe()
        self.diagnostic_result.emit(result)
        if result.success:
            self.info_occurred.emit("Servidor funcionando correctamente.")
        else:
            failed_step = next((s for s in result.steps if not s.passed), None)
            detail = f": {failed_step.detail}" if failed_step and failed_step.detail else ""
            self.error_occurred.emit(f"Falló '{failed_step.label if failed_step else '?'}'{detail}")

    def test_websocket(self) -> None:
        url = self._sync_service.get_peer_url() or self._transport.websocket_url
        result = probe_websocket(url)
        self.diagnostic_result.emit(result)
        if result.success:
            self.info_occurred.emit(result.detail)
        else:
            self.error_occurred.emit(result.detail)

    # -- Refresco periódico ---------------------------------------------------

    def _refresh(self) -> None:
        status = self._sync_service.get_status(
            running=self._transport.server.is_running,
            connected=self._transport.client.is_connected,
            local_ip=self._transport.local_ip,
            websocket_url=self._transport.websocket_url,
            uptime_seconds=self._transport.uptime_seconds,
            last_error=self._transport.last_error,
            connections_count=len(self._transport.list_connections()),
        )
        self.status_changed.emit(status)
        self.stations_loaded.emit(self._sync_service.list_stations())
        self.history_loaded.emit(self._sync_service.list_recent())
        self.connections_loaded.emit(self._transport.list_connections())
        self.events_loaded.emit(self._transport.list_recent_events())
