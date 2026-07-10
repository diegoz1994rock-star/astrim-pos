"""Pantalla de licencia: estado actual, huella de hardware y activación.

Se usa tanto como panel de administración (para revisar/renovar la
licencia) como pantalla de bloqueo elegante cuando la licencia no es
válida (PROJECT_SPEC.md, "LICENCIAS": bloquear acceso de forma elegante y
mostrar mensaje para contactar al proveedor)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pos.modules.licensing.application.dto import LicenseVerificationDTO
from pos.modules.licensing.domain.enums import LicenseVerificationResult
from pos.modules.licensing.presentation.license_view_model import LicenseViewModel

_STATUS_MESSAGES = {
    LicenseVerificationResult.VALID: "Licencia activa y vigente.",
    LicenseVerificationResult.EXPIRED: (
        "Tu licencia expiró. Contacta al proveedor para renovarla."
    ),
    LicenseVerificationResult.INVALID_SIGNATURE: (
        "La licencia activada no es válida. Contacta al proveedor."
    ),
    LicenseVerificationResult.HARDWARE_MISMATCH: (
        "Esta licencia pertenece a otro equipo. Contacta al proveedor."
    ),
    LicenseVerificationResult.CLOCK_TAMPERING_DETECTED: (
        "Se detectó un cambio inusual en la fecha del sistema. "
        "Verifica la hora de tu equipo o contacta al proveedor."
    ),
}


class LicenseView(QWidget):
    def __init__(self, view_model: LicenseViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._build_ui()
        self._connect_signals()
        self._view_model.refresh()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card_width = 420
        card_margin = 32
        content_width = card_width - 2 * card_margin
        # QLabel con word-wrap dentro de un QVBoxLayout no calcula bien su
        # alto (`heightForWidth`) hasta que se le da un ancho explícito —
        # sin esto, dos labels multilínea seguidos se superponen visualmente
        # (bug real detectado en verificación manual con capturas).

        card = QFrame(self)
        card.setObjectName("surface")
        card.setFixedWidth(card_width)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)
        card_layout.setContentsMargins(card_margin, card_margin, card_margin, card_margin)

        title = QLabel("Licencia", card)
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(16)
        title.setFont(title_font)
        card_layout.addWidget(title)

        self._status_label = QLabel(card)
        self._status_label.setWordWrap(True)
        self._status_label.setFixedWidth(content_width)
        card_layout.addWidget(self._status_label)

        fingerprint_instructions = QLabel(
            "Identificador de este equipo (envíalo al proveedor para activar):", card
        )
        fingerprint_instructions.setWordWrap(True)
        fingerprint_instructions.setFixedWidth(content_width)
        fingerprint_instructions.setProperty("role", "secondary")
        card_layout.addWidget(fingerprint_instructions)

        fingerprint_field = QLineEdit(self._view_model.hardware_fingerprint, card)
        fingerprint_field.setReadOnly(True)
        fingerprint_field.setCursorPosition(0)
        card_layout.addWidget(fingerprint_field)

        self._license_key_edit = QLineEdit(card)
        self._license_key_edit.setPlaceholderText("Pega aquí tu clave de licencia")
        card_layout.addWidget(self._license_key_edit)

        self._activate_button = QPushButton("Activar licencia", card)
        card_layout.addWidget(self._activate_button)

        outer_layout.addWidget(card)

    def _connect_signals(self) -> None:
        self._activate_button.clicked.connect(self._on_activate_clicked)
        self._view_model.status_changed.connect(self._on_status_changed)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_status_changed(self, verification: LicenseVerificationDTO) -> None:
        message = _STATUS_MESSAGES.get(verification.result, verification.details or "")
        if verification.license is not None:
            message += f"\nTipo: {verification.license.license_type.value}"
            if verification.license.expires_at is not None:
                message += f" — vence: {verification.license.expires_at:%Y-%m-%d}"
        self._status_label.setText(message)

    def _on_activate_clicked(self) -> None:
        self._view_model.activate(self._license_key_edit.text())
        self._license_key_edit.clear()

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        QMessageBox.information(self, "Listo", message)
