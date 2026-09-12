"""Editor de recorte de foto de perfil: fuerza que toda foto de usuario
quede en proporción 3x4 (retrato), sin importar la proporción original,
permitiendo mover (arrastrar) y acercar/alejar la imagen dentro de un
marco fijo antes de aceptar el recorte."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

CROP_WIDTH = 300
CROP_HEIGHT = 400
"""Marco de recorte fijo, proporción 3x4 (retrato)."""

_ZOOM_MIN_PERCENT = 100
_ZOOM_MAX_PERCENT = 400


class PhotoCropDialog(QDialog):
    """Diálogo modal: muestra `source_path` dentro de un marco fijo 3x4,
    con arrastre para mover y un control deslizante para hacer zoom.
    `cropped_image()` devuelve el resultado (ya en 3x4) tras aceptar."""

    def __init__(self, source_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Recortar foto")
        self._original = QPixmap(source_path)
        self._result: QImage | None = None
        self._current_scale = 1.0
        self._min_scale = 1.0

        self._build_ui()
        self._fit_image_to_frame()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Arrastrá la imagen para moverla y usá el control para "
            "acercar/alejar dentro del marco.",
            self,
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._scene = QGraphicsScene(self)
        self._pixmap_item = QGraphicsPixmapItem(self._original)
        self._scene.addItem(self._pixmap_item)
        self._scene.setSceneRect(self._pixmap_item.boundingRect())

        self._view = QGraphicsView(self._scene, self)
        self._view.setFixedSize(CROP_WIDTH, CROP_HEIGHT)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self._view.setFrameShape(QGraphicsView.Shape.Box)

        view_row = QHBoxLayout()
        view_row.addStretch()
        view_row.addWidget(self._view)
        view_row.addStretch()
        layout.addLayout(view_row)

        self._zoom_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._zoom_slider.setRange(_ZOOM_MIN_PERCENT, _ZOOM_MAX_PERCENT)
        self._zoom_slider.setValue(_ZOOM_MIN_PERCENT)
        self._zoom_slider.valueChanged.connect(self._on_zoom_changed)
        layout.addWidget(self._zoom_slider)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _fit_image_to_frame(self) -> None:
        """Escala inicial: la imagen cubre todo el marco (el lado más
        chico se ajusta exacto, el más grande queda recortado por los
        bordes del marco) — nunca queda espacio vacío al abrir."""
        width = self._original.width()
        height = self._original.height()
        if width <= 0 or height <= 0:
            return
        cover_scale = max(CROP_WIDTH / width, CROP_HEIGHT / height)
        self._min_scale = cover_scale
        self._current_scale = cover_scale
        self._view.resetTransform()
        self._view.scale(cover_scale, cover_scale)
        self._view.centerOn(self._pixmap_item)

    def _on_zoom_changed(self, value: int) -> None:
        target_scale = self._min_scale * (value / _ZOOM_MIN_PERCENT)
        factor = target_scale / self._current_scale
        # Ancla el zoom al centro del marco, no a la esquina.
        center = self._view.mapToScene(self._view.viewport().rect().center())
        self._view.scale(factor, factor)
        self._current_scale = target_scale
        self._view.centerOn(center)

    def _on_accept(self) -> None:
        viewport_rect = self._view.viewport().rect()
        scene_rect = self._view.mapToScene(viewport_rect).boundingRect()
        item_rect = self._pixmap_item.mapFromScene(scene_rect).boundingRect().toRect()
        item_rect = item_rect.intersected(self._original.rect())
        cropped = self._original.copy(item_rect)
        self._result = cropped.toImage()
        self.accept()

    def cropped_image(self) -> QImage | None:
        """Resultado del recorte tras aceptar (proporción 3x4). `None` si
        se canceló o la imagen de origen no pudo cargarse."""
        return self._result
