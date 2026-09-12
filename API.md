# API.md — API HTTP de negocio (ASTRIM)

Referencia técnica de la API REST expuesta por la estación configurada como "servidor principal" (panel Sincronización → modo Servidor). Pensada para clientes remotos: app Android, tablet, y futuras aplicaciones de escritorio — construida en las Fases 1 a 7, reutilizando siempre los mismos `Service`/DTO que ya usa la aplicación de escritorio (PySide6), nunca una reimplementación paralela.

**Base URL**: `http://<ip-de-la-estación-servidor>:<puerto>` (puerto configurable en el panel Sincronización, por defecto `8765`).

**Documentación interactiva** (generada automáticamente desde el mismo código, siempre sincronizada): `GET /docs` (Swagger UI) y `GET /redoc` (ReDoc). El esquema crudo está en `GET /openapi.json`. Ninguna de las tres requiere autenticación — son solo metadatos, no ejecutan nada.

---

## 1. Convenciones generales

- **Prefijo de versión**: todos los endpoints de negocio viven bajo `/api/v1/...`. Dos excepciones intencionales, fuera de ese prefijo y sin relación con la API pública: `GET /health` (diagnóstico interno del servidor de sincronización, ver `server/runner.py::SyncServer.probe`) y `ws://.../ws/sync` (protocolo de sincronización entre estaciones, no lo consume Android).
- **Formato**: JSON en cuerpo de solicitud/respuesta, `Content-Type: application/json`.
- **Decimales**: todo campo monetario/cantidad (`Decimal` en el backend) se serializa como **string**, no como número JSON — evita el redondeo de punto flotante en valores de dinero (`"3500.00"`, no `3500.0`). Parsear como decimal en el cliente, nunca como `float`/`double`.
- **Fechas**: ISO 8601 en UTC, con sufijo `Z` (ej. `"2026-07-24T17:03:34.889253Z"`).
- **Errores**: siempre `{"detail": "mensaje legible"}`, con el código HTTP correspondiente (ver §4). Nunca una traza cruda: cualquier error de negocio no capturado explícitamente por un endpoint pasa por un manejador global (`sync/server/api/errors.py`) que lo traduce a un código HTTP seguro.
- **Paginación**: solo donde el catálogo puede crecer sin límite (`GET /products`, ver §6.2) — parámetros `limit`/`offset` opcionales, con el total real en el encabezado de respuesta `X-Total-Count`. Sin esos parámetros, el endpoint se comporta igual que si no existiera paginación (compatibilidad hacia atrás).

---

## 2. Autenticación y autorización

### 2.1 Flujo

1. `POST /api/v1/auth/login` con usuario/contraseña → devuelve un `token` de sesión (válido 12 horas) y la identidad/permisos del usuario.
2. Cada solicitud posterior a un endpoint protegido debe incluir:
   ```
   Authorization: Bearer <token>
   ```
3. Un middleware (`AuthMiddleware`) protege **toda** ruta bajo `/api/v1` por default, salvo `POST /api/v1/auth/login` y `GET /api/v1/health`, declaradas explícitamente públicas. Cualquier endpoint nuevo que se agregue en el futuro queda protegido automáticamente sin tener que acordarse de nada.
4. El mismo sistema de bloqueo por intentos fallidos que usa el login de escritorio aplica acá (5 intentos fallidos → cuenta bloqueada 15 minutos, `423 Locked`).

### 2.2 Autorización por permiso

Además de "¿tiene un token válido?", algunos endpoints exigen un permiso específico — los mismos códigos de permiso que ya gobiernan qué paneles ve cada cargo en el escritorio (`Administración → Áreas y cargos`):

| Endpoint | Permiso requerido |
|---|---|
| `POST /api/v1/sales/drafts/{id}/complete` | `sales.create` |
| `GET /api/v1/sales/{sale_id}` | `sales.create` |
| Todos los demás endpoints protegidos | Solo requieren estar autenticado (cualquier token válido) |

Un usuario con el cargo "Administrador General" (`grants_full_access`) pasa cualquier chequeo de permiso automáticamente.

> **Nota para quien construya el cliente Android**: los endpoints de construcción del carrito (Fase 3: crear/agregar/modificar/eliminar líneas) no exigen `sales.create` hoy — solo estar autenticado. Es una asimetría conocida y documentada (ver §8, Recomendaciones), no un descuido.

### 2.3 Reloj del dispositivo

`GET /api/v1/health` devuelve `server_time` (hora UTC del servidor) — útil para que el cliente detecte si el reloj de su propio dispositivo está desfasado antes de interpretar `expires_at` de un token como expirado.

---

## 3. Módulos y endpoints

### 3.1 Auth (`/api/v1/auth`)

#### `POST /api/v1/auth/login`
Público. Autentica usuario/contraseña.

**Body**
```json
{ "username": "cajero1", "password": "clave-valida-123" }
```

