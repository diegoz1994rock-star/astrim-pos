"""Claves y etiquetas de las secciones configurables y reordenables de la
factura.

`content_order` guarda una lista de estas mismas claves reordenada por el
usuario en Administración → Configuración de factura. `company`,
`items_table`, `subtotal`/`discount`/`tax`/`total` (la tabla de totales
fusionada) NO están acá — su posición es siempre fija (empresa primero,
tabla de productos + totales justo después, ver
`domain/layout_plan.py::build_layout_plan`), así que no tiene sentido que
el usuario las reordene. Los booleanos `show_discounts`/`show_taxes`/
`show_total` de `InvoiceSettingsDTO` siguen controlando su visibilidad,
ahora vía casillas propias en la UI en vez de una fila de esta lista (ver
`presentation/invoice_settings_view.py`).

`CONTENT_KEYS` es la unión de `HEADER_KEYS` (entre la empresa y la tabla de
productos) y `FOOTER_KEYS` (después de los totales) — dos zonas separadas
para el orden de impresión real (`build_layout_plan` nunca mezcla una
clave de una zona en la otra), aunque ambas viven en una sola lista
`content_order` persistida."""

from __future__ import annotations

HEADER_KEYS: tuple[str, ...] = ("logo", "customer", "cashier", "register", "date", "time")
FOOTER_KEYS: tuple[str, ...] = ("qr", "barcode", "closing_message", "social_media", "return_policy")

CONTENT_KEYS: list[str] = [*HEADER_KEYS, *FOOTER_KEYS]

CONTENT_LABELS: dict[str, str] = {
    "logo": "Logo",
    "customer": "Cliente",
    "cashier": "Cajero",
    "register": "Caja",
    "date": "Fecha",
    "time": "Hora",
    "qr": "Código QR",
    "barcode": "Código de barras",
    "closing_message": "Mensaje final",
    "social_media": "Redes sociales",
    "return_policy": "Política de devolución",
}
