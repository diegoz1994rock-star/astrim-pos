"""Diálogo "Ver dispositivos autorizados" — lista los equipos autorizados
bajo la licencia vigente (`AuthorizedDeviceDTO`), con la posibilidad de
revocar cualquiera salvo el equipo desde el que se está viendo el
diálogo (mismo resguardo que ya aplica `LicenseService.revoke_device` a
nivel de negocio: nunca te puedes revocar a ti mismo)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from pos.modules.licensing.application.dto import AuthorizedDeviceDTO
from pos.modules.licensing.domain.enums import DeviceStatus
from pos.shared_ui.widgets.status_badge import StatusBadge
from pos.shared_ui.widgets.table_utils import fit_table_to_contents

_COLUMNS = ["Equipo", "Huella", "IP", "Primera vez", "Última vez", "Estado", ""]


def _truncated_fingerprint(fingerprint: str) -> str:
    return fingerprint if len(fingerprint) <= 16 else f"{fingerprint[:16]}…"


class AuthorizedDevicesDialog(QDialog):
    def __init__(
        self,
        devices: list[AuthorizedDeviceDTO],
        on_revoke: Callable[[str], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Dispositivos autorizados")
        self.resize(720, 400)
        self._devices = devices
        self._on_revoke = on_revoke

        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        button_row = QHBoxLayout()
        button_row.addStretch()
        close_button = QPushButton("Cerrar", self)
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

        self._populate()

    def _populate(self) -> None:
        self._table.setRowCount(len(self._devices))
        for row, device in enumerate(self._devices):
            name = device.device_name or "—"
            if device.is_current_device:
                name += " ★ (este equipo)"
            self._table.setItem(row, 0, QTableWidgetItem(name))
            self._table.setItem(row, 1, QTableWidgetItem(_truncated_fingerprint(device.hardware_fingerprint)))
            self._table.setItem(row, 2, QTableWidgetItem(device.ip_address or "—"))
            self._table.setItem(row, 3, QTableWidgetItem(f"{device.first_seen_at:%Y-%m-%d %H:%M}"))
            self._table.setItem(row, 4, QTableWidgetItem(f"{device.last_seen_at:%Y-%m-%d %H:%M}"))
            is_active = device.status is DeviceStatus.ACTIVE
            status_text = "Activo" if is_active else "Revocado"
            status_role = "success" if is_active else "secondary"
            self._table.setCellWidget(row, 5, StatusBadge(status_text, status_role))

            revoke_button = QPushButton("Revocar", self)
            revoke_button.setEnabled(is_active and not device.is_current_device)
            revoke_button.clicked.connect(
                lambda _checked=False, fp=device.hardware_fingerprint: self._revoke(fp)
            )
            self._table.setCellWidget(row, 6, revoke_button)
        fit_table_to_contents(self._table)

    def _revoke(self, hardware_fingerprint: str) -> None:
        self._on_revoke(hardware_fingerprint)
        self.accept()