**200 OK**
```json
{
  "token": "3f1e2b...",
  "expires_at": "2026-07-25T05:00:00.000000Z",
  "session": {
    "user_id": 7,
    "username": "cajero1",
    "full_name": "Ana Pérez",
    "is_admin": false,
    "permission_codes": ["sales.create"],
    "logged_in_at": "2026-07-24T17:00:00.000000Z",
    "job_position_name": "Cajero"
  }
}
```
`job_position_name` (Fase 6.1): mismo dato y misma resolución que la barra superior del escritorio (`main.py::_current_job_position_name`, vía `UserManagementService`) — `null` si el usuario no tiene un cargo asignado. No sustituye a `is_admin`: un administrador también tiene su propio `job_position_name` (ej. "Administrador General"); la etiqueta de respaldo que usa el escritorio ("Administrador"/"Empleado" cuando no hay cargo) es una decisión de presentación de cada cliente, no de esta API.

**Errores**: `401` credenciales inválidas · `423` cuenta bloqueada por intentos fallidos.

#### `GET /api/v1/auth/me`
Requiere autenticación. Devuelve la identidad del token actual (mismo objeto `session` de arriba, sin el envoltorio `token`/`expires_at`).

**200 OK**
```json
{
  "user_id": 7, "username": "cajero1", "full_name": "Ana Pérez",
  "is_admin": false, "permission_codes": ["sales.create"],
  "logged_in_at": "2026-07-24T17:00:00.000000Z",
  "job_position_name": "Cajero"
}
```

**Errores**: `401` sin token / token inválido o expirado.

---

### 3.2 Health

#### `GET /api/v1/health`
Público.

**200 OK**
```json
{ "status": "ok", "server_time": "2026-07-24T17:03:34.889253Z" }
```

---

### 3.3 Categorías (`/api/v1/categories`) — solo lectura

#### `GET /api/v1/categories`
Requiere autenticación. Todas las categorías (activas e inactivas — el filtro es decisión del cliente, igual que en el escritorio).

**200 OK**
```json
[{ "id": 1, "name": "Bebidas", "is_active": true }]
```

---

### 3.4 Productos (`/api/v1/products`) — solo lectura

CRUD de productos sigue siendo exclusivo del escritorio (Catálogo). `cost_price`/`unit_cost` (margen) nunca se exponen — ni la pantalla de Ventas del escritorio se los muestra a un cajero.

#### `GET /api/v1/products`
Requiere autenticación. Catálogo completo (igual que Catálogo/Ventas del escritorio: sin filtrar activos/inactivos).

**Query params**
| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `q` | string | — | Búsqueda por subcadena, sin distinguir mayúsculas, sobre SKU + código de barras + nombre + categoría (mismo criterio que el buscador del escritorio) |
| `limit` | int (1–500) | sin límite | Cantidad máxima de resultados |
| `offset` | int (≥0) | `0` | Desde qué posición empezar |

**Respuesta**: `200 OK`, encabezado `X-Total-Count: <n>` (total real después de `q`, antes de paginar).
```json
[{
  "id": 12, "sku": "SKU-001", "name": "Coca-Cola 400ml",
  "category_id": 3, "category_name": "Bebidas", "product_type": "simple",
  "unit_price": "3500.00", "unit_of_measure": "unidad", "sale_unit": "unit",
  "is_active": true, "track_inventory": true, "image_path": null,
  "barcodes": ["7701234567890"]
}]
```

#### `GET /api/v1/products/by-barcode/{code}`
Requiere autenticación. Detalle completo de un producto por código de barras — la misma fuente que usa Ventas al escanear.

**Errores**: `404` código no existe.

#### `GET /api/v1/products/{product_id}`
Requiere autenticación. Detalle completo (`ProductSummary` + `description`, rango de peso, y `recipe_items`/`combo_items` si el producto es compuesto/combo).

**200 OK** (ejemplo compuesto)
```json
{
  "id": 12, "sku": "SKU-001", "name": "Coca-Cola 400ml", "category_id": 3,
  "category_name": "Bebidas", "product_type": "simple", "unit_price": "3500.00",
  "unit_of_measure": "unidad", "sale_unit": "unit", "is_active": true,
  "track_inventory": true, "image_path": null, "barcodes": ["7701234567890"],
  "description": null, "min_weight": null, "max_weight": null,
  "weight_decimal_places": null, "recipe_items": [], "combo_items": []
}
```

**Errores**: `404` id no existe.

#### `GET /api/v1/products/{product_id}/image`
Requiere autenticación. Agregado en la Fase 2 del cliente Android: `image_path` (visto arriba) es una ruta de archivo *del servidor* — un cliente remoto no tiene forma de acceder a ella directamente, así que este endpoint sirve los bytes de la imagen ya guardada (mismo archivo que usa el escritorio en Catálogo/Ventas/Despacho).

