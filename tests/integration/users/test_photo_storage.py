"""Pruebas de integración de `save_user_photo` (redimensión/compresión)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QImage

from pos.modules.users.infrastructure.photo_storage import save_user_photo


def _make_image(path: Path, width: int, height: int) -> None:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(0xFF00FF)
    assert image.save(str(path))


def test_small_photo_is_copied_as_is(qapp, tmp_path: Path) -> None:
    source = tmp_path / "chica.png"
    _make_image(source, 90, 120)

    destination = save_user_photo(source)

    assert destination.endswith(".png")
    saved = QImage(destination)
    assert (saved.width(), saved.height()) == (90, 120)


def test_large_photo_is_resized_and_compressed_to_jpeg(qapp, tmp_path: Path) -> None:
    source = tmp_path / "grande.png"
    _make_image(source, 1500, 2000)

    destination = save_user_photo(source)

    assert destination.endswith(".jpg")
    saved = QImage(destination)
    assert max(saved.width(), saved.height()) <= 800
    # Se mantiene la proporción 3x4 (aprox 1500:2000 == 3:4).
    assert round(saved.width() / saved.height(), 2) == round(1500 / 2000, 2)


def test_heavy_but_small_resolution_photo_is_still_recompressed(
    qapp, tmp_path: Path
) -> None:
    """Una imagen de resolución baja pero muy pesada (ej. un PNG sin
    comprimir) también debe recomprimirse, no solo las de alta resolución."""
    source = tmp_path / "pesada.png"
    _make_image(source, 400, 533)
    # Infla el archivo por encima del umbral de peso sin tocar la imagen.
    with source.open("ab") as f:
        f.write(b"0" * 1_100_000)

    destination = save_user_photo(source)

    assert destination.endswith(".jpg")
