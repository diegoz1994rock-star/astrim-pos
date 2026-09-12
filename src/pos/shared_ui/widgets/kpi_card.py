"""Tarjeta de indicador (KPI), usada en el Dashboard principal y en varias
pantallas de módulo (Ganancias, Ventas, Backups)."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from pos.shared_ui.theme.elevation import apply_shadow
from pos.shared_ui.theme.spacing import SPACING_MD, SPACING_SM, SPACING_XS
from pos.shared_ui.theme.theme_manager import get_active_tokens
from pos.shared_ui.widgets.icon_badge import build_icon_badge
from pos.shared_ui.widgets.sparkline import Sparkline

_ICON_BADGE_SIZE = 36
_ACCENT_COLOR_FIELDS = {"primary": "primary", "success": "success", "secondary": "text_secondary"}
"""`accent` es un nombre de rol semántico (mismo vocabulario que
`QLabel[role=...]`), no siempre coincide con el nombre del campo en
`ThemeTokens` (`"secondary"` → `text_secondary`, no existe un campo
`secondary`) — este mapa traduce uno al otro."""
_ACCENT_TINTS = {"primary": None, "success": "success_tint", "secondary": None}
"""`None` = sin token `*_tint` propio (`primary`/`secondary` no tienen uno
en `ThemeTokens`) — en ese caso `build_icon_badge` usa `header_accent`, el
mismo neutro ya usado para "superficie tenue" en el resto de la app (headers
de tabla, chip de estado `secondary`, ver Fase 8)."""


class KpiCard(QFrame):
    """Tarjeta con ícono opcional, título, valor destacado, subtítulo y
    variación/tendencia opcionales.

    Reutiliza el selector `QFrame#surface` y la convención
    `QLabel[role="success"|"warning"|"danger"]` ya definidos en
    `shared_ui/theme/theme_manager.py` — no define ningún color propio.
    Elevación `"sm"` (ver `shared_ui/theme/elevation.py`, DESIGN_SYSTEM.md
    §8). `icon`/`accent`/`trend`/`delta_pct` son opcionales y por defecto no
    activan nada nuevo — las ~16 tarjetas de Ganancias/Ventas/Backups que ya
    usan este widget sin esos parámetros se ven exactamente igual que antes;
    solo el Dashboard los usa (ver DESIGN_SYSTEM.md, sección "Tarjeta KPI
    con ícono y tendencia")."""

    def __init__(
        self,
        title: str,
        value: str,
        subtitle: str | None = None,
        value_role: str | None = None,
        *,
        icon: str | None = None,
        accent: str = "secondary",
        trend: list[Decimal] | None = None,
        delta_pct: Decimal | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("surface")
        self.setMinimumWidth(180)
        if icon is not None:
            self.setProperty("accent", accent)
        glow_hex = getattr(get_active_tokens(), _ACCENT_COLOR_FIELDS[accent])
        apply_shadow(self, "sm", glow_color=glow_hex)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        layout.setSpacing(SPACING_XS)

        header_row = QHBoxLayout()
        header_row.setSpacing(SPACING_SM)
        if icon is not None:
            tokens = get_active_tokens()
            accent_hex = getattr(tokens, _ACCENT_COLOR_FIELDS[accent])
            tint_field = _ACCENT_TINTS.get(accent)
            tint_hex = getattr(tokens, tint_field) if tint_field else tokens.header_accent
            header_row.addWidget(
                build_icon_badge(icon, accent_hex, tint_hex, size=_ICON_BADGE_SIZE, parent=self)
            )
        title_label = QLabel(title, self)
        title_label.setProperty("role", "secondary")
        header_row.addWidget(title_label)
        header_row.addStretch()
        layout.addLayout(header_row)

        self._value_label = QLabel(value, self)
        self._value_label.setProperty("emphasis", True)
        if value_role is not None:
            self._value_label.setProperty("role", value_role)
        layout.addWidget(self._value_label)

        if delta_pct is not None:
            arrow = "▲" if delta_pct >= 0 else "▼"
            delta_label = QLabel(f"{arrow} {abs(delta_pct):.1f}% vs mes anterior", self)
            delta_label.setProperty("role", "success" if delta_pct >= 0 else "danger")
            layout.addWidget(delta_label)
        elif subtitle:
            subtitle_label = QLabel(subtitle, self)
            subtitle_label.setProperty("role", "secondary")
            subtitle_label.setWordWrap(True)
            layout.addWidget(subtitle_label)

        layout.addStretch()

        if trend and len(trend) >= 2:
            tokens = get_active_tokens()
            spark = Sparkline(getattr(tokens, _ACCENT_COLOR_FIELDS[accent]), self)
            spark.set_data(trend)
            layout.addWidget(spark)

    def set_value(self, value: str) -> None:
        self._value_label.setText(value)