**200 OK**: el archivo de imagen tal cual (`Content-Type` según su extensión — típicamente `image/jpeg`).

**Errores**: `404` id no existe, el producto no tiene imagen, o el archivo ya no está en disco (se trata igual que "no tiene imagen", nunca `500`).

---

### 3.5 Ventas — construcción del carrito (`/api/v1/sales/drafts`)

Un carrito ("venta en curso") **no se persiste en la base de datos** hasta que se finaliza (§3.6). Vive en memoria del proceso del servidor, identificado por `draft_id` (UUID), y pertenece exclusivamente al usuario que lo creó (otro usuario recibe `404`, no `403` — no revela si el id existe). Se pierde si el servidor se reinicia, igual que cerrar el escritorio sin cobrar pierde el carrito de esa sesión.

Todo el cálculo (subtotal, descuentos, impuestos, total) pasa por el mismo `SalesService.preview_sale` que usa el carrito del escritorio.

#### `POST /api/v1/sales/drafts`
Requiere autenticación. Crea un carrito vacío.

**201 Created**
```json
{ "draft_id": "ae330b5f-...", "subtotal": "0", "discount_total": "0", "tax_total": "0", "total": "0", "items": [] }
```

#### `GET /api/v1/sales/drafts/{draft_id}`
Requiere autenticación (dueño del carrito). Resumen actualizado.

**Errores**: `404` no existe / no es tuyo.

#### `POST /api/v1/sales/drafts/{draft_id}/items`
Agrega un producto. Si el producto ya está en el carrito, **suma** la cantidad a esa misma línea (no duplica) y conserva la nota anterior salvo que se envíe una nueva.

**Body**
```json
{ "product_id": 12, "quantity": "2", "note": "Sin hielo" }
```
`note` es opcional.

**Respuesta**: `200 OK`, mismo formato que el carrito.

**Errores**: `404` carrito o producto inexistente · `409` stock insuficiente / carrito ya finalizado · `422` cantidad ≤ 0.

#### `PATCH /api/v1/sales/drafts/{draft_id}/items/{item_index}`
Cambia cantidad (y nota, siempre — a diferencia de "agregar", acá si no se envía `note` queda en `null`, no conserva la anterior) de la línea en la posición `item_index` (basado en 0, según el orden del array `items` de la respuesta).

**Body**
```json
{ "quantity": "4", "note": null }
```

**Errores**: `404` carrito/línea inexistente · `409` stock insuficiente / carrito ya finalizado · `422` cantidad ≤ 0.

#### `DELETE /api/v1/sales/drafts/{draft_id}/items/{item_index}`
Elimina esa línea.

**Errores**: `404` carrito/línea inexistente · `409` carrito ya finalizado.

---

### 3.6 Ventas — finalización (cobro)

#### `POST /api/v1/sales/drafts/{draft_id}/complete`
Requiere permiso `sales.create`. Cobra el carrito: llama exactamente a `SalesService.complete_sale` (persiste la venta, descuenta inventario, mueve caja) — mismo flujo que "Cobrar" en el escritorio. Bodega/punto de caja se eligen automáticamente (la primera bodega y el primer punto de caja con turno abierto — el escritorio tampoco deja elegir).

Tras cobrar, llama también a `RestaurantService.create_order_from_sale` — réplica de la rama `else` de `SaleViewModel.complete_sale` del escritorio ("venta creada directo en Ventas, sin pasar por un pedido de Vendedor"): la venta genera automáticamente su propio pedido de Despacho, ya cobrado (`origin: "ventas"`, `sale_id` seteado desde el nacimiento), visible de inmediato en `GET /dispatch/orders` (§3.7). Corrección de un bug real: antes de esto, ninguna venta completada desde Android aparecía en Despacho.

**Body**
```json
{
  "payments": [{ "payment_method": "cash", "amount": "7000.00", "reference": null }],
  "customer_id": null,
  "customer_name": null,
  "customer_document": null
}
```
`payment_method` acepta: `cash`, `card`, `qr`, `nequi`, `bre_b`, `customer_credit` (mismo subconjunto seleccionable que el escritorio; `customer_credit` exige `customer_id`). Se admiten varios pagos (pago mixto), igual que el escritorio.

**200 OK** — la venta ya persistida (`SaleDTO`):
```json
{
  "id": 45, "status": "completed", "sale_type": "counter", "customer_id": null,
  "subtotal": "7000.00", "discount_total": "0", "tax_total": "0.00", "total": "7000.00",
  "created_at": "2026-07-24T17:10:00.000000Z", "created_by_user_id": 7,
  "cash_session_id": 3, "customer_name": null, "customer_document": null,
  "items": [{
    "id": 91, "product_id": 12, "product_name": "Coca-Cola 400ml", "quantity": "2.000",
    "unit_price": "3500.00", "discount_amount": "0", "tax_amount": "0.00",
    "line_total": "7000.00", "note": null, "sale_unit": "unit", "unit_of_measure": "unidad"
  }],
  "payments": [{ "id": 33, "payment_method": "cash", "amount": "7000.00", "reference": null }]
}
```

