"""Pantalla de administración de impresoras (Administración → Dispositivos
→ Impresoras) — no limitada a ninguna marca: cualquier impresora que el
sistema operativo reconozca (`PrintMethod.SYSTEM_DRIVER`) o cualquier
térmica hablando ESC/POS por puerto (`PrintMethod.RAW_ESCPOS`, ver
`application/providers/`)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.printers.application.dto import DetectedPrinterDTO, PrinterDTO
from pos.modules.printers.application.providers.registry import (
    PRINT_METHOD_LABELS,
    PRINTER_TYPE_LABELS,
)
from pos.modules.printers.domain.enums import ConnectionStatus
from pos.modules.printers.presentation.printer_diagnostics_dialog import PrinterDiagnosticsDialog
from pos.modules.printers.presentation.printer_discovery_dialog import PrinterDiscoveryDialog
from pos.modules.printers.presentation.printer_form_dialog import PrinterFormDialog
from pos.modules.printers.presentation.printer_history_dialog import PrinterHistoryDialog
from pos.modules.printers.presentation.printer_preview_dialog import PrinterPreviewDialog
from pos.modules.printers.presentation.printer_test_panel_dialog import PrinterTestPanelDialog
from pos.modules.printers.presentation.printers_view_model import PrintersViewModel
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.status_badge import StatusBadge
from pos.shared_ui.widgets.table_utils import fit_table_to_contents
from pos.shared_ui.widgets.toast import show_toast

_COLUMNS = [
    "Nombre", "Marca / Modelo", "Tipo", "Método", "Caja", "Área",
    "Predeterminada", "Activa", "Estado",
]
_STATUS_ROLE = {
    ConnectionStatus.CONNECTED: ("Conectada", "success"),
    ConnectionStatus.DISCONNECTED: ("Desconectada", "secondary"),
    ConnectionStatus.ERROR: ("Error", "danger"),
}


class PrintersView(QWidget):
    def __init__(
        self, view_model: PrintersViewModel, invoices_dir: Path, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._invoices_dir = invoices_dir
        self._devices: list[PrinterDTO] = []
        self._visible_devices: list[PrinterDTO] = []
        self._cash_register_names: dict[int, str] = {}
        self._cash_registers: list[tuple[int, str]] = []
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def reload(self) -> None:
        self._view_model.load()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll_area, layout = build_scrollable_page(self)
        outer.addWidget(scroll_area)
        toolbar = QHBoxLayout()
        toolbar.addWidget(make_section_title("Impresoras"))
        toolbar.addStretch()
        self._discover_button = QPushButton("Buscar impresoras")
        self._new_button = QPushButton("Agregar impresora")
        toolbar.addWidget(self._discover_button)
        toolbar.addWidget(self._new_button)
        layout.addLayout(toolbar)

        self._search_edit = QLineEdit(self)
        self._search_edit.setPlaceholderText("Buscar por nombre, marca, modelo o número de serie…")
        layout.addWidget(self._search_edit)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.cellDoubleClicked.connect(self._on_table_double_clicked)
        layout.addWidget(self._table)

        management_row = QHBoxLayout()
        self._edit_button = QPushButton("Editar")
        self._delete_button = QPushButton("Eliminar")
        self._toggle_button = QPushButton("Activar/Desactivar")
        self._set_default_button = QPushButton("Marcar como predeterminada")
        for button in (
            self._edit_button, self._delete_button, self._toggle_button,
            self._set_default_button,
        ):
            management_row.addWidget(button)
        layout.addLayout(management_row)

        connection_row = QHBoxLayout()
        self._connect_button = QPushButton("Conectar")
        self._disconnect_button = QPushButton("Desconectar")
        self._test_connection_button = QPushButton("Probar conexión")
        self._test_page_button = QPushButton("Probar impresora")
        self._preview_button = QPushButton("Vista previa")
        self._diagnostics_button = QPushButton("Diagnóstico")
        self._history_button = QPushButton("Historial")
        for button in (
            self._connect_button, self._disconnect_button, self._test_connection_button,
            self._test_page_button, self._preview_button, self._diagnostics_button,
            self._history_button,
        ):
            connection_row.addWidget(button)
        layout.addLayout(connection_row)

    def _connect_signals(self) -> None:
        self._discover_button.clicked.connect(self._on_discover_clicked)
        self._new_button.clicked.connect(self._on_new_clicked)
        self._edit_button.clicked.connect(self._on_edit_clicked)
        self._delete_button.clicked.connect(self._on_delete_clicked)
        self._toggle_button.clicked.connect(self._on_toggle_clicked)
        self._set_default_button.clicked.connect(self._on_set_default_clicked)
        self._connect_button.clicked.connect(self._on_connect_clicked)
        self._disconnect_button.clicked.connect(self._on_disconnect_clicked)
        self._test_connection_button.clicked.connect(self._on_test_connection_clicked)
        self._test_page_button.clicked.connect(self._on_test_page_clicked)
        self._preview_button.clicked.connect(self._on_preview_clicked)
        self._diagnostics_button.clicked.connect(self._on_diagnostics_clicked)
        self._history_button.clicked.connect(self._on_history_clicked)
        self._search_edit.textChanged.connect(self._render_table)
        self._view_model.devices_loaded.connect(self._on_devices_loaded)
        self._view_model.cash_registers_loaded.connect(self._on_cash_registers_loaded)
        self._view_model.detected_printers_loaded.connect(self._on_detected_printers_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_cash_registers_loaded(self, registers: list[tuple[int, str]]) -> None:
        self._cash_registers = registers
        self._cash_register_names = dict(registers)
        self._render_table()

    def _on_devices_loaded(self, devices: list[PrinterDTO]) -> None:
        self._devices = devices
        self._render_table()

    def _render_table(self) -> None:
        query = self._search_edit.text().strip().lower()
        self._visible_devices = [
            d
            for d in self._devices
            if not query
            or query in " ".join(filter(None, [d.name, d.brand, d.model, d.serial_number])).lower()
        ]
        self._table.setRowCount(len(self._visible_devices))
        for row, device in enumerate(self._visible_devices):
            brand_model = " / ".join(filter(None, [device.brand, device.model])) or "—"
            register_name = self._cash_register_names.get(device.cash_register_id or -1, "—")
            self._table.setItem(row, 0, QTableWidgetItem(device.name))
            self._table.setItem(row, 1, QTableWidgetItem(brand_model))
            self._table.setItem(
                row, 2, QTableWidgetItem(PRINTER_TYPE_LABELS.get(device.printer_type, "—"))
            )
            self._table.setItem(
                row, 3, QTableWidgetItem(PRINT_METHOD_LABELS.get(device.print_method, "—"))
            )
            self._table.setItem(row, 4, QTableWidgetItem(register_name))
            self._table.setItem(row, 5, QTableWidgetItem(device.area or "—"))
            self._table.setItem(row, 6, QTableWidgetItem("Sí" if device.is_default else ""))
            self._table.setItem(row, 7, QTableWidgetItem("Sí" if device.is_active else "No"))
            text, role = _STATUS_ROLE[device.connection_status]
            self._table.setCellWidget(row, 8, StatusBadge(text, role))
        fit_table_to_contents(self._table)

    def _on_discover_clicked(self) -> None:
        self._view_model.discover_printers()

    def _on_detected_printers_loaded(self, detected: list[DetectedPrinterDTO]) -> None:
        dialog = PrinterDiscoveryDialog(detected, parent=self)
        if dialog.exec() != PrinterDiscoveryDialog.DialogCode.Accepted:
            return
        selected = dialog.selected_printer()
        if selected is None:
            return
        if selected.already_registered:
            self._show_info(f"'{selected.name}' ya está registrada.")
            return
        form = PrinterFormDialog(
            cash_registers=self._cash_registers, detected_name=selected.name, parent=self
        )
        if form.exec() != PrinterFormDialog.DialogCode.Accepted:
            return
        self._view_model.create_device(**form.values())

    def _on_new_clicked(self) -> None:
        dialog = PrinterFormDialog(cash_registers=self._cash_registers, parent=self)
        if dialog.exec() != PrinterFormDialog.DialogCode.Accepted:
            return
        self._view_model.create_device(**dialog.values())

    def _selected_device(self) -> PrinterDTO | None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        return self._visible_devices[selected_rows[0].row()]

    def _on_table_double_clicked(self, row: int, _column: int) -> None:
        self._open_edit_dialog(self._visible_devices[row])

    def _on_edit_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona una impresora de la tabla.")
            return
        self._open_edit_dialog(device)

    def _open_edit_dialog(self, device: PrinterDTO) -> None:
        dialog = PrinterFormDialog(
            existing_device=device, cash_registers=self._cash_registers, parent=self
        )
        if dialog.exec() != PrinterFormDialog.DialogCode.Accepted:
            return
        self._view_model.update_device(device.id, **dialog.values())

    def _on_delete_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona una impresora de la tabla.")
            return
        confirmed = QMessageBox.question(
            self,
            "Eliminar impresora",
            f"¿Seguro que deseas eliminar '{device.name}'? Esta acción no se puede deshacer.",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        self._view_model.delete_device(device.id)

    def _on_toggle_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona una impresora de la tabla.")
            return
        self._view_model.set_active(device.id, not device.is_active)

    def _on_set_default_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona una impresora de la tabla.")
            return
        self._view_model.set_default(device.id)

    def _on_connect_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona una impresora de la tabla.")
            return
        self._view_model.connect_device(device.id)

    def _on_disconnect_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona una impresora de la tabla.")
            return
        self._view_model.disconnect_device(device.id)

    def _on_test_connection_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona una impresora de la tabla.")
            return
        self._view_model.test_connection(device.id)

    def _on_test_page_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona una impresora de la tabla.")
            return
        dialog = PrinterTestPanelDialog(
            self._view_model.service, self._view_model.session_manager,
            device.id, device.name, parent=self,
        )
        dialog.exec()

    def _on_preview_clicked(self) -> None:
        """Vista previa real de cualquier PDF ya generado (factura o
        recibo de abono) — abre el explorador de archivos en la carpeta de
        comprobantes, y renderiza con la misma vía (`QPdfDocument`) que
        usan ambos métodos de impresión."""
        file_path, _filter = QFileDialog.getOpenFileName(
            self, "Selecciona un comprobante para previsualizar",
            str(self._invoices_dir), "PDF (*.pdf)",
        )
        if not file_path:
            return
        dialog = PrinterPreviewDialog(Path(file_path), parent=self)
        dialog.exec()

    def _on_diagnostics_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona una impresora de la tabla.")
            return
        dialog = PrinterDiagnosticsDialog(
            self._view_model.service, device.id, device.name, parent=self
        )
        dialog.exec()

    def _on_history_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona una impresora de la tabla.")
            return
        events = self._view_model.service.list_events(device.id)
        dialog = PrinterHistoryDialog(events, device.name, parent=self)
        dialog.exec()

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        show_toast(self, message)
