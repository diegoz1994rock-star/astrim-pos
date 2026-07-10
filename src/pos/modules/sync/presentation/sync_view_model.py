"""View model del panel de Sincronización."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from pos.modules.sync.application.sync_transport import SyncTransport
from pos.modules.sync.domain.enums import SyncMode

_STATUS_REFRESH_MS = 2000


class SyncViewModel(QObject):
    status_changed = Signal(object)
    stations_loaded = Signal(list)
    history_loaded = Signal(list)
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
        al iniciar la app (`main.py`) si el modo configurado lo requiere —
        este método no lo vuelve a arrancar."""
        self._refresh()
        self._timer.start()

    def stop_refreshing(self) -> None:
        self._timer.stop()

    def refresh_now(self) -> None:
        self._refresh()

    def set_mode(self, mode: SyncMode) -> None:
        self._sync_service.set_mode(mode)
        self._transport.apply_mode(mode)
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
            self._transport.apply_mode(SyncMode.PRIMARY)
        self._refresh()

    def _refresh(self) -> None:
        status = self._sync_service.get_status(
            running=self._transport.server.is_running,
            connected=self._transport.client.is_connected,
        )
        self.status_changed.emit(status)
        self.stations_loaded.emit(self._sync_service.list_stations())
        self.history_loaded.emit(self._sync_service.list_recent())