**Duplicados — importante para el cliente**: cada carrito se finaliza **una sola vez**. Si la app reintenta la misma solicitud (timeout de red, doble tap) sobre el mismo `draft_id`, la API devuelve la **misma** venta ya persistida (mismo `id`) en vez de crear una segunda — verificado también bajo dos solicitudes verdaderamente simultáneas. **Recomendación**: si una solicitud de `complete` falla por timeout de red sin respuesta clara, la app debe reintentar sobre el **mismo** `draft_id`, nunca crear uno nuevo — eso sí generaría una venta distinta.

**Errores**: `401`/`403` sin token o sin permiso `sales.create` · `404` carrito inexistente · `409` sin bodega/caja configurada, sin turno de caja abierto, o stock insuficiente al momento de cobrar · `422` carrito vacío, sin pagos, medio de pago no disponible, o cualquier otra regla de negocio de `complete_sale` (ej. pago a crédito sin cliente, total de pagos no coincide con el total de la venta).

#### `GET /api/v1/sales/{sale_id}`
Requiere permiso `sales.create`. Consulta una venta ya finalizada por su id (mismo formato que la respuesta de `complete`).

**Errores**: `401`/`403` · `404` id no existe.

#### `GET /api/v1/sales`
Requiere permiso `sales.create`. Historial de ventas — botón "Historial" de Android, réplica de `Ventas → Historial` del escritorio (`SalesHistoryView`): mismo método, `SalesService.list_recent_sales`, ordenado por fecha descendente (más reciente primero). Sin filtros de fecha/cliente ni paginación real — el escritorio tampoco los tiene. `?limit=` es opcional (por defecto 50, máximo 200).

**200 OK** — lista de ventas en el mismo formato que `complete`/`GET /{sale_id}`.

**Solo lectura a propósito**: anular una venta y generar factura desde esta pantalla siguen siendo exclusivos del escritorio — no expuestos acá.

**Errores**: `401`/`403`.

---

### 3.7 Despacho (`/api/v1/dispatch`)

Pantalla "Despacho" del escritorio (`KitchenService`): pedidos organizados por cliente/pedido (una tarjeta por pedido, no por producto), sin importar si nacieron sin cobrar (Vendedor) o ya cobrados (Ventas). Solo replica las dos acciones reales que ofrece esa pantalla — el avance ítem por ítem que existe en el backend (`KitchenService.list_queue`/`advance_item`) no tiene UI propia y por eso tampoco API.

Filtros (Todos/Pendientes/En preparación/Entregados/Pagados/No pagados/Pedidos del Vendedor/Pedidos de Ventas) y búsqueda son responsabilidad del cliente: `GET /orders` siempre devuelve la cola activa completa (nunca pre-filtrada), igual que el escritorio filtra en memoria sobre la lista ya cargada.

#### `GET /api/v1/dispatch/orders`
Requiere permiso `kitchen.manage`. Cola completa de pedidos activos (excluye `cancelled`/`archived`, igual que el escritorio).

**200 OK**
```json
[{
  "order_id": 12, "origin": "vendedor", "customer_name": "Juan Pérez",
  "customer_document": null, "is_paid": false, "caja_name": null,
  "dispatch_status": "pending", "item_count": 1, "total_units": 2,
  "items": [{
    "id": 30, "order_id": 12, "product_id": 5, "product_name": "Coca-Cola 400ml",
    "quantity": 2, "notes": "Sin hielo", "status": "pending", "product_image_path": null
  }],
  "created_at": "2026-07-24T17:03:34.889253Z", "created_by_user_name": "Diego Gutiérrez",
  "dispatched_by_user_name": null, "sale_id": null
}]
```
`origin`: `"vendedor"` (pedido tomado sin cobrar todavía) o `"ventas"` (nace ya cobrado, creado automáticamente al completar una venta directo en Ventas — ver §8, no implementado desde la API todavía). `dispatch_status`: `"pending"` | `"preparing"` | `"ready"` (ningún flujo actual lo produce, se mantiene por compatibilidad) | `"delivered"`. `caja_name` es `null` hasta que el pedido tenga una venta asociada con turno de caja. `sale_id` (rediseño de Despacho en Android): mismo valor que ya resuelve `is_paid` (`null` = sin cobrar); si tiene valor, el pedido ya tiene una venta real y su precio/pago se consulta con `GET /sales/{sale_id}` (§3.6, requiere permiso `sales.create` — no necesariamente el mismo cargo que ve Despacho, ver ese permiso antes de asumir acceso).

**Errores**: `401` sin token · `403` sin permiso `kitchen.manage`.

