"""Pantalla de inicio de sesión.

Identidad visual oficial de ASTRIM (ver `docs/branding/`, DESIGN_GUIDE.md):
logo, nombre y eslogan son imágenes de marca, nunca texto — ver
`_brand_image_label`. Pensada para pantallas táctiles: campos y botón con
alto mínimo generoso (ver `shared_ui.theme.tokens.ThemeTokens.
touch_control_min_height_px`) y sin depender de hover para ninguna acción.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
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
from pos.shared_ui.branding import load_brand_pixmap
from pos.shared_ui.theme.elevation import apply_shadow
from pos.shared_ui.theme.spacing import SPACING_LG, SPACING_MD, SPACING_XL
from pos.shared_ui.theme.theme_manager import get_active_tokens
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page

_LOGO_HEIGHT_PX = 260
"""El elemento principal de la pantalla — 260px (~73% más que el valor
original de 150px) para que capte la atención de inmediato, tal como pidió
el usuario ("debe llamar la atención inmediatamente")."""
_WORDMARK_WIDTH_PX = 280
_SLOGAN_WIDTH_PX = 320
_VERSION_WIDTH_PX = 130
"""Pie de página discreto — no debe competir con el logo."""
_CARD_WIDTH_PX = 380
_FOOTER_MARGIN_PX = 28
_BRAND_STACK_SPACING_PX = 10
"""Separación entre logo/nombre/eslogan — deliberadamente chica (8-12px)
para que los tres se lean como un solo bloque de marca, no como elementos
sueltos."""
_TRIM_ALPHA_THRESHOLD = 40
"""Los PNG de marca traen una sombra/brillo suave que se desvanece hasta
alfa≈0 en casi todo el lienzo — un recorte "cualquier píxel no-cero" (`QImage.
getbbox`-equivalente) apenas recorta nada, porque esa cola de sombra casi
llega a cubrir el lienzo completo. Este umbral separa el glifo realmente
visible de esa cola."""
_TRIM_PROXY_MAX_DIM = 128
"""Escanear una copia reducida en vez de la imagen a resolución completa
(hasta 1536×1024) — miles de píxeles en vez de millones, sin diferencia
visible en el recuadro resultante."""
_TRIM_MARGIN_RATIO = 0.04
"""Margen de seguridad alrededor del recuadro detectado, para no recortar
el suavizado de los bordes del glifo."""


def _trim_transparent_margin(pixmap: QPixmap) -> QPixmap:
    """Recorta el margen transparente alrededor del contenido realmente
    visible de `pixmap` (nunca modifica el archivo original en
    `docs/branding/`) — sin este recorte, escalar por ancho/alto el PNG tal
    cual reproduce también su margen vacío, así que la separación visual
    entre logo/nombre/eslogan quedaba dominada por ese margen y no por el
    espaciado real del layout (ver DESIGN_GUIDE.md)."""
    proxy = (
        pixmap.scaled(
            _TRIM_PROXY_MAX_DIM,
            _TRIM_PROXY_MAX_DIM,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        .toImage()
        .convertToFormat(QImage.Format.Format_ARGB32)
    )
    left, top, right, bottom = proxy.width(), proxy.height(), -1, -1
    for y in range(proxy.height()):
        for x in range(proxy.width()):
            if proxy.pixelColor(x, y).alpha() >= _TRIM_ALPHA_THRESHOLD:
                left, right = min(left, x), max(right, x)
                top, bottom = min(top, y), max(bottom, y)
    if right < left or bottom < top:
        return pixmap

    scale_x = pixmap.width() / proxy.width()
    scale_y = pixmap.height() / proxy.height()
    margin_x = max(1, round((right - left) * _TRIM_MARGIN_RATIO))
    margin_y = max(1, round((bottom - top) * _TRIM_MARGIN_RATIO))
    crop_rect = QRect(
        round((left - margin_x) * scale_x),
        round((top - margin_y) * scale_y),
        round((right - left + 1 + 2 * margin_x) * scale_x),
        round((bottom - top + 1 + 2 * margin_y) * scale_y),
    ).intersected(pixmap.rect())
    return pixmap.copy(crop_rect)


def _brand_image_label(
    filename: str, *, height: int | None = None, width: int | None = None, parent: QWidget
) -> QLabel:
    """`QLabel` con el PNG de marca `filename` recortado a su contenido
    visible (`_trim_transparent_margin`) y escalado preservando su
    proporción original (nunca se deforma) — se oculta a sí mismo si el
    asset no existe en vez de mostrar un ícono de imagen rota, para que la
    pantalla de login siga siendo usable."""
    label = QLabel(parent)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    pixmap = load_brand_pixmap(filename)
    if pixmap.isNull():
        label.setVisible(False)
        return label
    pixmap = _trim_transparent_margin(pixmap)
    if height is not None:
        scaled = pixmap.scaledToHeight(height, Qt.TransformationMode.SmoothTransformation)
    else:
        scaled = pixmap.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)
    label.setPixmap(scaled)
    return label


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
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        scroll_area, outer_layout = build_scrollable_page(self)
        root_layout.addWidget(scroll_area)
        outer_layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, _FOOTER_MARGIN_PX)
        outer_layout.setSpacing(0)

        outer_layout.addStretch(1)

        logo_label = _brand_image_label("logo.png", height=_LOGO_HEIGHT_PX, parent=self)
        outer_layout.addWidget(logo_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer_layout.addSpacing(_BRAND_STACK_SPACING_PX)

        wordmark_label = _brand_image_label(
            "astrim.png", width=_WORDMARK_WIDTH_PX, parent=self
        )
        outer_layout.addWidget(wordmark_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer_layout.addSpacing(_BRAND_STACK_SPACING_PX)

        slogan_label = _brand_image_label("frase1.png", width=_SLOGAN_WIDTH_PX, parent=self)
        outer_layout.addWidget(slogan_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer_layout.addSpacing(SPACING_XL)

        card = QFrame(self)
        card.setObjectName("surface")
        card.setFixedWidth(_CARD_WIDTH_PX)
        apply_shadow(card, "lg", glow_color=get_active_tokens().primary)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(SPACING_MD)
        card_layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)

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

        card_layout.addWidget(self._username_edit)
        card_layout.addWidget(self._password_edit)
        card_layout.addWidget(self._error_label)
        card_layout.addWidget(self._login_button)

        outer_layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Espacio fijo (no solo `addStretch`) antes del pie de página: si el
        # contenido ya casi llena la ventana, el espacio "extra" que
        # reparte un stretch puede ser ~0px — sin este mínimo garantizado,
        # la versión terminaba pegada al borde inferior de la tarjeta.
        outer_layout.addSpacing(SPACING_XL)
        outer_layout.addStretch(1)

        version_label = _brand_image_label("version.png", width=_VERSION_WIDTH_PX, parent=self)
        outer_layout.addWidget(version_label, alignment=Qt.AlignmentFlag.AlignHCenter)

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
