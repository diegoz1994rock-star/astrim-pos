"""Almacenamiento genérico de una imagen de configuración subida por el
usuario — mismo patrón que `products/infrastructure/image_storage.py`/
`users/infrastructure/photo_storage.py` (redimensionado/recompresión),
generalizado para cualquier módulo que necesite guardar una sola imagen
configurable (logo de factura, imagen de fondo del Dashboard, etc.) sin
duplicar la lógica de redimensionado en cada uno."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from pos.core.config.bootstrap import get_app_data_dir

_MAX_DIMENSION_PX = 1600
_MAX_FILE_SIZE_BYTES = 2_000_000
_JPEG_QUALITY = 90


def save_configured_image(source_path: Path, subdir: str) -> str:
    """Copia `source_path` a `get_app_data_dir()/subdir` y devuelve la ruta
    final (absoluta, como string) para guardar en el campo de
    configuración correspondiente."""
    images_dir = get_app_data_dir() / subdir
    images_dir.mkdir(parents=True, exist_ok=True)

    image = QImage(str(source_path))
    oversized_resolution = not image.isNull() and (
        max(image.width(), image.height()) > _MAX_DIMENSION_PX
    )
    oversized_weight = not image.isNull() and (
        source_path.stat().st_size > _MAX_FILE_SIZE_BYTES
    )

    if oversized_resolution or oversized_weight:
        if oversized_resolution:
            image = image.scaled(
                _MAX_DIMENSION_PX,
                _MAX_DIMENSION_PX,
                aspectMode=Qt.AspectRatioMode.KeepAspectRatio,
                mode=Qt.TransformationMode.SmoothTransformation,
            )
        destination = images_dir / f"{uuid4().hex}.jpg"
        image.save(str(destination), "JPG", _JPEG_QUALITY)
    else:
        destination = images_dir / f"{uuid4().hex}{source_path.suffix.lower()}"
        shutil.copy2(source_path, destination)

    return str(destination)