#### `POST /api/v1/dispatch/orders/{order_id}/advance`
Requiere permiso `kitchen.manage`. Botón "Siguiente proceso" del escritorio: avanza el pedido un paso — `pending`→`preparing`→`delivered`→(sale del listado, sin quedar accesible por esta API). Nunca retrocede ni salta pasos. Sobre un pedido ya en `delivered`, lo archiva y deja de listarse en `GET /orders` (el registro se conserva en la base, solo deja de aparecer acá).

**Respuesta**: `200 OK`, la cola completa ya recargada (`list[DispatchOrderCardSchema]`, mismo formato que `GET /orders`) — evita que el cliente tenga que pedirla aparte después de actuar.

**Errores**: `401`/`403` · `404` el pedido no existe.

#### `POST /api/v1/dispatch/orders/{order_id}/deliver`
Requiere permiso `kitchen.manage`. Botón "Marcar como entregado" del detalle del pedido en el escritorio: marca el pedido (y todos sus ítems) como entregado directamente, sin importar el paso en el que esté — a diferencia de `advance`, no archiva el pedido, así que sigue listado en `GET /orders` con `dispatch_status: "delivered"` hasta el próximo `advance`.

**Respuesta**: `200 OK`, la cola completa ya recargada, igual que `advance`.

**Errores**: `401`/`403` · `404` el pedido no existe.

---

### 3.9 Clientes (`/api/v1/customers`)

Sobre `CustomerManagementService` — el mismo caso de uso que ya usan la pantalla "Clientes" y el buscador de cliente registrado de "Ventas" en el escritorio. `GET /customers` **no** exige el permiso `customers.manage`: el escritorio lo llama sin ninguna restricción propia desde `SaleViewModel` (cualquier cajero con acceso a Ventas puede buscar un cliente para una venta) — solo la pantalla de administración "Clientes" está detrás de ese permiso, y eso decide qué paneles ve cada cargo, no esta API. Crear un cliente y registrar un abono sí lo exigen: son las dos acciones reales de esa pantalla protegida ("Nuevo cliente"/"Registrar abono").

#### `GET /api/v1/customers`
Requiere autenticación (sin permiso adicional). Catálogo completo de clientes, sin filtrar — igual que `list_customers()` del escritorio; búsqueda/filtro son responsabilidad del cliente (mismo criterio que Catálogo/Despacho: se carga una vez y se filtra en memoria).

**200 OK**
```json
[{
  "id": 7, "full_name": "Juan Pérez", "document_id": "123456",
  "email": null, "phone": "3001234567", "address": null,
  "credit_limit": "100000.00", "current_debt": "30000.00",
  "loyalty_points_balance": 0
}]
```

**Errores**: `401` sin token.

#### `POST /api/v1/customers`
Requiere permiso `customers.manage`. Alta de cliente — botón "Nuevo cliente" del escritorio.

**Body**
```json
{
  "full_name": "Juan Pérez", "document_id": "123456", "email": null,
  "phone": "3001234567", "address": null, "credit_limit": "100000"
}
```
Solo `full_name` es obligatorio; el resto (incluido `credit_limit`, por defecto `0`) es opcional, igual que el formulario del escritorio.

**Respuesta**: `201 Created`, el cliente ya creado (mismo formato que `GET /customers`, con `current_debt: "0"`).

**Errores**: `401`/`403` · `422` nombre vacío o cupo de crédito negativo.

#### `POST /api/v1/customers/{customer_id}/payments`
Requiere permiso `customers.manage`. Registra un abono a la deuda del cliente — botón "Registrar abono" del escritorio. El cargo automático de una venta a crédito (`payment_method: "customer_credit"`) ya lo hace `POST /sales/drafts/{id}/complete` directamente vía `SalesService.complete_sale` (que a su vez llama `register_credit_movement`); este endpoint es solo para el abono manual.

**Body**
```json
{ "amount": "20000", "reference": "efectivo" }
```
`reference` es opcional.

**Respuesta**: `200 OK`, el cliente con `current_debt` ya actualizado (mismo formato que `GET /customers`).

**Errores**: `401`/`403` · `404` el cliente no existe · `422` monto ≤ 0, o el abono supera la deuda actual.

---

### 3.10 Caja (`/api/v1/cash-register`)

Sobre `CashRegisterService` — el mismo caso de uso que ya usa la pantalla "Caja" del escritorio (`cash_register_view.py`): ver el estado del turno, abrirlo y cerrarlo. No expone la administración de puntos de caja (`cash_registers_view.py`: crear/renombrar/desactivar cajas) ni los movimientos manuales de ingreso/egreso — funciones distintas, fuera del alcance de un vendedor con el móvil.

Las tres acciones exigen el permiso `cash_register.manage` (el mismo que gobierna si el panel "Caja" es visible en el escritorio) — a diferencia de Clientes (§3.9), acá no hay ningún caso de uso del escritorio que consulte el estado de caja sin pasar por ese panel protegido, así que incluso la lectura lo exige.

