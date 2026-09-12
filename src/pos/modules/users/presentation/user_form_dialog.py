"""Diálogo de creación/edición de usuario."""

from __future__ import annotations

import shutil
import tempfile

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pos.core.exceptions import DomainError
from pos.modules.job_positions.application.dto import JobAreaDTO
from pos.modules.users.application.dto import UserDocumentDTO, UserDTO
from pos.modules.users.presentation.photo_crop_dialog import PhotoCropDialog
from pos.modules.users.presentation.users_view_model import UsersViewModel

_NO_AREA_LABEL = "(sin área)"
_NO_POSITION_LABEL = "(sin cargo)"
_PHOTO_PREVIEW_SIZE = 96
_IMAGE_FILTER = "Imágenes (*.png *.jpg *.jpeg)"
_ANY_FILE_FILTER = "Todos los archivos (*)"
_DOCUMENT_ROLE = Qt.ItemDataRole.UserRole
_MIN_PASSWORD_LENGTH = 8


def _error_label() -> QLabel:
    label = QLabel("")
    label.setProperty("role", "danger")
    label.setWordWrap(True)
    label.setVisible(False)
    return label


class UserFormDialog(QDialog):
    """Formulario modal para crear un usuario nuevo o editar uno
    existente (si se pasa `existing_user`).

    Los errores de validación (de forma o del servidor, ej. usuario
    duplicado) se muestran junto al campo correspondiente sin cerrar el
    diálogo ni perder lo ya escrito — ver `_on_accept_clicked`."""

    def __init__(
        self,
        areas: list[JobAreaDTO],
        view_model: UsersViewModel,
        existing_user: UserDTO | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._areas = areas
        self._view_model = view_model
        self._existing_user = existing_user
        self._photo_source_path: str | None = None
        self.setWindowTitle("Editar usuario" if existing_user else "Nuevo usuario")
        self.resize(720, 600)

        self._build_ui()
        if existing_user is not None:
            self._load_existing_user(existing_user)
            self._reload_documents()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)

        root_layout.addWidget(self._build_photo_section())

        self._form_error = _error_label()
        root_layout.addWidget(self._form_error)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content = QWidget()
        grid = QGridLayout(content)
        grid.addWidget(self._build_access_section(), 0, 0)
        grid.addWidget(self._build_organization_section(), 0, 1)
        grid.addWidget(self._build_personal_section(), 1, 0, 1, 2)
        if self._existing_user is not None:
            grid.addWidget(self._build_documents_section(), 2, 0, 1, 2)
        content.setMinimumWidth(680)

        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self._on_accept_clicked)
        buttons.rejected.connect(self.reject)
        root_layout.addWidget(buttons)

    def _build_photo_section(self) -> QWidget:
        self._photo_preview = QLabel(self)
        self._photo_preview.setFixedSize(_PHOTO_PREVIEW_SIZE, _PHOTO_PREVIEW_SIZE)
        self._photo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._photo_preview.setText("Sin foto")
        self._photo_button = QPushButton("Seleccionar foto", self)
        self._photo_button.clicked.connect(self._on_select_photo_clicked)

        row = QHBoxLayout()
        row.addWidget(self._photo_preview)
        row.addWidget(self._photo_button)
        row.addStretch()
        container = QWidget(self)
        container.setLayout(row)
        return container

    def _build_access_section(self) -> QGroupBox:
        group = QGroupBox("Datos de acceso", self)
        form = QFormLayout(group)
        self._username_edit = QLineEdit(self)
        self._username_error = _error_label()
        form.addRow("Usuario", self._username_edit)
        form.addRow("", self._username_error)
        if self._existing_user is None:
            self._password_edit = QLineEdit(self)
            self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._password_error = _error_label()
            form.addRow("Contraseña", self._password_edit)
            form.addRow("", self._password_error)
        return group

    def _build_personal_section(self) -> QGroupBox:
        group = QGroupBox("Datos personales", self)
        form = QFormLayout(group)
        self._full_name_edit = QLineEdit(self)
        self._full_name_error = _error_label()
        self._email_edit = QLineEdit(self)
        self._email_error = _error_label()
        self._phone_edit = QLineEdit(self)
        self._phone_error = _error_label()
        self._emergency_phone_edit = QLineEdit(self)
        self._emergency_phone_error = _error_label()
        self._blood_type_edit = QLineEdit(self)
        self._blood_type_error = _error_label()
        self._address_edit = QLineEdit(self)
        self._address_error = _error_label()
        form.addRow("Nombre completo", self._full_name_edit)
        form.addRow("", self._full_name_error)
        form.addRow("Correo", self._email_edit)
        form.addRow("", self._email_error)
        form.addRow("Teléfono", self._phone_edit)
        form.addRow("", self._phone_error)
        form.addRow("Teléfono de emergencia", self._emergency_phone_edit)
        form.addRow("", self._emergency_phone_error)
        form.addRow("RH", self._blood_type_edit)
        form.addRow("", self._blood_type_error)
        form.addRow("Dirección", self._address_edit)
        form.addRow("", self._address_error)
        return group

    def _build_organization_section(self) -> QGroupBox:
        group = QGroupBox("Organización", self)
        form = QFormLayout(group)

        self._area_combo = QComboBox(self)
        self._area_combo.addItem(_NO_AREA_LABEL, userData=None)
        for area in self._areas:
            self._area_combo.addItem(area.name, userData=area.id)
        self._area_combo.currentIndexChanged.connect(self._on_area_changed)

        self._position_combo = QComboBox(self)
        self._populate_positions(None)
        self._organization_error = _error_label()

        form.addRow("Área", self._area_combo)
        form.addRow("Cargo", self._position_combo)
        form.addRow("", self._organization_error)
        return group

    def _build_documents_section(self) -> QGroupBox:
        group = QGroupBox("Documentos adjuntos", self)
        layout = QVBoxLayout(group)

        self._documents_list = QListWidget(self)
        self._documents_list.setMaximumHeight(160)
        layout.addWidget(self._documents_list)

        buttons = QHBoxLayout()
        self._attach_button = QPushButton("Adjuntar archivo", self)
        self._download_button = QPushButton("Descargar", self)
        self._delete_document_button = QPushButton("Eliminar", self)
        self._attach_button.clicked.connect(self._on_attach_clicked)
        self._download_button.clicked.connect(self._on_download_clicked)
        self._delete_document_button.clicked.connect(self._on_delete_document_clicked)
        buttons.addWidget(self._attach_button)
        buttons.addWidget(self._download_button)
        buttons.addWidget(self._delete_document_button)
        layout.addLayout(buttons)
        return group

    def _load_existing_user(self, user: UserDTO) -> None:
        self._username_edit.setText(user.username)
        self._full_name_edit.setText(user.full_name)
        self._email_edit.setText(user.email or "")
        self._phone_edit.setText(user.phone or "")
        self._emergency_phone_edit.setText(user.emergency_phone or "")
        self._blood_type_edit.setText(user.blood_type or "")
        self._address_edit.setText(user.address or "")

        area_index = self._area_combo.findData(user.job_area_id)
        if area_index >= 0:
            self._area_combo.setCurrentIndex(area_index)
        position_index = self._position_combo.findData(user.job_position_id)
        if position_index >= 0:
            self._position_combo.setCurrentIndex(position_index)

        if user.photo_path:
            self._set_photo_preview(QPixmap(user.photo_path))

    def _on_area_changed(self) -> None:
        self._populate_positions(self._area_combo.currentData())

    def _populate_positions(self, area_id: int | None) -> None:
        self._position_combo.clear()
        self._position_combo.addItem(_NO_POSITION_LABEL, userData=None)
        area = next((a for a in self._areas if a.id == area_id), None)
        self._position_combo.setEnabled(area is not None)
        if area is None:
            return
        for position in area.positions:
            self._position_combo.addItem(position.name, userData=position.id)

    def _set_photo_preview(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        scaled = pixmap.scaled(
            _PHOTO_PREVIEW_SIZE,
            _PHOTO_PREVIEW_SIZE,
            aspectMode=Qt.AspectRatioMode.KeepAspectRatio,
            mode=Qt.TransformationMode.SmoothTransformation,
        )
        self._photo_preview.setText("")
        self._photo_preview.setPixmap(scaled)

    def _on_select_photo_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar foto", "", _IMAGE_FILTER)
        if not path:
            return

        crop_dialog = PhotoCropDialog(path, self)
        if crop_dialog.exec() != PhotoCropDialog.DialogCode.Accepted:
            return
        cropped = crop_dialog.cropped_image()
        if cropped is None:
            return

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
            temp_path = temp_file.name
        cropped.save(temp_path, "JPG", 90)

        self._photo_source_path = temp_path
        self._set_photo_preview(QPixmap.fromImage(cropped))

    def _reload_documents(self) -> None:
        assert self._existing_user is not None
        try:
            documents = self._view_model.list_documents(self._existing_user.id)
        except DomainError as error:
            self._show_error(str(error))
            return
        self._documents_list.clear()
        for document in documents:
            item = QListWidgetItem(document.original_filename)
            item.setData(_DOCUMENT_ROLE, document)
            self._documents_list.addItem(item)

    def _selected_document(self) -> UserDocumentDTO | None:
        item = self._documents_list.currentItem()
        if item is None:
            return None
        return item.data(_DOCUMENT_ROLE)

    def _on_attach_clicked(self) -> None:
        assert self._existing_user is not None
        path, _ = QFileDialog.getOpenFileName(self, "Adjuntar archivo", "", _ANY_FILE_FILTER)
        if not path:
            return
        try:
            self._view_model.add_document(self._existing_user.id, path)
        except DomainError as error:
            self._show_error(str(error))
            return
        self._reload_documents()

    def _on_download_clicked(self) -> None:
        document = self._selected_document()
        if document is None:
            self._show_error("Selecciona un archivo de la lista.")
            return
        destination, _ = QFileDialog.getSaveFileName(
            self, "Guardar como", document.original_filename
        )
        if not destination:
            return
        try:
            shutil.copy2(document.stored_path, destination)
        except OSError as error:
            self._show_error(f"No se pudo guardar el archivo: {error}")

    def _on_delete_document_clicked(self) -> None:
        document = self._selected_document()
        if document is None:
            self._show_error("Selecciona un archivo de la lista.")
            return
        confirmation = QMessageBox.question(
            self, "Eliminar archivo", f"¿Eliminar '{document.original_filename}'?"
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        try:
            self._view_model.delete_document(document.id)
        except DomainError as error:
            self._show_error(str(error))
            return
        self._reload_documents()

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _clear_field_errors(self) -> None:
        self._form_error.setVisible(False)
        self._username_error.setVisible(False)
        if self._existing_user is None:
            self._password_error.setVisible(False)
        self._full_name_error.setVisible(False)
        self._email_error.setVisible(False)
        self._phone_error.setVisible(False)
        self._emergency_phone_error.setVisible(False)
        self._blood_type_error.setVisible(False)
        self._address_error.setVisible(False)
        self._organization_error.setVisible(False)

    def _set_field_error(self, label: QLabel, message: str) -> None:
        label.setText(message)
        label.setVisible(True)

    def _validate_client_side(self) -> bool:
        """Validaciones de forma que no requieren consultar el servidor
        (campos obligatorios, largo mínimo de contraseña) — se muestran
        junto al campo correspondiente antes de siquiera llamar al
        servicio."""
        is_valid = True
        if not self._username_edit.text().strip():
            self._set_field_error(self._username_error, "El usuario es obligatorio.")
            is_valid = False
        if not self._full_name_edit.text().strip():
            self._set_field_error(self._full_name_error, "El nombre completo es obligatorio.")
            is_valid = False
        if self._existing_user is None and len(self._password_edit.text()) < _MIN_PASSWORD_LENGTH:
            self._set_field_error(
                self._password_error,
                f"La contraseña debe tener al menos {_MIN_PASSWORD_LENGTH} caracteres.",
            )
            is_valid = False
        if not self._email_edit.text().strip():
            self._set_field_error(self._email_error, "El correo es obligatorio.")
            is_valid = False
        if not self._phone_edit.text().strip():
            self._set_field_error(self._phone_error, "El teléfono es obligatorio.")
            is_valid = False
        if not self._emergency_phone_edit.text().strip():
            self._set_field_error(
                self._emergency_phone_error, "El teléfono de emergencia es obligatorio."
            )
            is_valid = False
        if not self._blood_type_edit.text().strip():
            self._set_field_error(self._blood_type_error, "El RH es obligatorio.")
            is_valid = False
        if not self._address_edit.text().strip():
            self._set_field_error(self._address_error, "La dirección es obligatoria.")
            is_valid = False
        return is_valid

    def _route_server_error(self, message: str) -> None:
        """Los mensajes de error del servicio son texto libre, no vienen
        atados a un campo — se enrutan por contenido al campo más
        probable; si no calza con ninguno conocido, se muestra un mensaje
        general arriba del formulario, nunca se pierde silenciosamente."""
        lowered = message.lower()
        if "contraseña" in lowered:
            self._set_field_error(self._password_error, message)
        elif "nombre de usuario" in lowered or "usuario" in lowered:
            self._set_field_error(self._username_error, message)
        elif "nombre completo" in lowered:
            self._set_field_error(self._full_name_error, message)
        elif "correo" in lowered or "email" in lowered:
            self._set_field_error(self._email_error, message)
        elif "cargo" in lowered or "área" in lowered:
            self._set_field_error(self._organization_error, message)
        else:
            self._set_field_error(self._form_error, message)

    def _on_accept_clicked(self) -> None:
        self._clear_field_errors()
        if not self._validate_client_side():
            return

        try:
            if self._existing_user is None:
                self._view_model.create_user(**self.values())  # type: ignore[arg-type]
            else:
                self._view_model.update_user(
                    self._existing_user.id, **self.values()  # type: ignore[arg-type]
                )
        except DomainError as error:
            self._route_server_error(str(error))
            return

        self.accept()

    def values(self) -> dict[str, str | int | None]:
        """Datos ingresados, listos para pasar a `UsersViewModel.create_user`
        o `update_user` (esta última no espera `password`)."""
        values: dict[str, str | int | None] = {
            "username": self._username_edit.text().strip(),
            "full_name": self._full_name_edit.text().strip(),
            "email": self._email_edit.text().strip(),
            "phone": self._phone_edit.text().strip(),
            "emergency_phone": self._emergency_phone_edit.text().strip(),
            "blood_type": self._blood_type_edit.text().strip(),
            "address": self._address_edit.text().strip(),
            "photo_source_path": self._photo_source_path,
            "job_area_id": self._area_combo.currentData(),
            "job_position_id": self._position_combo.currentData(),
        }
        if self._existing_user is None:
            values["password"] = self._password_edit.text()
        return values
