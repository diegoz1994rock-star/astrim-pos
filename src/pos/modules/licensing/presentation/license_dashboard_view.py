"""Panel de administración de Licencia — dashboard completo (estado,
información, dispositivo, resumen de uso, acciones rápidas, historial e
información importante). Distinto de `LicenseView` (pantalla de bloqueo
pre-login, sin cambios) — este es el que se abre desde el menú
"Licencia" (`main.py::_build_license_content`, `admin_only=True`)."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.licensing.application.dto import (
    AuthorizedDeviceDTO,
    LicenseHistoryEntryDTO,
    LicenseUsageDTO,
    LicenseVerificationDTO,
)
from pos.modules.licensing.domain.enums import (
    LicenseHistoryAction,
    LicenseStatus,
    LicenseType,
    LicenseVerificationResult,
)
from pos.modules.licensing.presentation.authorized_devices_dialog import AuthorizedDevicesDialog
from pos.modules.licensing.presentation.license_dashboard_view_model import (
    LicenseDashboardViewModel,
)
from pos.shared_ui.theme.spacing import SPACING_LG, SPACING_MD, SPACING_SM
from pos.shared_ui.theme.theme_manager import get_active_tokens
from pos.shared_ui.widgets.icon_badge import build_icon_badge
from pos.shared_ui.widgets.kpi_card import KpiCard
from pos.shared_ui.widgets.percentage_bar import PercentageBar
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.status_badge import StatusBadge
from pos.shared_ui.widgets.table_utils import fit_table_to_contents
from pos.shared_ui.widgets.toast import show_toast

_RESULT_LABELS: dict[LicenseVerificationResult, tuple[str, str]] = {
    LicenseVerificationResult.VALID: ("Activa", "success"),
    LicenseVerificationResult.EXPIRED: ("Vencida", "danger"),
    LicenseVerificationResult.SUSPENDED: ("Suspendida", "warning"),
    LicenseVerificationResult.BLOCKED: ("Bloqueada", "danger"),
    LicenseVerificationResult.HARDWARE_MISMATCH: ("Equipo no autorizado", "danger"),
    LicenseVerificationResult.INVALID_SIGNATURE: ("Licencia inválida", "danger"),
    LicenseVerificationResult.CLOCK_TAMPERING_DETECTED: ("Reloj manipulado", "warning"),
}
_LICENSE_TYPE_LABELS = {
    LicenseType.TRIAL: "Prueba",
    LicenseType.MONTHLY: "Mensual",
    LicenseType.SEMIANNUAL: "Semestral",
    LicenseType.ANNUAL: "Anual",
    LicenseType.PERMANENT: "Permanente",
}
_HISTORY_ACTION_LABELS = {
    LicenseHistoryAction.ACTIVATED: "Activación",
    LicenseHistoryAction.RENEWED: "Renovación",
    LicenseHistoryAction.SUSPENDED: "Suspensión",
    LicenseHistoryAction.REACTIVATED: "Reactivación",
    LicenseHistoryAction.BLOCKED: "Bloqueo",
    LicenseHistoryAction.DEVICE_REGISTERED: "Dispositivo autorizado",
    LicenseHistoryAction.DEVICE_REVOKED: "Dispositivo revocado",
}
_STATUS_LABELS: dict[LicenseStatus, tuple[str, str]] = {
    LicenseStatus.ACTIVE: ("Activa", "success"),
    LicenseStatus.EXPIRED: ("Vencida", "danger"),
    LicenseStatus.REVOKED: ("Revocada", "danger"),
    LicenseStatus.SUSPENDED: ("Suspendida", "warning"),
    LicenseStatus.BLOCKED: ("Bloqueada", "danger"),
}
_EXPIRY_WARNING_DAYS = 15
_HISTORY_COLUMNS = ["Fecha", "Acción", "Equipo", "IP", "Estado", "Detalle"]


def _format_date(value: datetime | None) -> str:
    return f"{value:%Y-%m-%d}" if value is not None else "—"


def _mask_key(license_key: str | None) -> str:
    if not license_key:
        return ""
    if len(license_key) <= 12:
        return license_key
    return f"{license_key[:6]}…{license_key[-6:]}"


class LicenseDashboardView(QWidget):
    def __init__(
        self, view_model: LicenseDashboardViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._devices: list[AuthorizedDeviceDTO] = []
        self._current_status: LicenseStatus | None = None
        self._build_ui()
        self._connect_signals()
        self._view_model.start_refreshing()

    # -- construcción de la interfaz -----------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll_area, layout = build_scrollable_page(self)
        outer.addWidget(scroll_area)
        layout.setSpacing(SPACING_MD)
        layout.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)

        layout.addWidget(make_section_title("Licencia"))
        layout.addWidget(self._build_top_bar())
        layout.addWidget(self._build_status_panel())
        layout.addWidget(self._build_info_panel())
        layout.addWidget(self._build_device_panel())
        layout.addWidget(self._build_usage_panel())
        layout.addWidget(self._build_actions_panel())
        layout.addWidget(make_section_title("Historial"))
        layout.addWidget(self._build_history_table())
        layout.addWidget(self._build_important_info_panel())
        layout.addStretch()

    def _build_top_bar(self) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("surface")
        row = QHBoxLayout(panel)
        self._last_check_label = QLabel("Última verificación: —", panel)
        self._last_check_label.setProperty("role", "secondary")
        row.addWidget(self._last_check_label)
        row.addStretch()
        self._online_badge = StatusBadge("En línea", "success", emphasis=True)
        row.addWidget(self._online_badge)
        self._refresh_button = QPushButton("Actualizar", panel)
        row.addWidget(self._refresh_button)
        self._change_license_button = QPushButton("Cambiar licencia", panel)
        row.addWidget(self._change_license_button)
        return panel

    def _build_status_panel(self) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("surface")
        outer = QVBoxLayout(panel)

        header_row = QHBoxLayout()
        tokens = get_active_tokens()
        self._status_icon = build_icon_badge(
            "key", tokens.primary, tokens.header_accent, size=64, parent=panel
        )
        header_row.addWidget(self._status_icon)

        text_col = QVBoxLayout()
        self._status_badge = StatusBadge(emphasis=True)
        text_col.addWidget(self._status_badge)
        self._license_type_label = QLabel(panel)
        self._license_type_label.setProperty("role", "secondary")
        text_col.addWidget(self._license_type_label)
        header_row.addLayout(text_col)
        header_row.addStretch()
        outer.addLayout(header_row)

        self._expiry_warning_label = QLabel(panel)
        self._expiry_warning_label.setProperty("role", "warning")
        self._expiry_warning_label.setProperty("emphasis", True)
        self._expiry_warning_label.setWordWrap(True)
        self._expiry_warning_label.setVisible(False)
        outer.addWidget(self._expiry_warning_label)

        self._percentage_bar = PercentageBar(panel)
        outer.addWidget(self._percentage_bar)
        self._period_label = QLabel(panel)
        self._period_label.setProperty("role", "secondary")
        outer.addWidget(self._period_label)

        return panel

    def _build_info_panel(self) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("surface")
        form = QFormLayout(panel)
        self._company_label = QLabel(panel)
        self._nit_label = QLabel(panel)
        self._type_label = QLabel(panel)
        self._activated_label = QLabel(panel)
        self._expires_label = QLabel(panel)
        self._key_field = QLineEdit(panel)
        self._key_field.setReadOnly(True)
        self._fingerprint_field = QLineEdit(self._view_model.hardware_fingerprint, panel)
        self._fingerprint_field.setReadOnly(True)
        form.addRow("Empresa:", self._company_label)
        form.addRow("NIT:", self._nit_label)
        form.addRow("Tipo de licencia:", self._type_label)
        form.addRow("Fecha de activación:", self._activated_label)
        form.addRow("Fecha de vencimiento:", self._expires_label)
        form.addRow("Clave de licencia:", self._key_field)
        form.addRow("Huella de este equipo:", self._fingerprint_field)
        return panel

    def _build_device_panel(self) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("surface")
        form = QFormLayout(panel)
        self._device_name_label = QLabel(panel)
        self._device_fingerprint_label = QLabel(panel)
        self._device_last_seen_label = QLabel(panel)
        self._device_status_badge = StatusBadge()
        form.addRow("Nombre del equipo:", self._device_name_label)
        form.addRow("Identificador (Hardware ID):", self._device_fingerprint_label)
        form.addRow("Última conexión:", self._device_last_seen_label)
        form.addRow("Estado:", self._device_status_badge)
        self._view_devices_button = QPushButton("Ver dispositivos autorizados", panel)
        form.addRow(self._view_devices_button)
        return panel

    def _build_usage_panel(self) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("surface")
        outer = QVBoxLayout(panel)
        outer.addWidget(make_section_title("Resumen de uso", panel))
        grid = QGridLayout()
        grid.setSpacing(SPACING_SM)
        self._users_card = KpiCard("Usuarios", "—/—", icon="users", accent="primary")
        self._branches_card = KpiCard("Sucursales", "—/—", icon="package", accent="primary")
        self._registers_card = KpiCard("Cajas", "—/—", icon="cash", accent="primary")
        self._devices_card = KpiCard("Dispositivos", "—/—", icon="key", accent="primary")
        for index, card in enumerate(
            (self._users_card, self._branches_card, self._registers_card, self._devices_card)
        ):
            grid.addWidget(card, 0, index)
        outer.addLayout(grid)
        return panel

    def _build_actions_panel(self) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("surface")
        outer = QVBoxLayout(panel)
        outer.addWidget(make_section_title("Acciones rápidas", panel))
        grid = QGridLayout()
        grid.setSpacing(SPACING_SM)
        self._renew_button = QPushButton("Renovar / cambiar licencia", panel)
        self._suspend_reactivate_button = QPushButton("Suspender licencia", panel)
        self._block_button = QPushButton("Bloquear licencia", panel)
        self._block_button.setProperty("role", "danger")
        self._devices_action_button = QPushButton("Agregar / ver dispositivos", panel)
        self._history_scroll_button = QPushButton("Historial", panel)
        self._download_button = QPushButton("Descargar información", panel)
        self._support_button = QPushButton("Contactar soporte", panel)
        buttons = (
            self._renew_button,
            self._suspend_reactivate_button,
            self._block_button,
            self._devices_action_button,
            self._history_scroll_button,
            self._download_button,
            self._support_button,
        )
        for index, button in enumerate(buttons):
            grid.addWidget(button, index // 3, index % 3)
        outer.addLayout(grid)
        return panel

    def _build_history_table(self) -> QWidget:
        self._history_table = QTableWidget(0, len(_HISTORY_COLUMNS), self)
        self._history_table.setHorizontalHeaderLabels(_HISTORY_COLUMNS)
        self._history_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        return self._history_table

    def _build_important_info_panel(self) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("surface")
        outer = QVBoxLayout(panel)
        outer.addWidget(make_section_title("Información importante", panel))
        messages = [
            "La licencia está vinculada a este dispositivo — copiar la base de datos a otro "
            "equipo no permite activarla ahí.",
            "El sistema verifica automáticamente la licencia cada cierto tiempo mientras la "
            "aplicación está abierta.",
            "El modo sin conexión está disponible por un tiempo limitado — la licencia debe "
            "poder verificarse periódicamente.",
            "Antes de cambiar componentes importantes del equipo (disco, placa base), contacta "
            "a soporte para evitar que el identificador de hardware cambie.",
        ]
        for message in messages:
            label = QLabel(message, panel)
            label.setProperty("role", "info")
            label.setWordWrap(True)
            outer.addWidget(label)
        return panel

    # -- señales --------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._refresh_button.clicked.connect(self._view_model.refresh_now)
        self._change_license_button.clicked.connect(self._on_change_license_clicked)
        self._renew_button.clicked.connect(self._on_change_license_clicked)
        self._suspend_reactivate_button.clicked.connect(self._on_suspend_reactivate_clicked)
        self._block_button.clicked.connect(self._on_block_clicked)
        self._view_devices_button.clicked.connect(self._on_view_devices_clicked)
        self._devices_action_button.clicked.connect(self._on_view_devices_clicked)
        self._history_scroll_button.clicked.connect(
            lambda: self._history_table.scrollToTop()
        )
        self._download_button.clicked.connect(self._on_download_clicked)
        self._support_button.clicked.connect(self._on_support_clicked)

        self._view_model.verification_changed.connect(self._on_verification_changed)
        self._view_model.devices_loaded.connect(self._on_devices_loaded)
        self._view_model.history_loaded.connect(self._on_history_loaded)
        self._view_model.usage_loaded.connect(self._on_usage_loaded)
        self._view_model.connectivity_changed.connect(self._on_connectivity_changed)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.info_occurred.connect(self._show_info)

    # -- manejadores de datos ---------------------------------------------

    def _on_connectivity_changed(self, online: bool) -> None:
        self._last_check_label.setText(f"Última verificación: {datetime.now():%H:%M:%S}")
        if online:
            self._online_badge.set_status("En línea", "success")
        else:
            self._online_badge.set_status("Fuera de línea", "danger")

    def _on_verification_changed(self, verification: LicenseVerificationDTO) -> None:
        label, role = _RESULT_LABELS.get(verification.result, (verification.result.value, "secondary"))
        self._status_badge.set_status(label, role)

        license_dto = verification.license
        if license_dto is None:
            self._license_type_label.setText("Sin licencia activada en esta estación.")
            self._company_label.setText("—")
            self._nit_label.setText("—")
            self._type_label.setText("—")
            self._activated_label.setText("—")
            self._expires_label.setText("—")
            self._key_field.setText("")
            self._expiry_warning_label.setVisible(False)
            self._percentage_bar.setVisible(False)
            self._period_label.setText("")
            self._current_status = None
            self._update_action_buttons()
            return

        self._current_status = license_dto.status
        self._license_type_label.setText(
            _LICENSE_TYPE_LABELS.get(license_dto.license_type, license_dto.license_type.value)
        )
        self._company_label.setText(license_dto.company_name or "—")
        self._nit_label.setText(license_dto.company_nit or "—")
        self._type_label.setText(
            _LICENSE_TYPE_LABELS.get(license_dto.license_type, license_dto.license_type.value)
        )
        self._activated_label.setText(_format_date(license_dto.issued_at))
        self._expires_label.setText(_format_date(license_dto.expires_at))
        self._key_field.setText("")
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        status = self._current_status
        if status is LicenseStatus.SUSPENDED:
            self._suspend_reactivate_button.setText("Reactivar licencia")
            self._suspend_reactivate_button.setEnabled(True)
        elif status in (LicenseStatus.ACTIVE, LicenseStatus.EXPIRED):
            self._suspend_reactivate_button.setText("Suspender licencia")
            self._suspend_reactivate_button.setEnabled(status is LicenseStatus.ACTIVE)
        else:
            self._suspend_reactivate_button.setText("Suspender licencia")
            self._suspend_reactivate_button.setEnabled(False)
        self._block_button.setEnabled(status is not None and status is not LicenseStatus.BLOCKED)

    def _on_devices_loaded(self, devices: list[AuthorizedDeviceDTO]) -> None:
        self._devices = devices
        current = next((d for d in devices if d.is_current_device), None)
        if current is None:
            self._device_name_label.setText("—")
            self._device_fingerprint_label.setText(self._view_model.hardware_fingerprint)
            self._device_last_seen_label.setText("—")
            self._device_status_badge.set_status("Sin registrar", "secondary")
        else:
            self._device_name_label.setText(current.device_name or "—")
            self._device_fingerprint_label.setText(current.hardware_fingerprint)
            self._device_last_seen_label.setText(f"{current.last_seen_at:%Y-%m-%d %H:%M}")
            status_text = "Activo" if current.status.value == "active" else "Revocado"
            status_role = "success" if current.status.value == "active" else "danger"
            self._device_status_badge.set_status(status_text, status_role)
        self._view_devices_button.setText(f"Ver dispositivos autorizados ({len(devices)})")

    def _on_history_loaded(self, entries: list[LicenseHistoryEntryDTO]) -> None:
        self._history_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self._history_table.setItem(row, 0, QTableWidgetItem(f"{entry.occurred_at:%Y-%m-%d %H:%M}"))
            self._history_table.setItem(
                row, 1, QTableWidgetItem(_HISTORY_ACTION_LABELS.get(entry.action, entry.action.value))
            )
            self._history_table.setItem(row, 2, QTableWidgetItem(entry.device_name or "—"))
            self._history_table.setItem(row, 3, QTableWidgetItem(entry.ip_address or "—"))
            status_text, status_role = _STATUS_LABELS.get(
                entry.status_at_time, (entry.status_at_time.value, "secondary")
            )
            self._history_table.setCellWidget(row, 4, StatusBadge(status_text, status_role))
            self._history_table.setItem(row, 5, QTableWidgetItem(entry.details or "—"))
        fit_table_to_contents(self._history_table)

    def _on_usage_loaded(self, usage: LicenseUsageDTO | None) -> None:
        if usage is None:
            return
        self._users_card.set_value(self._format_usage(usage.users_used, usage.users_allowed))
        self._branches_card.set_value(
            self._format_usage(usage.branches_used, usage.branches_allowed)
        )
        self._registers_card.set_value(
            self._format_usage(usage.registers_used, usage.registers_allowed)
        )
        self._devices_card.set_value(
            self._format_usage(usage.devices_used, usage.devices_allowed)
        )

        if usage.period_elapsed_pct is None:
            self._percentage_bar.setVisible(False)
            self._period_label.setText("Licencia permanente — sin vencimiento.")
            self._period_label.setProperty("role", "success")
            self._expiry_warning_label.setVisible(False)
        else:
            self._percentage_bar.setVisible(True)
            role = "danger" if usage.period_elapsed_pct >= 90 else "primary"
            self._percentage_bar.set_percentage(usage.period_elapsed_pct, role)
            days = usage.days_remaining or 0
            self._period_label.setText(f"{usage.period_elapsed_pct:.0f}% del período consumido")
            self._period_label.setProperty("role", "secondary")
            if usage.days_remaining is not None and usage.days_remaining <= _EXPIRY_WARNING_DAYS:
                self._expiry_warning_label.setText(f"Tu licencia vence en {days} días.")
                self._expiry_warning_label.setVisible(True)
            else:
                self._expiry_warning_label.setVisible(False)
        self._period_label.style().unpolish(self._period_label)
        self._period_label.style().polish(self._period_label)

    @staticmethod
    def _format_usage(used: int, allowed: int | None) -> str:
        return f"{used} (sin límite)" if allowed is None else f"{used}/{allowed}"

    # -- acciones -----------------------------------------------------------

    def _on_change_license_clicked(self) -> None:
        license_key, accepted = QInputDialog.getText(
            self, "Cambiar licencia", "Pega la nueva clave de licencia:"
        )
        if not accepted:
            return
        self._view_model.renew(license_key)

    def _on_suspend_reactivate_clicked(self) -> None:
        if self._current_status is LicenseStatus.SUSPENDED:
            self._view_model.reactivate()
            return
        reason, _accepted = QInputDialog.getText(
            self, "Suspender licencia", "Motivo (opcional):"
        )
        self._view_model.suspend(reason or None)

    def _on_block_clicked(self) -> None:
        confirmed = QMessageBox.question(
            self,
            "Bloquear licencia",
            "Bloquear la licencia impide su uso hasta que el proveedor emita una clave nueva. "
            "¿Continuar?",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        reason, _accepted = QInputDialog.getText(self, "Bloquear licencia", "Motivo (opcional):")
        self._view_model.block(reason or None)

    def _on_view_devices_clicked(self) -> None:
        dialog = AuthorizedDevicesDialog(self._devices, self._view_model.revoke_device, self)
        dialog.exec()

    def _on_download_clicked(self) -> None:
        show_toast(self, "La exportación de la información de licencia estará disponible pronto.")

    def _on_support_clicked(self) -> None:
        QMessageBox.information(
            self,
            "Contactar soporte",
            "Escribe a soporte@astrim.com o comunícate por WhatsApp con tu proveedor, "
            "indicando el identificador de este equipo (huella de hardware).",
        )

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        show_toast(self, message)
