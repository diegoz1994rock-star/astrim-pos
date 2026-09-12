"""Diálogo "Programación de Backups Automáticos".

Reemplaza la vieja entrada de expresión cron en texto libre por 4 opciones
de frecuencia (botones de radio) y, cuando aplica, un horario elegido con
dos `QSpinBox` — nunca un campo de texto. El usuario jamás ve ni escribe
cron; la traducción a cron ocurre en `application/schedule_translator.py`.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pos.modules.backups.domain.enums import ScheduleFrequency

_FREQUENCY_LABELS: dict[ScheduleFrequency, str] = {
    ScheduleFrequency.HOURLY: "Cada hora",
    ScheduleFrequency.EVERY_SIX_HOURS: "Cada 6 horas",
    ScheduleFrequency.DAILY: "Todos los días",
    ScheduleFrequency.WEEKLY_MONDAY: "Todos los lunes",
}
_TIME_ENABLED_FREQUENCIES = {ScheduleFrequency.DAILY, ScheduleFrequency.WEEKLY_MONDAY}


class ScheduleBackupDialog(QDialog):
    def __init__(
        self,
        *,
        initial_frequency: ScheduleFrequency,
        initial_hour: int,
        initial_minute: int,
        initial_backup_on_close: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Programación de Backups Automáticos")

        layout = QVBoxLayout(self)

        explanation = QLabel(
            "Seleccione cada cuánto desea que el sistema cree automáticamente "
            "una copia de seguridad."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self._radio_group = QButtonGroup(self)
        self._radios: dict[ScheduleFrequency, QRadioButton] = {}
        for frequency in ScheduleFrequency:
            radio = QRadioButton(_FREQUENCY_LABELS[frequency])
            self._radio_group.addButton(radio)
            self._radios[frequency] = radio
            layout.addWidget(radio)
            radio.toggled.connect(self._update_time_controls_enabled)
        self._radios[initial_frequency].setChecked(True)

        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("Hora:"))
        self._hour_spin = QSpinBox(self)
        self._hour_spin.setRange(0, 23)
        self._hour_spin.setValue(initial_hour)
        time_row.addWidget(self._hour_spin)
        time_row.addWidget(QLabel("Minutos:"))
        self._minute_spin = QSpinBox(self)
        self._minute_spin.setRange(0, 59)
        self._minute_spin.setValue(initial_minute)
        time_row.addWidget(self._minute_spin)
        time_row.addStretch()
        layout.addLayout(time_row)

        self._backup_on_close_checkbox = QCheckBox(
            "Ejecutar un backup automáticamente al cerrar el sistema"
        )
        self._backup_on_close_checkbox.setChecked(initial_backup_on_close)
        layout.addWidget(self._backup_on_close_checkbox)

        buttons_row = QHBoxLayout()
        self._cancel_button = QPushButton("Cancelar", self)
        self._save_button = QPushButton("Guardar programación", self)
        buttons_row.addWidget(self._cancel_button)
        buttons_row.addWidget(self._save_button)
        layout.addLayout(buttons_row)

        self._cancel_button.clicked.connect(self.reject)
        self._save_button.clicked.connect(self.accept)

        self._update_time_controls_enabled()

    def _update_time_controls_enabled(self) -> None:
        enabled = self.selected_frequency() in _TIME_ENABLED_FREQUENCIES
        self._hour_spin.setEnabled(enabled)
        self._minute_spin.setEnabled(enabled)

    def selected_frequency(self) -> ScheduleFrequency:
        for frequency, radio in self._radios.items():
            if radio.isChecked():
                return frequency
        return ScheduleFrequency.DAILY

    def selected_time(self) -> tuple[int, int]:
        return self._hour_spin.value(), self._minute_spin.value()

    def backup_on_close_enabled(self) -> bool:
        return self._backup_on_close_checkbox.isChecked()
