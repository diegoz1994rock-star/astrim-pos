"""Panel de Sincronización: centro de administración real del transporte
de red (servidor/cliente WebSocket) — estado en vivo, control real del
servidor, diagnóstico, consola de eventos, clientes conectados y
estadísticas, además de la configuración de esta estación."""

from __future__ import annotations

from datetime import UTC, datetime

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.sync.application.dto import (
    ServerProbeResultDTO,
    SyncConnectionDTO,
    SyncEventLogLineDTO,
    SyncLogEntryDTO,
    SyncStationDTO,
    SyncStatusDTO,
    WebSocketProbeResultDTO,
)
from pos.modules.sync.domain.enums import SyncLogStatus, SyncMode, SyncStationStatus
from pos.modules.sync.presentation.sync_view_model import SyncViewModel
from pos.shared_ui.icons import DEFAULT_ICON_SIZE, get_icon
from pos.shared_ui.theme.spacing import SPACING_LG, SPACING_MD
from pos.shared_ui.theme.theme_manager import get_active_tokens
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.status_badge import StatusBadge
from pos.shared_ui.widgets.table_utils import fit_list_to_contents, fit_table_to_contents
from pos.shared_ui.widgets.toast import show_toast

_MODE_LABELS = {
    SyncMode.DISABLED: "Deshabilitada (estación única)",
    SyncMode.PRIMARY: "Servidor principal",
    SyncMode.CLIENT: "Cliente",
}
_ROLE_LABELS = {
    SyncMode.DISABLED: "Estación única",
    SyncMode.PRIMARY: "Servidor principal",
    SyncMode.CLIENT: "Cliente",
}
_LOG_STATUS_ROLES = {
    SyncLogStatus.APPLIED: "success",
    SyncLogStatus.FAILED: "danger",
    SyncLogStatus.PENDING: "warning",
}
_STATION_COLUMNS = ["Estación", "Rol", "Estado", "Última conexión"]
_HISTORY_COLUMNS = ["Hora", "Evento", "Módulo", "Origen", "Estado"]
_CONNECTION_COLUMNS = [
    "Nombre",
    "IP",
    "Puerto",
    "Estado",
    "Hora de conexión",
    "Última sincronización",
    "Versión",
    "Latencia",
    "Tiempo conectado",
]


def _format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _format_latency(latency_ms: float | None) -> str:
    return "—" if latency_ms is None else f"{latency_ms:.0f} ms"


