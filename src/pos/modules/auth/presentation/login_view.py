"""Pantalla de inicio de sesión.

Pensada para pantallas táctiles: campos y botón con alto mínimo generoso
(ver `shared_ui.theme.tokens.ThemeTokens.touch_control_min_height_px`) y
sin depender de hover para ninguna acción.
"""

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
from pos.modules.auth.presentation.login_view_model import LoginViewModel


class LoginView(QWidget):
    """Vista de login: username, contraseña, botón de acceso y mensaje de error."""

    authenticated = Signal(object)
    """Reemite `ActiveSession` hacia quien cablea esta vista (ej. `main.py`),
    para que decida qué pantalla mostrar a continuación sin que esta vista
    conozca el resto de la aplicación."""

    def __init__(self, view_model: LoginViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame(self)
        card.setObjectName("surface")
        card.setFixedWidth(360)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)
        card_layout.setContentsMargins(32, 32, 32, 32)

        title = QLabel("Sistema POS", card)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = title.font()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)

        self._username_edit = QLineEdit(card)
        self._username_edit.setPlaceholderText("Usuario")

        self._password_edit = QLineEdit(card)
        self._password_edit.setPlaceholderText("Contraseña")
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.returnPressed.connect(self._on_login_clicked)

        self._error_label = QLabel(card)
        self._error_label.setProperty("role", "danger")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)

        self._login_button = QPushButton("Iniciar sesión", card)
        self._login_button.setDefault(True)

        card_layout.addWidget(title)
        card_layout.addWidget(self._username_edit)
        card_layout.addWidget(self._password_edit)
        card_layout.addWidget(self._error_label)
        card_layout.addWidget(self._login_button)

        outer_layout.addWidget(card)

    def _connect_signals(self) -> None:
        self._login_button.clicked.connect(self._on_login_clicked)
        self._view_model.login_failed.connect(self._show_error)
        self._view_model.login_succeeded.connect(self._on_login_succeeded)

    def _on_login_clicked(self) -> None:
        self._error_label.setVisible(False)
        self._view_model.attempt_login(self._username_edit.text(), self._password_edit.text())

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)
        self._password_edit.clear()
        self._password_edit.setFocus()

    def _on_login_succeeded(self, session: ActiveSession) -> None:
        self._username_edit.clear()
        self._password_edit.clear()
        self._error_label.setVisible(False)
        self.authenticated.emit(session)
