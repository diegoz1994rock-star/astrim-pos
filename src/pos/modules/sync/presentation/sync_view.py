"""Panel de Sincronización: modo de la estación, configuración de red,
estaciones conocidas e historial de eventos propagados."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.sync.application.dto import SyncLogEntryDTO, SyncStationDTO, SyncStatusDTO
from pos.modules.sync.domain.enums import SyncMode, SyncStationStatus
from pos.modules.sync.presentation.sync_view_model import SyncViewModel

_MODE_LABELS = {
    SyncMode.DISABLED: "Deshabilitada (estación única)",
    SyncMode.PRIMARY: "Servidor principal",
    SyncMode.CLIENT: "Cliente",
}
_STATION_COLUMNS = ["Estación", "Rol", "Estado", "Última conexión"]
_HISTORY_COLUMNS = ["Hora", "Evento", "Módulo", "Origen", "Estado"]


class SyncView(QWidget):
    def __init__(self, view_model: SyncViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._build_ui()
        self._connect_signals()
        self._view_model.start_refreshing()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Sincronización")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        layout.addWidget(title)

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

        layout.addWidget(config_box)

        status_row = QHBoxLayout()
        self._status_label = QLabel("(sin datos)")
        self._pending_label = QLabel("")
        status_row.addWidget(self._status_label)
        status_row.addWidget(self._pending_label)
        status_row.addStretch()
        layout.addLayout(status_row)

        layout.addWidget(QLabel("Estaciones conocidas:"))
        self._stations_table = QTableWidget(0, len(_STATION_COLUMNS), self)
        self._stations_table.setHorizontalHeaderLabels(_STATION_COLUMNS)
        self._stations_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._stations_table.setMaximumHeight(150)
        layout.addWidget(self._stations_table)

        layout.addWidget(QLabel("Historial de eventos sincronizados:"))
        self._history_table = QTableWidget(0, len(_HISTORY_COLUMNS), self)
        self._history_table.setHorizontalHeaderLabels(_HISTORY_COLUMNS)
        self._history_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._history_table)

        refresh_row = QHBoxLayout()
        self._refresh_button = QPushButton("Actualizar ahora")
        refresh_row.addWidget(self._refresh_button)
        refresh_row.addStretch()
        layout.addLayout(refresh_row)

    def _connect_signals(self) -> None:
        self._refresh_button.clicked.connect(self._view_model.refresh_now)
        self._view_model.status_changed.connect(self._on_status_changed)
        self._view_model.stations_loaded.connect(self._on_stations_loaded)
        self._view_model.history_loaded.connect(self._on_history_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.info_occurred.connect(self._show_info)

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

    def _on_status_changed(self, status: SyncStatusDTO) -> None:
        config_widgets = (
            self._mode_combo,
            self._station_name_edit,
            self._port_spin,
            self._peer_url_edit,
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
        for widget in config_widgets:
            widget.blockSignals(False)

        if status.mode is SyncMode.PRIMARY:
            state = "en línea, esperando clientes" if status.running else "detenido"
        elif status.mode is SyncMode.CLIENT:
            state = "conectado" if status.connected else "sin conexión, reintentando…"
        else:
            state = "estación única, sin red"
        self._status_label.setText(f"Estado: {state}")
        self._pending_label.setText(
            f"Eventos locales pendientes de confirmar: {status.pending_outbound_count}"
        )

    def _on_stations_loaded(self, stations: list[SyncStationDTO]) -> None:
        self._stations_table.setRowCount(len(stations))
        for row, station in enumerate(stations):
            self._stations_table.setItem(row, 0, QTableWidgetItem(station.name))
            self._stations_table.setItem(
                row, 1, QTableWidgetItem("Principal" if station.is_primary else "Cliente")
            )
            self._stations_table.setItem(
                row,
                2,
                QTableWidgetItem(
                    "En línea" if station.status is SyncStationStatus.ONLINE else "Fuera de línea"
                ),
            )
            last_seen = f"{station.last_seen_at:%Y-%m-%d %H:%M}" if station.last_seen_at else "—"
            self._stations_table.setItem(row, 3, QTableWidgetItem(last_seen))

    def _on_history_loaded(self, history: list[SyncLogEntryDTO]) -> None:
        self._history_table.setRowCount(len(history))
        for row, entry in enumerate(history):
            self._history_table.setItem(
                row, 0, QTableWidgetItem(f"{entry.created_at:%Y-%m-%d %H:%M:%S}")
            )
            self._history_table.setItem(row, 1, QTableWidgetItem(entry.event_type))
            self._history_table.setItem(row, 2, QTableWidgetItem(entry.entity_type))
            self._history_table.setItem(row, 3, QTableWidgetItem(entry.origin_station_name))
            self._history_table.setItem(row, 4, QTableWidgetItem(entry.status.value))

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        QMessageBox.information(self, "Sincronización", message)
