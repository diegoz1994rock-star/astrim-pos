"""Pantalla de caja: selección de punto de caja, apertura/cierre y
movimientos manuales del turno abierto."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pos.modules.cash_register.application.dto import (
    CashMovementDTO,
    CashRegisterDTO,
    CashSessionDTO,
)
from pos.modules.cash_register.domain.enums import CashMovementType
from pos.modules.cash_register.presentation.cash_register_view_model import (
    CashRegisterViewModel,
)
from pos.modules.users.application.dto import UserDTO
from pos.shared_ui.formatting import format_currency
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.table_utils import fit_list_to_contents
from pos.shared_ui.widgets.toast import show_toast


class CashRegisterView(QWidget):
    def __init__(self, view_model: CashRegisterViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._registers: list[CashRegisterDTO] = []
        self._users: list[UserDTO] = []
        self._current_session: CashSessionDTO | None = None
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll_area, layout = build_scrollable_page(self)
        outer.addWidget(scroll_area)
        title = make_section_title("Caja")
        layout.addWidget(title)

        self._register_combo = QComboBox(self)
        layout.addWidget(self._register_combo)

        user_row = QHBoxLayout()
        user_row.addWidget(QLabel("Usuario que opera el turno:"))
        self._user_combo = QComboBox(self)
        user_row.addWidget(self._user_combo)
        layout.addLayout(user_row)

        self._status_label = QLabel("Sin turno abierto.")
        layout.addWidget(self._status_label)

        session_actions = QHBoxLayout()
        self._open_button = QPushButton("Abrir turno")
        self._close_button = QPushButton("Cerrar turno")
        session_actions.addWidget(self._open_button)
        session_actions.addWidget(self._close_button)
        layout.addLayout(session_actions)

        movement_actions = QHBoxLayout()
        self._income_button = QPushButton("Ingreso manual")
        self._expense_button = QPushButton("Egreso manual")
        movement_actions.addWidget(self._income_button)
        movement_actions.addWidget(self._expense_button)
        layout.addLayout(movement_actions)

        layout.addWidget(QLabel("Movimientos del turno:"))
        self._movements_list = QListWidget(self)
        layout.addWidget(self._movements_list)

    def _connect_signals(self) -> None:
        self._register_combo.currentIndexChanged.connect(self._on_register_selected)
        self._open_button.clicked.connect(self._on_open_clicked)
        self._close_button.clicked.connect(self._on_close_clicked)
        self._income_button.clicked.connect(
            lambda: self._on_movement_clicked(CashMovementType.MANUAL_IN)
        )
        self._expense_button.clicked.connect(
            lambda: self._on_movement_clicked(CashMovementType.MANUAL_OUT)
        )
        self._view_model.registers_loaded.connect(self._on_registers_loaded)
        self._view_model.users_loaded.connect(self._on_users_loaded)
        self._view_model.session_changed.connect(self._on_session_changed)
        self._view_model.movements_loaded.connect(self._on_movements_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_registers_loaded(self, registers: list[CashRegisterDTO]) -> None:
        self._registers = registers
        self._register_combo.clear()
        for register in registers:
            self._register_combo.addItem(register.name, userData=register.id)
        if registers:
            self._view_model.select_register(registers[0].id)

    def _on_register_selected(self, index: int) -> None:
        register_id = self._register_combo.currentData()
        if register_id is not None:
            self._view_model.select_register(register_id)

    def _on_users_loaded(self, users: list[UserDTO]) -> None:
        self._users = users
        self._user_combo.clear()
        for user in users:
            self._user_combo.addItem(user.full_name, userData=user.id)

    def _user_name_by_id(self, user_id: int) -> str | None:
        return next((user.full_name for user in self._users if user.id == user_id), None)

    def _on_session_changed(self, cash_session: CashSessionDTO | None) -> None:
        self._current_session = cash_session
        if cash_session is None:
            self._status_label.setText("Sin turno abierto.")
        else:
            register_name = self._register_combo.currentText()
            operator_name = self._user_name_by_id(cash_session.opened_by_user_id)
            header = f"{register_name} — {operator_name}" if operator_name else register_name
            self._status_label.setText(
                f"{header}\n"
                f"Turno abierto desde {cash_session.opened_at:%Y-%m-%d %H:%M} "
                f"con apertura de {format_currency(cash_session.opening_amount)}."
            )

    def _on_movements_loaded(self, movements: list[CashMovementDTO]) -> None:
        self._movements_list.clear()
        for movement in movements:
            self._movements_list.addItem(
                f"{movement.movement_type.value} — {format_currency(movement.amount)} — "
                f"{movement.reason or ''}"
            )
        fit_list_to_contents(self._movements_list)

    def _ask_amount(self, title: str, label: str) -> Decimal | None:
        text, accepted = QInputDialog.getText(self, title, label)
        if not accepted:
            return None
        try:
            return Decimal(text)
        except InvalidOperation:
            self._show_error("El monto debe ser un número válido.")
            return None

    def _on_open_clicked(self) -> None:
        user_id = self._user_combo.currentData()
        if user_id is None:
            self._show_error("Selecciona qué usuario va a operar esta caja.")
            return
        amount = self._ask_amount("Abrir turno", "Monto de apertura:")
        if amount is not None:
            self._view_model.open_session(amount, user_id)

    def _on_close_clicked(self) -> None:
        amount = self._ask_amount("Cerrar turno", "Monto contado en caja:")
        if amount is not None:
            self._view_model.close_session(amount)

    def _on_movement_clicked(self, movement_type: CashMovementType) -> None:
        amount = self._ask_amount("Monto", "Monto del movimiento:")
        if amount is None:
            return
        reason, _ = QInputDialog.getText(self, "Motivo", "Motivo (opcional):")
        self._view_model.register_movement(movement_type, amount, reason)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        show_toast(self, message)
