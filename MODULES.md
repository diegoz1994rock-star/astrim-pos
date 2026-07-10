# MODULES.md

Catálogo de todos los módulos del sistema. Cada módulo vive en `src/pos/modules/<nombre>/` siguiendo la estructura de capas de ARCHITECTURE.md. El estado de cada uno se mantiene sincronizado con PROGRESS.md y con la lista de tareas activa.

Leyenda de estado: `pendiente` · `en progreso` · `completo` · `fase posterior`

| Módulo | Carpeta | Depende de (vía eventos/dominio) | Estado |
|---|---|---|---|
| Configuración inicial / núcleo | `core/`, `modules/settings/` | — | completo |
| Base de datos | `core/database/`, `migrations/` | — | completo |
| Login / Autenticación | `modules/auth/` | users, roles | completo |
| Usuarios | `modules/users/` | roles | completo |
| Roles y Permisos | `modules/roles/` | — | completo |
| Clientes | `modules/customers/` | — | completo |
| Proveedores | `modules/suppliers/` | — | completo |
| Productos y Categorías | `modules/products/` | inventory (stock) | completo |
| Inventario | `modules/inventory/` | products | completo |
| Compras | `modules/purchasing/` | products, inventory, suppliers | pendiente |
| Ventas | `modules/sales/` | products, inventory, customers, cash_register | completo |
| Facturación / Impuestos | `modules/billing/` | sales, settings | pendiente |
| Caja | `modules/cash_register/` | — | completo |
| Mesas y Pedidos (Restaurante) | `modules/restaurant/` | sales, kitchen | pendiente |
| Cocina | `modules/kitchen/` | restaurant | pendiente |
| Promociones y Descuentos | `modules/promotions/` | products, sales | pendiente |
| Reportes | `modules/reports/` | sales, inventory, cash_register, customers, users, billing | completo (parcial: ventas/productos/inventario/caja; clientes/usuarios/impuestos/ganancias pendientes) |
| Configuración (panel admin) | `modules/settings/` | — | pendiente |
| Licencias | `modules/licensing/` | — | completo |
| Backups | `modules/backups/` | — | completo |
| Auditoría | `modules/audit/` | todos (suscriptor de eventos) | pendiente |
| Notificaciones | `modules/notifications/` | kitchen, inventory, licensing | pendiente |
| Sincronización / Servidor | `modules/sync/` | todos (suscriptor de eventos) | completo (transporte; el aplicador genérico por entidad queda como extensión futura, ver descripción) |
| App Android | `android/` | sync (vía API) | fase posterior |
| Instalador Windows | `installer/` | — | completo (config. lista; build en Windows real pendiente de ejecutar, ver installer/README.md) |

## Descripción por módulo

**Configuración inicial / núcleo** — Bootstrap de la aplicación: entrypoint, contenedor de DI, gestor de configuración editable desde UI (nombre del negocio, logo, moneda, dirección, NIT, etc.), gestor de temas claro/oscuro/personalizado.

**Base de datos** — Engine SQLAlchemy, sesión, Alembic, clase base declarativa, patrón Unit of Work compartido por todos los módulos.

**Login / Autenticación** — Pantalla de inicio de sesión, verificación de credenciales, gestión de sesión activa, bloqueo por intentos fallidos.

**Usuarios** — CRUD de usuarios del sistema (administrador, gerente, cajero, mesero, cocinero, bodeguero), asignación de rol.

**Roles y Permisos** — Roles predefinidos y personalizados, matriz de permisos granular por acción, aplicada tanto en UI como en la capa de aplicación.

**Clientes** — Datos de clientes, historial de compras, puntos de fidelidad, créditos y deudas.

**Proveedores** — Datos de proveedores, historial de compras asociadas.

**Productos y Categorías** — Productos simples y compuestos, recetas, combos, categorías jerárquicas.

**Inventario** — Entradas, salidas, transferencias entre bodegas, ajustes, control por lote y fecha de vencimiento, alertas de stock mínimo/agotado.

