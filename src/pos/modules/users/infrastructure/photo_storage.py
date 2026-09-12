"""Almacenamiento de fotos de perfil de usuario.

No hay un flujo de edición/borrado de foto todavía (solo alta, ver
`UserFormDialog`): si un usuario se elimina físicamente, el archivo de
foto queda huérfano en disco. Aceptable por ahora — no hay tantos
usuarios en un POS como para que el espacio en disco importe, y agregar
limpieza automática es una abstracción que nadie pidió todavía.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from pos.core.config.bootstrap import get_app_data_dir

_PHOTOS_SUBDIR = "user_photos"

_MAX_DIMENSION_PX = 800
"""Lado más largo permitido (la foto es retrato 3x4): por encima de esto
se redimensiona antes de guardar."""
_MAX_FILE_SIZE_BYTES = 1_000_000
"""Por encima de este peso se recomprime aunque la resolución ya sea baja
(ej. un PNG sin comprimir)."""
_JPEG_QUALITY = 85
"""Buena calidad visual con compresión real — más que esto no se nota a
simple vista en una miniatura/perfil, y aumenta el peso del archivo."""


def save_user_photo(source_path: Path) -> str:
    """Copia `source_path` al directorio de datos de la app y devuelve la
    ruta final (absoluta, como string) para guardar en `User.photo_path`.

    Si la imagen es grande (en resolución o en peso), se redimensiona y
    recomprime a JPEG antes de guardarla, para no ocupar espacio ni
    ralentizar la app innecesariamente. Una foto ya liviana se copia tal
    cual, sin perder calidad por una recompresión innecesaria.
    """
    photos_dir = get_app_data_dir() / _PHOTOS_SUBDIR
    photos_dir.mkdir(parents=True, exist_ok=True)

    image = QImage(str(source_path))
    oversized_resolution = not image.isNull() and (
        max(image.width(), image.height()) > _MAX_DIMENSION_PX
    )
    oversized_weight = not image.isNull() and (
        source_path.stat().st_size > _MAX_FILE_SIZE_BYTES
    )

    if oversized_resolution or oversized_weight:
        if oversized_resolution:
            # Solo reduce resolución cuando realmente excede el máximo —
            # nunca agranda una imagen chica que sea simplemente pesada.
            image = image.scaled(
                _MAX_DIMENSION_PX,
                _MAX_DIMENSION_PX,
                aspectMode=Qt.AspectRatioMode.KeepAspectRatio,
                mode=Qt.TransformationMode.SmoothTransformation,
            )
        destination = photos_dir / f"{uuid4().hex}.jpg"
        image.save(str(destination), "JPG", _JPEG_QUALITY)
    else:
        destination = photos_dir / f"{uuid4().hex}{source_path.suffix.lower()}"
        shutil.copy2(source_path, destination)

    return str(destination)
