"""Indicador visual de estado (ej. conexión de un dispositivo), reusado por
los módulos de Administración → Dispositivos (Báscula electrónica,
Impresoras, Cajón monedero, Lectores de códigos de barras).

Se renderiza como chip relleno (fondo `*_tint` + texto de color, ver
DESIGN_SYSTEM.md §4/§7): el selector `QLabel[badge="true"][role=...]` en
`shared_ui/theme/theme_manager.py` es distinto del `QLabel[role=...]` plano
que usan los textos comunes — así una etiqueta de estado se distingue de un
texto auxiliar cualquiera sin afectar los ~20 sitios que ya usan `role=` solo
para color de texto. Cada módulo mapea su propio enum de estado (ej.
`ConnectionStatus.CONNECTED`) a un `role` en su capa de presentación; este
widget no conoce ningún dominio de negocio."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget


class StatusBadge(QWidget):
    def __init__(
        self,
        text: str = "",
        role: str = "secondary",
        *,
        emphasis: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel(self)
        self._label.setProperty("badge", True)
        self._label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        """Sin esto, una tabla con la columna "Estado" en modo `Stretch`
        (ej. `cash_registers_view.py`, con solo 2 columnas) estira el chip
        a lo ancho de toda la celda — se ve como un rectángulo relleno en
        vez de una píldora compacta. El `addStretch()` de abajo lo alinea
        a la izquierda dentro de esa celda ancha."""
        if emphasis:
            self._label.setProperty("emphasis", True)
        layout.addWidget(self._label)
        layout.addStretch(1)
        self.set_status(text, role)

    def set_status(self, text: str, role: str) -> None:
        self._label.setText(f"● {text}" if text else "")
        self._label.setProperty("role", role)
        # `role` ya tenía un valor aplicado por el QSS desde la construcción
        # — Qt no vuelve a evaluar el stylesheet de un widget ya polished
        # solo porque cambió una property, hay que forzarlo explícitamente.
        style = self._label.style()
        style.unpolish(self._label)
        style.polish(self._label)