**Compras** — Órdenes de compra a proveedores, recepción de mercancía, actualización de inventario y costos.

**Ventas** — Registro de venta (POS), aplicación de promociones/descuentos/impuestos, múltiples medios de pago.

**Facturación / Impuestos** — Generación de comprobantes/facturas, cálculo de impuestos configurables por producto/región.

**Caja** — Apertura y cierre de caja, arqueos, movimientos de efectivo (ingresos/egresos manuales), cuadre.

**Mesas y Pedidos (Restaurante)** — Administración de mesas, estados, división de cuentas, unión de mesas, pedidos para llevar/domicilio/rápidos.

**Cocina** — Pantalla independiente (KDS) con pedidos entrantes automáticos y estados (pendiente/preparando/listo/entregado), notificación al mesero.

**Promociones y Descuentos** — Reglas de promoción configurables (por producto, categoría, combo, fecha/hora) sin tocar código.

**Reportes** — Ventas, ganancias/pérdidas, inventario, productos, clientes, usuarios, impuestos, caja, estadísticas; exportables a PDF y Excel.

**Configuración (panel admin)** — Superficie de UI que expone todo lo configurable del sistema (impresoras, backups, licencias, usuarios, permisos, promociones, categorías) sin editar código, según exige el spec.

**Licencias** — Activación por clave, tipos (prueba/mensual/anual/permanente), validación robusta no dependiente solo del reloj del sistema (ver ARCHITECTURE.md §9), bloqueo elegante al expirar.

**Backups** — Copias manuales y programadas (APScheduler + expresión cron) mediante `VACUUM INTO` para snapshots consistentes de SQLite, historial de ejecuciones y restauración con liberación previa del pool de conexiones (`dispose_engine()`), verificada sin necesidad de reiniciar la app.

**Auditoría** — Bitácora append-only de acciones sensibles del sistema, historial de cambios, consumidor del bus de eventos.

**Notificaciones** — Notificaciones internas entre módulos y hacia el usuario (ej. stock bajo, pedido listo en cocina, licencia por expirar).

**Sincronización / Servidor** — Servidor principal embebido (FastAPI + WebSocket) y clientes que sondean cada pocos segundos (no push instantáneo). Captura genérica de outbox: `core/events/bus.py::EventBus.subscribe_all` registra `SyncService.capture_event` para TODO evento de dominio publicado en el proceso, sin que cada módulo tenga que suscribirse a mano. Deduplicación/idempotencia por `entity_uuid` = `event_id` (ya un UUID por evento). Alcance de esta versión: transporte real y probado de punta a punta (dos estaciones, dos bases SQLite independientes, protocolo pull/push real por WebSocket); el "aplicador" genérico que reproduzca cada evento recibido sobre las tablas de negocio locales queda fuera a propósito y documentado como extensión futura — cada evento ya se persiste completo en `sync_log`, listo para que un aplicador futuro lo consuma.

**App Android** (fase posterior) — Cliente delgado sin base de datos propia, consume la API del servidor principal: tomar pedidos, cobrar, consultar mesas/productos.

**Instalador Windows** — `installer/pos.spec` (PyInstaller, modo `--onedir`, con `alembic.ini`/`migrations/` empaquetados e `hiddenimports` de `uvicorn`) + `installer/setup.iss` (Inno Setup, asistente en español, sin privilegios de administrador, no borra los datos del negocio al desinstalar). El primer arranque real quedó resuelto de punta a punta para que el instalador entregue una app usable sin pasos manuales: migraciones de Alembic automáticas (`core/database/migrate.py`) y una pantalla de configuración inicial que crea la cuenta de administrador cuando la base de datos está recién creada (`modules/users/presentation/first_run_setup_view.py`), verificado con un e2e real (licencia → configuración inicial → bienvenida). Pendiente, documentado en `installer/README.md`: un build real en una máquina Windows (PyInstaller no hace cross-compilación, no se pudo instalar en este entorno de desarrollo) y un ícono de aplicación.