Sin selector de punto de caja: réplica del mismo criterio que ya usa `POST /sales/drafts/{id}/complete` (§3.6) para resolver la sesión de caja de una venta — toma el primer punto de caja activo (`list_registers()[0]`), sin ofrecer selector. Un negocio con un solo punto de caja (el caso común, ver `scripts/seed_demo_data.py`) nunca nota la diferencia.

#### `GET /api/v1/cash-register/status`
Requiere permiso `cash_register.manage`. Estado actual del punto de caja por defecto: el punto de caja y, si tiene un turno abierto, la sesión (`null` si no hay ninguno abierto).

**200 OK**
```json
{
  "cash_register": { "id": 1, "name": "Caja Principal", "location": null, "is_active": true },
  "session": {
    "id": 4, "cash_register_id": 1, "cash_register_name": "Caja Principal",
    "status": "open", "opened_by_user_id": 7, "opened_at": "2026-07-25T09:00:00Z",
    "opening_amount": "50000.00", "closed_at": null, "closing_amount": null,
    "expected_amount": null, "difference": null
  }
}
```
`expected_amount`/`difference` son siempre `null` mientras el turno está abierto — igual que el escritorio, que tampoco los muestra hasta el cierre (ver `CashRegisterService.close_session`).

**Errores**: `401` sin token · `403` sin permiso `cash_register.manage` · `409` no hay ningún punto de caja configurado.

#### `POST /api/v1/cash-register/sessions/open`
Requiere permiso `cash_register.manage`. Botón "Abrir turno" del escritorio.

**Body**
```json
{ "opening_amount": "50000" }
```

**Respuesta**: `201 Created`, la sesión ya abierta (mismo formato que el campo `session` de `GET /status`).

**Errores**: `401`/`403` · `409` no hay ningún punto de caja configurado · `422` monto de apertura negativo, o el punto de caja ya tiene un turno abierto.

#### `POST /api/v1/cash-register/sessions/close`
Requiere permiso `cash_register.manage`. Botón "Cerrar turno" del escritorio — cierra el turno abierto del punto de caja por defecto con el monto contado, y devuelve la diferencia contra lo esperado (`opening_amount` + ventas en efectivo + ingresos manuales − egresos manuales − devoluciones).

**Body**
```json
{ "counted_amount": "49000" }
```

**Respuesta**: `200 OK`, la sesión ya cerrada con `closing_amount`/`expected_amount`/`difference` resueltos.

**Errores**: `401`/`403` · `409` no hay ningún turno de caja abierto · `422` monto contado negativo.

---

### 3.11 Vendedor (`/api/v1/restaurant`)

Sobre `RestaurantService`/`SalesService` — el mismo caso de uso que ya usa la pantalla "Vendedor" del escritorio (`restaurant_view.py`): un pedido rápido **sin mesa** (el escritorio real no usa mesas en esta pantalla — el dominio de mesas, `DiningTable`/`TableSession`, existe y está probado a nivel de servicio, pero ninguna vista del escritorio lo consume hoy). El carrito en construcción vive en memoria del cliente (Android), igual que vive en memoria del `ViewModel` Qt del escritorio (`RestaurantViewModel._items`) hasta confirmarlo — no hay un `draft_id` ni un carrito persistido en el servidor para esto, a diferencia de Ventas (§3.5).

Ambos endpoints exigen el permiso `restaurant.manage` — el mismo que gobierna si el panel "Vendedor" es visible en el escritorio.

#### `POST /api/v1/restaurant/orders/preview`
Total en vivo del pedido en construcción — mismo cálculo que ve el mesero antes de confirmar (`SalesService.preview_sale`, la misma función que ya usa el carrito de Ventas). También valida stock antes de calcular: mismo criterio que `RestaurantViewModel._check_stock` (solo productos que controlan inventario, sumando la cantidad de cada producto en toda la lista, ya que acá no hay un carrito servidor con el que comparar incrementalmente).

**Body**
```json
{ "items": [{ "product_id": 12, "quantity": "2", "note": "Sin cebolla" }] }
```

**200 OK**
```json
{
  "subtotal": "30000.00", "discount_total": "0", "tax_total": "5700.00", "total": "35700.00",
  "items": [{
    "product_id": 12, "product_name": "Hamburguesa", "quantity": "2",
    "unit_price": "15000.00", "discount_amount": "0", "tax_amount": "5700.00",
    "line_total": "35700.00", "note": "Sin cebolla"
  }]
}
```

**Errores**: `401`/`403` · `404` algún producto no existe · `409` stock insuficiente para algún producto que controla inventario.

