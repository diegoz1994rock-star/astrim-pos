# DATABASE.md

Visión conceptual del modelo de datos. Este documento se profundiza a nivel de tablas, columnas, índices y restricciones exactas en la Fase 3 (implementada junto con los modelos SQLAlchemy reales en `src/pos/modules/*/infrastructure/models.py` y las migraciones en `migrations/`). Aquí se fijan las **convenciones globales** y el **mapa de entidades por dominio**, que no deben contradecirse una vez implementado el esquema real.

## Convenciones globales

- Motor por defecto: SQLite (archivo `.db` local). Ver ARCHITECTURE.md §6 para la estrategia de portabilidad a PostgreSQL/MySQL.
- Toda tabla de negocio tiene: `id` (INTEGER PK autoincremental, uso interno/rendimiento) y `uuid` (TEXT, UUID4, único, usado por Sincronización y por cualquier referencia externa).
- Columnas de auditoría estándar: `created_at`, `updated_at` (UTC, ISO 8601), `created_by_user_id`, `updated_by_user_id`.
- **Soft delete**: las tablas con historial de negocio (productos, clientes, usuarios, ventas, etc.) usan `is_deleted` + `deleted_at` en lugar de `DELETE` físico. Tablas puramente de catálogo sin historial dependiente pueden usar borrado físico si se documenta explícitamente en su modelo.
- Nombres de tabla: `snake_case`, plural (`products`, `sale_items`).
- Toda relación foránea usa `ON DELETE RESTRICT` por defecto salvo que el negocio exija `CASCADE` explícitamente (ej. líneas de una venta al eliminar el encabezado de una venta en borrador no confirmada).
- Montos monetarios: almacenados como enteros en la unidad mínima de la moneda (centavos) o `DECIMAL` con precisión fija — nunca `FLOAT`, para evitar errores de redondeo en dinero.

## Mapa de entidades por dominio

**Identidad y acceso**
- `users`, `roles`, `permissions`, `role_permissions`, `user_sessions`, `login_attempts`.

**Terceros**
- `customers`, `customer_credit_movements`, `customer_loyalty_points`, `suppliers`.

**Catálogo**
- `categories` (jerárquica, `parent_id` autorreferenciado), `products`, `product_variants` (si aplica), `recipes` (producto compuesto → insumos), `recipe_items`, `combos`, `combo_items`, `taxes`, `product_taxes`.

**Inventario**
- `warehouses` (bodegas/puntos de almacenamiento), `stock_levels` (producto × bodega × cantidad), `stock_movements` (entrada/salida/transferencia/ajuste, tipo + referencia a documento origen), `product_batches` (lote, fecha de vencimiento), `stock_alerts_config` (umbrales por producto).

**Compras**
- `purchase_orders`, `purchase_order_items`, `purchase_receipts`.

**Ventas y facturación**
- `sales`, `sale_items`, `sale_payments` (múltiples medios de pago por venta), `invoices`, `promotions`, `promotion_rules`, `discounts_applied`.

**Restaurante / Cocina**
- `dining_tables`, `table_sessions` (ocupación de mesa), `orders`, `order_items`, `order_item_status_history` (pendiente/preparando/listo/entregado), `bill_splits`.

**Caja**
- `cash_registers` (puntos de caja), `cash_sessions` (apertura/cierre), `cash_movements` (ingreso/egreso manual, venta, arqueo).

**Configuración del negocio**
- `business_settings` (clave/valor tipado + tabla estructurada para datos fijos: nombre, logo, dirección, NIT, moneda), `printers_config`, `themes_config`.

**Licencias**
- `licenses`, `license_activations`, `license_verification_log`.

**Backups**
- `backup_jobs`, `backup_history`.

**Auditoría y notificaciones**
- `audit_log` (append-only: quién, qué, cuándo, entidad afectada, valores antes/después), `notifications`.

**Sincronización**
- `sync_stations` (estaciones registradas), `sync_log` (eventos propagados, estado de aplicación), `sync_conflicts`.

## Diagrama de relaciones de alto nivel

```
users ──< user_sessions
users ──< login_attempts
users >── roles ──< role_permissions >── permissions

customers ──< sales
customers ──< customer_credit_movements
customers ──< customer_loyalty_points

suppliers ──< purchase_orders ──< purchase_order_items >── products

categories ──< products
products ──< recipe_items >── products (insumo)
products ──< combo_items
products ──< product_taxes >── taxes

warehouses ──< stock_levels >── products
stock_movements >── products
stock_movements >── warehouses
product_batches >── products

sales >── customers
sales ──< sale_items >── products
sales ──< sale_payments
sales ──< invoices
sales >── cash_sessions

dining_tables ──< table_sessions ──< orders ──< order_items >── products
orders ──< order_item_status_history

cash_registers ──< cash_sessions ──< cash_movements

licenses ──< license_activations
licenses ──< license_verification_log

* ──< audit_log        (toda tabla de negocio es origen potencial de un registro de auditoría)
* ──< sync_log          (toda tabla sincronizable es origen potencial de un evento de sync)
```

## Índices previstos (mínimos, se amplían en Fase 3)

- Índice único en `uuid` de toda tabla sincronizable.
- Índice compuesto `(product_id, warehouse_id)` en `stock_levels`.
- Índice en `sales.created_at` y `sales.customer_id` para reportes.
- Índice en `audit_log.entity_type, entity_id` para consulta de historial por registro.
- Índice único `(username)` en `users`, `(email)` en `customers` cuando esté presente.

## Implementación (Fase 3 completada)

- Los 54 modelos SQLAlchemy están implementados en `src/pos/modules/*/infrastructure/models.py`, registrados centralmente en `src/pos/core/database/model_registry.py`.
- **Enums de estado**: se implementaron como `enum.Enum` de Python en `domain/enums.py` de cada módulo, mapeados con `sqlalchemy.Enum(..., native_enum=False)` — se almacenan como `VARCHAR` con `CHECK` constraint, portable entre SQLite/PostgreSQL/MySQL, sin necesitar una tabla de catálogo aparte para valores fijos que no cambian desde la UI (roles, permisos y promociones sí son configurables y por eso son tablas, no enums).
- **Montos monetarios**: `Numeric(12, 2)` (o `Numeric(14, 3)` para cantidades de inventario que pueden llevar decimales de peso/volumen), nunca `FLOAT`.
- Primera migración Alembic generada y verificada de punta a punta (`migrations/versions/`): crea las 54 tablas sobre SQLite limpio sin errores.
- Script de semilla `scripts/seed_demo_data.py`: roles predefinidos + permisos base, usuario `admin`, bodega principal, impuesto IVA de ejemplo, parámetros de negocio esenciales. Verificado end-to-end (migración + seed) contra una base SQLite real.
- `ruff check` y `mypy --strict` pasan sin errores sobre todo `src/`.

## Pendiente (deuda consciente, no bloqueante)

- Restricciones `CHECK` adicionales más allá de lo que Alembic/SQLAlchemy generan por defecto (ej. cantidades no negativas salvo ajustes de tipo "merma") — se añadirán vía migración incremental cuando se implemente la lógica de aplicación de cada módulo (Fase 4), no antes, para no adivinar reglas de negocio que aún no están codificadas.
- Diagrama entidad-relación visual (imagen) — el diagrama en texto de este documento es la referencia autoritativa por ahora; se puede generar una imagen con una herramienta externa (ej. `eralchemy`) sin cambiar el esquema.
