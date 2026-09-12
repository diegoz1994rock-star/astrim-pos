"""Almacenamiento de archivos adjuntos de usuario (hoja de vida,
documentos, etc.). Mismo patrón que `photo_storage.py`: copia el archivo
elegido al directorio de datos de la app con un nombre único en disco,
conservando el nombre original para mostrarlo/descargarlo con su nombre
real."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from pos.core.config.bootstrap import get_app_data_dir

_DOCUMENTS_SUBDIR = "user_documents"


def save_user_document(source_path: Path) -> str:
    """Copia `source_path` al directorio de datos de la app y devuelve la
    ruta final (absoluta, como string) para guardar en
    `UserDocument.stored_path`. El nombre original se guarda aparte
    (`UserDocument.original_filename`), no se pierde aunque el archivo en
    disco tenga un nombre único para evitar colisiones."""
    documents_dir = get_app_data_dir() / _DOCUMENTS_SUBDIR
    documents_dir.mkdir(parents=True, exist_ok=True)

    destination = documents_dir / f"{uuid4().hex}_{source_path.name}"
    shutil.copy2(source_path, destination)
    return str(destination)