#### `POST /api/v1/restaurant/orders`
Botón "Confirmar pedido" del escritorio — llama exactamente a `RestaurantService.create_order(table_session_id=None, order_type=QUICK, origin=VENDEDOR, ...)`. El pedido nace `status: "pending"`, sin venta asociada (`sale_id: null`) y **aparece automáticamente en Despacho** (`GET /dispatch/orders`, §3.7) — no hace falta ninguna llamada adicional para "enviarlo". No repite la validación de stock de `/preview` (tampoco lo hace `confirm_order` del escritorio, que confía en que ya se validó al armar el carrito). `quantity` fraccionaria se trunca a entero (`int()`, no redondeo) — mismo comportamiento literal del escritorio, no corregido acá.

**Body**
```json
{
  "items": [{ "product_id": 12, "quantity": "2", "note": "Sin cebolla" }],
  "customer_name": "Juan Pérez", "customer_document": "123456"
}
```
`customer_name`/`customer_document` son opcionales; un nombre vacío o nulo se guarda como `"Consumidor Final"`, igual que el escritorio.

**201 Created**
```json
{
  "id": 45, "table_session_id": null, "order_type": "quick", "status": "pending",
  "items": [{
    "id": 90, "product_id": 12, "product_name": "Hamburguesa", "quantity": 2,
    "notes": "Sin cebolla", "status": "pending", "product_image_path": null
  }],
  "created_at": "2026-07-26T10:00:00.000000Z", "created_by_user_id": 7,
  "sale_id": null, "customer_name": "Juan Pérez", "customer_document": "123456",
  "origin": "vendedor", "dispatched_by_user_id": null
}
```

**Errores**: `401`/`403` · `404` algún producto no existe · `422` sin ítems, o cantidad de alguna línea ≤ 0.

---

### 3.12 Métodos de pago electrónico (`/api/v1/payment-methods`) — solo lectura

Espejo exacto de la configuración de QR/Nequi/Bre-B que ya administra el escritorio (Administración → Pagos electrónicos, `qr_payments`/`nequi_payments`/`bre_b_payments`) y que Caja consulta al cobrar (`QrPaymentDialog`/`NequiPaymentDialog`/`BreBPaymentDialog`, los tres llaman a `get_default_config()`). Ningún dato inventado: Daviplata, Transferencia Bancaria, alias/referencia, descripción e instrucciones al cliente **no existen** en el escritorio hoy, así que este bloque no los expone — es un espejo, no una ampliación de funcionalidad. Crear/editar/activar/eliminar configuraciones sigue siendo exclusivo del escritorio.

Solo requieren autenticación (`401` sin token) — sin permiso adicional, mismo criterio que los diálogos del escritorio: cualquier cajero autenticado ve el método predeterminado.

#### `GET /api/v1/payment-methods/qr`
El QR predeterminado (`is_default=true`).

**200 OK**
```json
{ "id": 3, "name": "QR Bancolombia", "has_image": true }
```
`has_image` indica si hay una imagen asociada — pedirla con `GET /payment-methods/qr/{id}/image`.

**Errores**: `401` · `409` no hay ningún QR configurado en Administración → Pagos electrónicos.

#### `GET /api/v1/payment-methods/qr/{config_id}/image`
El archivo de imagen guardado por el escritorio para ese QR (mismo patrón que `GET /products/{id}/image`, §3.4).

**Errores**: `401` · `404` no existe ese QR, o no tiene imagen, o el archivo no está disponible en disco.

#### `GET /api/v1/payment-methods/nequi`
El número de Nequi predeterminado (`is_default=true`, siempre activo).

**200 OK**
```json
{ "id": 2, "number": "3001234567" }
```

**Errores**: `401` · `409` no hay ningún número de Nequi configurado.

#### `GET /api/v1/payment-methods/bre-b`
La llave Bre-B predeterminada (`is_default=true`).

**200 OK**
```json
{ "id": 1, "key": "usuario@banco.breb" }
```

**Errores**: `401` · `409` no hay ninguna llave Bre-B configurada.

---

## 4. Códigos de error — referencia global

Todo error de negocio (no de infraestructura) pasa por el mismo mapeo, sin importar qué endpoint lo generó:

| Código | Origen | Significado |
|---|---|---|
| `401` | `AuthenticationError` | Sin token, token inválido/expirado, o credenciales incorrectas en login |
| `403` | `PermissionDeniedError` | Autenticado pero sin el permiso requerido |
| `404` | `NotFoundError` | El recurso (producto, carrito, línea, venta) no existe (o no es tuyo, para carritos) |
| `409` | `ConflictError` | Conflicto de estado (ej. stock insuficiente al agregar, carrito ya finalizado, caja sin turno abierto) |
| `422` | `ValidationError` / `BusinessRuleViolationError` | Regla de negocio o de forma incumplida (cantidad ≤ 0, carrito vacío, pago a crédito sin cliente) |
| `423` | `AccountLockedError` | Cuenta bloqueada por intentos fallidos de login |
| `400` | Cualquier otro `DomainError` | Poco frecuente — mensaje siempre en `detail` |

---

