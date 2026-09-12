"""Catálogo de códigos de permiso otorgables a un cargo (`JobPosition`),
uno por cada `NavPanel` no administrativo de `main.py`. Constante plana en
vez de tabla de base de datos: no hay otro consumidor de una fila de
catálogo (ej. una `description` separada) además del checklist de la
pantalla "Áreas y cargos", así que una tabla extra sería una abstracción
sin uso real. Agregar un módulo nuevo con permiso propio es agregar una
tupla aquí y el `permission_code` correspondiente en
`main.py::_build_nav_panels`, nada más.

"Administrador General" (`JobPosition.grants_full_access=True`) nunca
necesita filas en `job_position_permissions`: ese flag bypasea cualquier
chequeo de permiso (ver `main.py::_panel_visible`)."""

from __future__ import annotations

PERMISSION_CATALOG: list[tuple[str, str]] = [
    ("products.manage", "Catálogo"),
    ("inventory.manage", "Inventario"),
    ("customers.manage", "Clientes y Proveedores"),
    ("cash_register.manage", "Caja"),
    ("restaurant.manage", "Vendedor"),
    ("kitchen.manage", "Despacho"),
    ("sales.create", "Ventas"),
    ("reports.view", "Reportes"),
    ("profits.view", "Ganancias"),
    ("admin.manage", "Administración"),
]
