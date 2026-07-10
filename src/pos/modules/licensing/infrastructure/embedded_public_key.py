"""Clave pública Ed25519 del vendedor, embebida en la aplicación.

Solo la clave PÚBLICA vive aquí y se versiona en git — es segura de
distribuir. La clave PRIVADA correspondiente nunca debe estar en el
repositorio; vive fuera de control de versiones y solo la usa
`scripts/generate_license.py` para emitir licencias nuevas (ver
ARCHITECTURE.md §9 y README.md, sección de licencias).

Este es un par de claves de **desarrollo/demostración**, generado para
este proyecto. Antes de un lanzamiento comercial real, el vendedor debe
generar su propio par con `scripts/generate_license.py keygen` y
reemplazar esta constante — la clave privada de desarrollo nunca debe
usarse para licencias vendidas de verdad.
"""

from __future__ import annotations

VENDOR_PUBLIC_KEY_B64 = "eLhs2MyCl+OVs31PIy2TKegSVz2BLHk0PE3JW7hH6pw="