## 5. Concurrencia y múltiples dispositivos

- Cada carrito pertenece a un único usuario; dos dispositivos con el mismo usuario logueado verían/editarían el mismo carrito si comparten `draft_id` (no hay aislamiento por dispositivo, solo por usuario) — normalmente no es un problema porque cada login genera su propio flujo.
- La finalización de un carrito (`.../complete`) está protegida por un lock propio de cada carrito: dos solicitudes simultáneas sobre el mismo `draft_id` se serializan (una espera a la otra) y ambas reciben la misma venta como resultado — nunca se duplica. Carritos distintos no se bloquean entre sí.
- Todas las operaciones de lectura/escritura contra la base de datos reutilizan las mismas transacciones (`session_scope()`) que ya usa el escritorio — si algo fallara a mitad de camino, no queda nada escrito a medias (probado explícitamente con un escenario de stock agotado durante el cobro, ver PROGRESS.md Fase 4).

---

## 6. Ejemplo de flujo completo (curl)

```bash
BASE=http://192.168.1.50:8765

# 1. Login
TOKEN=$(curl -s -X POST "$BASE/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"cajero1","password":"clave-valida-123"}' | jq -r .token)

# 2. Buscar un producto
curl -s "$BASE/api/v1/products?q=coca" -H "Authorization: Bearer $TOKEN"

# 3. Crear el carrito
DRAFT=$(curl -s -X POST "$BASE/api/v1/sales/drafts" -H "Authorization: Bearer $TOKEN" | jq -r .draft_id)

# 4. Agregar un producto
curl -s -X POST "$BASE/api/v1/sales/drafts/$DRAFT/items" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"product_id": 12, "quantity": "2"}'

# 5. Cobrar
curl -s -X POST "$BASE/api/v1/sales/drafts/$DRAFT/complete" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"payments":[{"payment_method":"cash","amount":"7000.00"}]}'
```

---

## 7. Qué NO expone esta API (a propósito)

- CRUD de productos/categorías/usuarios/cargos/configuración — exclusivo del escritorio.
- CRUD de métodos de pago electrónico (crear/editar/activar/eliminar QR, Nequi, Bre-B) — exclusivo de Administración → Pagos electrónicos en el escritorio; §3.12 solo expone lectura del método predeterminado de cada tipo.
- Inventario (bodegas, movimientos manuales) — solo se consulta indirectamente vía disponibilidad al armar el carrito.
- Cobro con facturación electrónica automática e impresión — el escritorio sí los dispara después de `complete_sale`; la API no.
- Hardware local (básculas, cajones monedero, impresoras, lectores) — atado a una estación física concreta, no tiene sentido controlarlo desde un dispositivo remoto.
- Sincronización entre estaciones — protocolo aparte (`ws://.../ws/sync`), no lo consume un cliente de negocio como Android.

---

## 8. Recomendaciones para fases futuras

(Evaluadas durante la Fase 5, no implementadas — cada una habría requerido tocar código fuera del alcance de "solo mejoras estructurales" o cambiar comportamiento ya aprobado.)

- **Modo WAL de SQLite**: mejoraría la concurrencia real bajo escritura simultánea de múltiples dispositivos. No se activó esta fase porque el flujo de respaldo/restauración (`sqlite_file_ops.py`) copia el archivo `.db` directamente y no maneja los archivos `-wal`/`-shm` que ese modo genera — activarlo sin antes adaptar restauración es un riesgo real de inconsistencia. Requiere su propia fase.
- **Refresh token**: hoy la sesión dura 12 horas fijas, sin renovación — suficiente para un turno, pero una app que se queda abierta más tiempo forzaría un nuevo login. Agregar un endpoint de refresco es una funcionalidad nueva de autenticación, fuera del alcance de "no agregar funcionalidades".
- **Permiso `sales.create` en los endpoints de carrito** (Fase 3): hoy solo `complete`/`get_sale` lo exigen; construir el carrito no. Armonizarlo cambiaría el comportamiento de endpoints ya aprobados — se documenta la asimetría en vez de decidirlo unilateralmente.
- **Paginación a nivel de base de datos**: `GET /products` pagina en memoria sobre el resultado completo de `list_products()` — reduce el tamaño de la respuesta (lo que importa para un teléfono en red móvil) pero no el trabajo del servidor. Si el catálogo crece a decenas de miles de productos, valdría la pena un método de repositorio con `LIMIT`/`OFFSET` real en SQL.
- **CORS**: no se agregó — Android/desktop nativos no lo necesitan (es un mecanismo de navegador). Si en el futuro se construye un cliente web, hace falta agregarlo entonces.
- **Rate limiting general**: hoy solo `login` tiene protección contra fuerza bruta (heredada del escritorio). Se evaluó y se descartó agregar límites de tasa a los demás endpoints por ahora — este backend corre en la red local de un negocio, no expuesto a Internet público; revisar si eso cambia.
