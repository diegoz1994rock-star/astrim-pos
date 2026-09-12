"""Insignia circular de ícono (fondo tenue + ícono centrado) — extraída como
helper porque la necesitan dos componentes distintos del Dashboard
(`KpiCard` y las tarjetas de acceso rápido, ver `quick_access_panel.py`),
mismo criterio de unificación que `success_tint`/`warning_tint`/
`danger_tint` (DESIGN_SYSTEM.md §12)."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from pos.shared_ui.icons import get_icon


def build_icon_badge(
    icon_name: str, accent_hex: str, tint_hex: str, size: int = 40, parent: QWidget | None = None
) -> QFrame:
    """Círculo de diámetro `size` con fondo `tint_hex` (tenue) e ícono
    `icon_name` coloreado `accent_hex` centrado — mismo ícono/color que ya
    usa el resto de la tarjeta/tarjeta de acceso, sin definir un color nuevo."""
    badge = QFrame(parent)
    badge.setFixedSize(size, size)
    badge.setStyleSheet(
        f"QFrame {{ background-color: {tint_hex}; border-radius: {size // 2}px; border: none; }}"
    )
    layout = QVBoxLayout(badge)
    layout.setContentsMargins(0, 0, 0, 0)
    icon_size = round(size * 0.5)
    icon_label = QLabel(badge)
    icon = get_icon(icon_name, accent_hex, size=icon_size)
    icon_label.setPixmap(icon.pixmap(icon_size, icon_size))
    icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon_label.setFixedSize(QSize(icon_size, icon_size))
    layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
    return badge