class SyncView(QWidget):
    def __init__(self, view_model: SyncViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._current_url = ""
        self._stations: list[SyncStationDTO] = []
        self._connections: list[SyncConnectionDTO] = []
        self._build_ui()
        self._connect_signals()
        self._view_model.start_refreshing()

    # -- Construcción de la interfaz -----------------------------------------

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area, layout = build_scrollable_page(self)
        outer_layout.addWidget(scroll_area)
        layout.setSpacing(SPACING_MD)
        layout.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)
        layout.addWidget(make_section_title("Sincronización"))

        layout.addWidget(self._build_status_panel())
        layout.addWidget(self._build_info_panel())
        layout.addLayout(self._build_button_row())
        layout.addWidget(self._build_diagnostics_box())
        layout.addWidget(self._build_stats_panel())
        layout.addWidget(self._build_config_box())
        layout.addWidget(QLabel("Registro de eventos:"))
        layout.addWidget(self._build_event_console())
        layout.addWidget(QLabel("Clientes conectados:"))
        layout.addWidget(self._build_connections_table())
        layout.addWidget(QLabel("Estaciones conocidas:"))
        layout.addWidget(self._build_stations_table())
        layout.addWidget(QLabel("Historial de eventos sincronizados:"))
        layout.addWidget(self._build_history_table())

        layout.addStretch()

    def _build_status_panel(self) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("surface")
        row = QHBoxLayout(panel)
        self._status_badge = StatusBadge(emphasis=True)
        row.addWidget(self._status_badge)
        row.addStretch()
        return panel

    def _build_info_panel(self) -> QWidget:
        box = QGroupBox("Información del servidor")
        form = QFormLayout(box)
        self._info_station_label = QLabel()
        self._info_role_label = QLabel()
        self._info_mode_label = QLabel()
        self._info_ip_label = QLabel()
        self._info_port_label = QLabel()
        self._info_url_label = QLabel()
        self._info_url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Nombre de la estación:", self._info_station_label)
        form.addRow("Rol:", self._info_role_label)
        form.addRow("Modo:", self._info_mode_label)
        form.addRow("IP local detectada:", self._info_ip_label)
        form.addRow("Puerto:", self._info_port_label)
        form.addRow("URL WebSocket:", self._info_url_label)
        return box

    def _build_button_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._start_button = QPushButton("Iniciar servidor")
        self._stop_button = QPushButton("Detener servidor")
        self._restart_button = QPushButton("Reiniciar servidor")
        self._sync_now_button = QPushButton("Sincronizar ahora")
        self._copy_url_button = QPushButton("Copiar URL")
        self._test_server_button = QPushButton("Probar servidor")
        self._test_websocket_button = QPushButton("Probar conexión WebSocket")
        icon_color = get_active_tokens().on_primary
        button_icons = (
            ("play", self._start_button),
            ("stop", self._stop_button),
            ("sync", self._restart_button),
            ("sync", self._sync_now_button),
            ("copy", self._copy_url_button),
            ("search", self._test_server_button),
            ("search", self._test_websocket_button),
        )
        for icon_name, button in button_icons:
            button.setIcon(get_icon(icon_name, icon_color))
            button.setIconSize(QSize(DEFAULT_ICON_SIZE, DEFAULT_ICON_SIZE))
            button.setMinimumHeight(48)
            row.addWidget(button)
        return row

    def _build_diagnostics_box(self) -> QWidget:
        box = QGroupBox("Diagnóstico del servidor")
        inner = QVBoxLayout(box)
        self._diagnostics_list = QListWidget()
        self._diagnostics_list.addItem("Presiona \"Probar servidor\" para ejecutar el diagnóstico.")
        fit_list_to_contents(self._diagnostics_list)
        inner.addWidget(self._diagnostics_list)
        return box

    def _build_stats_panel(self) -> QWidget:
        box = QGroupBox("Estadísticas")
        grid = QGridLayout(box)
        self._stat_pending_label = QLabel("0")
        self._stat_sent_label = QLabel("0")
        self._stat_received_label = QLabel("0")
        self._stat_failed_label = QLabel("0")
        self._stat_active_clients_label = QLabel("0")
        self._stat_disconnected_clients_label = QLabel("0")
        self._stat_uptime_label = QLabel("—")
        self._stat_latency_label = QLabel("—")
        pairs = [
            ("Eventos pendientes:", self._stat_pending_label),
            ("Eventos enviados:", self._stat_sent_label),
            ("Eventos recibidos:", self._stat_received_label),
            ("Eventos con error:", self._stat_failed_label),
            ("Clientes activos:", self._stat_active_clients_label),
            ("Clientes desconectados:", self._stat_disconnected_clients_label),
            ("Tiempo de actividad:", self._stat_uptime_label),
            ("Latencia promedio:", self._stat_latency_label),
        ]
        for index, (caption, value_label) in enumerate(pairs):
            row, col = divmod(index, 2)
            caption_label = QLabel(caption)
            caption_label.setProperty("role", "secondary")
            grid.addWidget(caption_label, row, col * 2)
            grid.addWidget(value_label, row, col * 2 + 1)
        return box

    def _build_config_box(self) -> QWidget:
        config_box = QGroupBox("Configuración de esta estación")
        form = QFormLayout(config_box)

        self._station_name_edit = QLineEdit()
        self._station_name_edit.editingFinished.connect(self._on_station_name_changed)
        form.addRow("Nombre de la estación:", self._station_name_edit)

        self._mode_combo = QComboBox()
        for mode in (SyncMode.DISABLED, SyncMode.PRIMARY, SyncMode.CLIENT):
            self._mode_combo.addItem(_MODE_LABELS[mode], mode)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        form.addRow("Modo:", self._mode_combo)

        self._port_spin = QSpinBox()
        self._port_spin.setRange(1024, 65535)
        self._port_spin.editingFinished.connect(self._on_port_changed)
        form.addRow("Puerto del servidor:", self._port_spin)

        self._peer_url_edit = QLineEdit()
        self._peer_url_edit.setPlaceholderText("ws://192.168.1.10:8765/ws/sync")
        self._peer_url_edit.editingFinished.connect(self._on_peer_url_changed)
        form.addRow("URL del servidor principal:", self._peer_url_edit)

        self._auto_start_checkbox = QCheckBox(
            "Iniciar servidor automáticamente al abrir el sistema"
        )
        self._auto_start_checkbox.toggled.connect(self._on_auto_start_toggled)
        form.addRow(self._auto_start_checkbox)

        self._pending_label = QLabel("")
        form.addRow(self._pending_label)

        return config_box

    def _build_event_console(self) -> QWidget:
        self._event_console = QListWidget()
        # Log en vivo, acotado a 500 líneas por `SyncEventLog` — se
        # mantiene con su propio scroll interno tipo terminal (a
        # diferencia de las demás tablas de esta pantalla, que muestran
        # todo su contenido y dejan el desplazamiento a la página) para
        # que una sesión larga no vuelva la página interminable. Alto
        # subido considerablemente (antes 160px) para que el texto se lea
        # cómodo, pedido explícito del usuario.
        self._event_console.setMinimumHeight(320)
        self._event_console.setMaximumHeight(320)
        return self._event_console

    def _build_connections_table(self) -> QWidget:
        self._connections_table = QTableWidget(0, len(_CONNECTION_COLUMNS), self)
        self._connections_table.setHorizontalHeaderLabels(_CONNECTION_COLUMNS)
        self._connections_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        return self._connections_table

    def _build_stations_table(self) -> QWidget:
        self._stations_table = QTableWidget(0, len(_STATION_COLUMNS), self)
        self._stations_table.setHorizontalHeaderLabels(_STATION_COLUMNS)
        self._stations_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        return self._stations_table

    def _build_history_table(self) -> QWidget:
        self._history_table = QTableWidget(0, len(_HISTORY_COLUMNS), self)
        self._history_table.setHorizontalHeaderLabels(_HISTORY_COLUMNS)
        self._history_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        return self._history_table

    # -- Señales --------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._start_button.clicked.connect(self._on_start_clicked)
        self._stop_button.clicked.connect(self._view_model.stop_server)
        self._restart_button.clicked.connect(self._on_restart_clicked)
        self._sync_now_button.clicked.connect(self._on_sync_now_clicked)
        self._copy_url_button.clicked.connect(self._on_copy_url_clicked)
        self._test_server_button.clicked.connect(self._on_test_server_clicked)
        self._test_websocket_button.clicked.connect(self._on_test_websocket_clicked)

        self._view_model.status_changed.connect(self._on_status_changed)
        self._view_model.stations_loaded.connect(self._on_stations_loaded)
        self._view_model.history_loaded.connect(self._on_history_loaded)
        self._view_model.connections_loaded.connect(self._on_connections_loaded)
        self._view_model.events_loaded.connect(self._on_events_loaded)
        self._view_model.diagnostic_result.connect(self._on_diagnostic_result)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.info_occurred.connect(self._show_info)

    # -- Configuración ---------------------------------------------------

    def _on_mode_changed(self, _index: int) -> None:
        mode = self._mode_combo.currentData()
        if mode is not None:
            self._view_model.set_mode(mode)

    def _on_station_name_changed(self) -> None:
        self._view_model.set_local_station_name(self._station_name_edit.text())

    def _on_peer_url_changed(self) -> None:
        self._view_model.set_peer_url(self._peer_url_edit.text())

    def _on_port_changed(self) -> None:
        self._view_model.set_server_port(self._port_spin.value())

    def _on_auto_start_toggled(self, checked: bool) -> None:
        self._view_model.set_auto_start(checked)

    # -- Botones de control -----------------------------------------------

    def _on_start_clicked(self) -> None:
        self._status_badge.set_status("Iniciando…", "warning")
        QApplication.processEvents()
        self._view_model.start_server()

    def _on_restart_clicked(self) -> None:
        self._status_badge.set_status("Iniciando…", "warning")
        QApplication.processEvents()
        self._view_model.restart_server()

    def _on_sync_now_clicked(self) -> None:
        self._view_model.sync_now()

    def _on_copy_url_clicked(self) -> None:
        if not self._current_url:
            self._show_info("Todavía no hay una URL disponible.")
            return
        QApplication.clipboard().setText(self._current_url)
        self._show_info("URL copiada al portapapeles.")

    def _on_test_server_clicked(self) -> None:
        self._view_model.test_server()

    def _on_test_websocket_clicked(self) -> None:
        self._view_model.test_websocket()

    # -- Refresco de datos --------------------------------------------------

    def _on_status_changed(self, status: SyncStatusDTO) -> None:
        config_widgets = (
            self._mode_combo,
            self._station_name_edit,
            self._port_spin,
            self._peer_url_edit,
            self._auto_start_checkbox,
        )
        for widget in config_widgets:
            widget.blockSignals(True)
        if self._station_name_edit.text() != status.local_station_name:
            self._station_name_edit.setText(status.local_station_name)
        index = self._mode_combo.findData(status.mode)
        if index >= 0:
            self._mode_combo.setCurrentIndex(index)
        if self._port_spin.value() != status.server_port:
            self._port_spin.setValue(status.server_port)
        if self._peer_url_edit.text() != (status.peer_url or ""):
            self._peer_url_edit.setText(status.peer_url or "")
        self._auto_start_checkbox.setChecked(status.auto_start_enabled)
        for widget in config_widgets:
            widget.blockSignals(False)

        self._current_url = status.websocket_url
        self._info_station_label.setText(status.local_station_name)
        self._info_role_label.setText(_ROLE_LABELS[status.mode])
        self._info_mode_label.setText(_MODE_LABELS[status.mode])
        self._info_ip_label.setText(status.local_ip)
        self._info_port_label.setText(str(status.server_port))
        self._info_url_label.setText(status.websocket_url)

        if status.mode is SyncMode.PRIMARY:
            if status.running:
                self._status_badge.set_status("Servidor EN LÍNEA", "success")
            elif status.last_error:
                self._status_badge.set_status(f"Error al iniciar: {status.last_error}", "danger")
            else:
                self._status_badge.set_status("Servidor DETENIDO", "danger")
        elif status.mode is SyncMode.CLIENT:
            if status.connected:
                self._status_badge.set_status("Conectado al servidor principal", "success")
            else:
                self._status_badge.set_status("Sin conexión, reintentando…", "danger")
        else:
            self._status_badge.set_status("Sincronización deshabilitada", "secondary")

        self._pending_label.setText(
            f"Eventos locales pendientes de confirmar: {status.pending_outbound_count}"
        )

        self._stat_pending_label.setText(str(status.pending_outbound_count))
        self._stat_sent_label.setText(str(status.sent_count))
        self._stat_received_label.setText(str(status.received_count))
        self._stat_failed_label.setText(str(status.failed_count))
        self._stat_active_clients_label.setText(str(status.connections_count))
        self._stat_uptime_label.setText(_format_duration(status.uptime_seconds))

    def _on_stations_loaded(self, stations: list[SyncStationDTO]) -> None:
        self._stations = stations
        self._stations_table.setRowCount(len(stations))
        for row, station in enumerate(stations):
            self._stations_table.setItem(row, 0, QTableWidgetItem(station.name))
            self._stations_table.setItem(
                row, 1, QTableWidgetItem("Principal" if station.is_primary else "Cliente")
            )
            is_online = station.status is SyncStationStatus.ONLINE
            status_text = "En línea" if is_online else "Fuera de línea"
            self._stations_table.setCellWidget(
                row, 2, StatusBadge(status_text, "success" if is_online else "secondary")
            )
            last_seen = f"{station.last_seen_at:%Y-%m-%d %H:%M}" if station.last_seen_at else "—"
            self._stations_table.setItem(row, 3, QTableWidgetItem(last_seen))
        fit_table_to_contents(self._stations_table)
        self._update_disconnected_stat()

    def _on_history_loaded(self, history: list[SyncLogEntryDTO]) -> None:
        self._history_table.setRowCount(len(history))
        for row, entry in enumerate(history):
            self._history_table.setItem(
                row, 0, QTableWidgetItem(f"{entry.created_at:%Y-%m-%d %H:%M:%S}")
            )
            self._history_table.setItem(row, 1, QTableWidgetItem(entry.event_type))
            self._history_table.setItem(row, 2, QTableWidgetItem(entry.entity_type))
            self._history_table.setItem(row, 3, QTableWidgetItem(entry.origin_station_name))
            self._history_table.setCellWidget(
                row, 4, StatusBadge(entry.status.value, _LOG_STATUS_ROLES[entry.status])
            )
        fit_table_to_contents(self._history_table)

    def _on_connections_loaded(self, connections: list[SyncConnectionDTO]) -> None:
        self._connections = connections
        self._connections_table.setRowCount(len(connections))
        latencies: list[float] = []
        now = datetime.now(UTC)
        for row, connection in enumerate(connections):
            connected_seconds = (now - connection.connected_at).total_seconds()
            values = [
                connection.station_name,
                connection.ip,
                str(connection.port),
                "Conectado",
                f"{connection.connected_at:%H:%M:%S}",
                f"{connection.last_sync_at:%H:%M:%S}" if connection.last_sync_at else "—",
                connection.app_version or "—",
                _format_latency(connection.latency_ms),
                _format_duration(connected_seconds),
            ]
            for col, value in enumerate(values):
                self._connections_table.setItem(row, col, QTableWidgetItem(value))
            if connection.latency_ms is not None:
                latencies.append(connection.latency_ms)
        fit_table_to_contents(self._connections_table)
        self._stat_latency_label.setText(
            _format_latency(sum(latencies) / len(latencies)) if latencies else "—"
        )
        self._update_disconnected_stat()

    def _update_disconnected_stat(self) -> None:
        """Estaciones conocidas (menos la propia estación local, que no
        tiene una conexión WebSocket consigo misma) que no aparecen entre
        las conexiones vivas ahora mismo."""
        connected_names = {c.station_name for c in self._connections}
        local_name = self._info_station_label.text()
        disconnected = [
            s for s in self._stations if s.name != local_name and s.name not in connected_names
        ]
        self._stat_disconnected_clients_label.setText(str(len(disconnected)))

    def _on_events_loaded(self, events: list[SyncEventLogLineDTO]) -> None:
        self._event_console.clear()
        for line in events:
            self._event_console.addItem(f"{line.occurred_at:%H:%M:%S}  {line.message}")
        self._event_console.scrollToBottom()

    def _on_diagnostic_result(self, result: object) -> None:
        self._diagnostics_list.clear()
        if isinstance(result, ServerProbeResultDTO):
            for step in result.steps:
                mark = "✓" if step.passed else "✗"
                text = f"{mark} {step.label}"
                if step.detail:
                    text += f" — {step.detail}"
                self._diagnostics_list.addItem(QListWidgetItem(text))
        elif isinstance(result, WebSocketProbeResultDTO):
            mark = "✓" if result.success else "✗"
            self._diagnostics_list.addItem(QListWidgetItem(f"{mark} {result.detail}"))
        fit_list_to_contents(self._diagnostics_list)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        show_toast(self, message)
