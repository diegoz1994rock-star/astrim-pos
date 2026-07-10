"""Pantalla de configuración inicial: se muestra en vez del login cuando la
base de datos está recién creada (cero usuarios) — crea la cuenta de
administrador y, opcionalmente, el nombre del negocio."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pos.core.security.session import ActiveSession
from pos.modules.users.presentation.first_run_setup_view_model import FirstRunSetupViewModel


class FirstRunSetupView(QWidget):
    setup_completed = Signal(object)

    def __init__(
        self, view_model: FirstRunSetupViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame(self)
        card.setObjectName("surface")
        card.setFixedWidth(420)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)
        card_layout.setContentsMargins(32, 32, 32, 32)

        title = QLabel("Bienvenido — configuración inicial", card)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = title.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setWordWrap(True)
        title.setFixedWidth(356)

        subtitle = QLabel(
            "Es la primera vez que arranca el sistema. Crea la cuenta del "
            "administrador para empezar a usarlo.",
            card,
        )
        subtitle.setWordWrap(True)
        subtitle.setFixedWidth(356)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._business_name_edit = QLineEdit(card)
        self._business_name_edit.setPlaceholderText("Nombre del negocio (opcional)")

        self._username_edit = QLineEdit(card)
        self._username_edit.setPlaceholderText("Usuario del administrador")

        self._full_name_edit = QLineEdit(card)
        self._full_name_edit.setPlaceholderText("Nombre completo")

        self._password_edit = QLineEdit(card)
        self._password_edit.setPlaceholderText("Contraseña (mínimo 8 caracteres)")
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self._password_confirm_edit = QLineEdit(card)
        self._password_confirm_edit.setPlaceholderText("Confirmar contraseña")
        self._password_confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_confirm_edit.returnPressed.connect(self._on_start_clicked)

        self._error_label = QLabel(card)
        self._error_label.setProperty("role", "danger")
        self._error_label.setWordWrap(True)
        self._error_label.setFixedWidth(356)
        self._error_label.setVisible(False)

        self._start_button = QPushButton("Comenzar", card)
        self._start_button.setDefault(True)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addWidget(self._business_name_edit)
        card_layout.addWidget(self._username_edit)
        card_layout.addWidget(self._full_name_edit)
        card_layout.addWidget(self._password_edit)
        card_layout.addWidget(self._password_confirm_edit)
        card_layout.addWidget(self._error_label)
        card_layout.addWidget(self._start_button)

        outer_layout.addWidget(card)

    def _connect_signals(self) -> None:
        self._start_button.clicked.connect(self._on_start_clicked)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.setup_completed.connect(self._on_setup_completed)

    def _on_start_clicked(self) -> None:
        self._error_label.setVisible(False)
        self._view_model.complete_setup(
            business_name=self._business_name_edit.text(),
            admin_username=self._username_edit.text(),
            admin_full_name=self._full_name_edit.text(),
            admin_password=self._password_edit.text(),
            admin_password_confirm=self._password_confirm_edit.text(),
        )

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    def _on_setup_completed(self, session: ActiveSession) -> None:
        self.setup_completed.emit(session)
