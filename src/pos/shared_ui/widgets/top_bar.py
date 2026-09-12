"""Barra superior del Dashboard principal: identidad del sistema, usuario
conectado, fecha/hora en vivo, campana de despachos pendientes y menú de
usuario."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pos.shared_ui.icons import DEFAULT_ICON_SIZE, get_icon
from pos.shared_ui.theme.elevation import apply_shadow
from pos.shared_ui.theme.spacing import SPACING_LG, SPACING_MD, SPACING_SM, SPACING_XS
from pos.shared_ui.theme.theme_manager import get_active_tokens
from pos.shared_ui.widgets.icon_badge import build_icon_badge
from pos.shared_ui.widgets.section_title import make_section_title

_WEEKDAYS_ES = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo",
}
_MONTHS_ES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


def _format_datetime_es(moment: datetime) -> str:
    """`strftime("%A")`/`"%B"` dependen del locale del sistema operativo, que
    normalmente viene en inglés — se arma el texto a mano para que siempre
    salga en español sin importar el locale de la máquina. Formato de 24
    horas, igual al resto de la app (ver `sale_view.py`, `reports_view_model.py`)."""
    weekday = _WEEKDAYS_ES[moment.weekday()]
    month = _MONTHS_ES[moment.month]
    return f"{weekday} {moment.day} de {month} de {moment.year}, {moment:%H:%M}"


class _DispatchBellButton(QFrame):
    """Campana de despachos pendientes: ícono grande + distintivo circular
    con la cantidad, agrupados como una sola unidad clicable. Dedicada
    exclusivamente a Despacho — no conoce cajas, backups, licencia,
    sincronización ni el sistema de notificaciones genérico."""

    def __init__(
        self, on_open_dispatch: Callable[[], None] | None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._on_open_dispatch = on_open_dispatch
        self.setObjectName("surface")
        """Mismo chip redondeado que el resto de "superficies" de la app
        (`QFrame#surface`, ver `theme_manager.py`) — antes era transparente,
        sin ningún contorno que la distinguiera del resto de la barra."""
        apply_shadow(self, "sm", glow_color=get_active_tokens().primary)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING_SM, SPACING_XS, SPACING_SM, SPACING_XS)
        layout.setSpacing(SPACING_XS)

        self._button = QToolButton(self)
        self._button.setIcon(get_icon("bell", get_active_tokens().text_primary, size=24))
        self._button.setIconSize(QSize(24, 24))
        self._button.setToolTip("Despachos pendientes")
        self._button.setStyleSheet(
            "QToolButton { border: none; background: transparent; padding: 0; }"
        )
        self._button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._menu = QMenu(self._button)
        self._button.setMenu(self._menu)
        layout.addWidget(self._button)

        self._badge = QLabel("0", self)
        self._badge.setObjectName("dispatchBadge")
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setFixedHeight(30)
        self._badge.setMinimumWidth(30)
        layout.addWidget(self._badge)

        self.set_pending_dispatch_count(0)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._button.showMenu()
        super().mousePressEvent(event)

    def set_pending_dispatch_count(self, count: int) -> None:
        self._badge.setText(str(count))
        self._menu.clear()
        if count > 0:
            self._menu.addAction("Despachos pendientes").setEnabled(False)
            self._menu.addAction(f"Cantidad: {count}").setEnabled(False)
            if self._on_open_dispatch is not None:
                self._menu.addSeparator()
                self._menu.addAction("Abrir Despacho").triggered.connect(self._on_open_dispatch)
        else:
            self._menu.addAction("No hay despachos pendientes.").setEnabled(False)


class TopBar(QFrame):
    def __init__(
        self,
        system_name: str,
        greeting: str,
        role_label: str,
        branch_label: str,
        on_logout: Callable[[], None],
        on_open_dispatch: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("surface")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING_LG, SPACING_SM, SPACING_LG, SPACING_SM)
        layout.setSpacing(SPACING_MD)

        tokens = get_active_tokens()
        brand_badge = build_icon_badge(
            "package", tokens.primary, tokens.header_accent, size=32, parent=self
        )
        layout.addWidget(brand_badge)

        identity_layout = QVBoxLayout()
        identity_layout.setSpacing(SPACING_XS)

        system_label = make_section_title(system_name, self)
        identity_layout.addWidget(system_label)

        subtitle_label = QLabel(f"{greeting} · {role_label} · {branch_label}", self)
        subtitle_label.setProperty("role", "secondary")
        identity_layout.addWidget(subtitle_label)

        layout.addLayout(identity_layout)
        layout.addStretch()

        self._datetime_label = QLabel(self)
        self._datetime_label.setProperty("role", "secondary")
        self._datetime_label.setProperty("emphasis", True)
        self._datetime_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self._datetime_label)
        self._update_datetime()
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_datetime)
        self._clock_timer.start(30_000)

        self._dispatch_bell = _DispatchBellButton(on_open_dispatch, self)
        layout.addWidget(self._dispatch_bell)

        user_button = QToolButton(self)
        user_button.setText(role_label)
        user_button.setIcon(get_icon("user", get_active_tokens().text_primary))
        user_button.setIconSize(QSize(DEFAULT_ICON_SIZE, DEFAULT_ICON_SIZE))
        user_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        user_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        user_button.setStyleSheet(
            "QToolButton { border: none; background: transparent; padding: 0; }"
        )
        user_menu = QMenu(user_button)
        logout_action = user_menu.addAction("Cerrar sesión")
        logout_action.triggered.connect(on_logout)
        user_button.setMenu(user_menu)

        user_chip = QFrame(self)
        user_chip.setObjectName("surface")
        """Mismo chip que `_DispatchBellButton` — antes el botón de usuario
        era el único elemento de la barra sin ningún contorno propio."""
        apply_shadow(user_chip, "sm", glow_color=tokens.primary)
        user_chip_layout = QHBoxLayout(user_chip)
        user_chip_layout.setContentsMargins(SPACING_SM, SPACING_XS, SPACING_SM, SPACING_XS)
        user_chip_layout.addWidget(user_button)
        layout.addWidget(user_chip)

    def _update_datetime(self) -> None:
        self._datetime_label.setText(_format_datetime_es(datetime.now()))

    def set_pending_dispatch_count(self, count: int) -> None:
        self._dispatch_bell.set_pending_dispatch_count(count)
