# ARCHITECTURE.md

Arquitectura técnica del sistema POS. Este documento es la referencia obligatoria para toda decisión de diseño futura. Cualquier cambio a la arquitectura aquí descrita debe reflejarse en este archivo en el mismo commit que lo introduce.

## 1. Estilo arquitectónico

**Monolito modular con Clean Architecture aplicada por módulo.**

No usamos microservicios: la complejidad operativa (despliegue, red, consistencia distribuida) no se justifica para un POS de estación única o de pocas estaciones sincronizadas. En su lugar, cada dominio de negocio (Usuarios, Productos, Inventario, Ventas, etc.) es un **módulo autocontenido** con sus propias capas internas, y todos los módulos se empaquetan y despliegan como una sola aplicación de escritorio (más un proceso opcional de servidor de sincronización).

Esto satisface el requisito del spec ("cada módulo debe poder mantenerse de manera independiente") sin pagar el costo de una arquitectura distribuida real.

## 2. Capas dentro de cada módulo

Cada módulo en `src/modules/<modulo>/` tiene cuatro capas, en este orden de dependencia (las flechas indican "depende de"):

```
presentation  →  application  →  domain  ←  infrastructure
```

- **domain/**: Entidades de negocio puras (dataclasses), value objects, reglas de negocio invariantes, e **interfaces** de repositorio (`Protocol` o ABC). No importa nada de SQLAlchemy, PySide6 ni ninguna librería externa. Es el corazón del módulo y el único código que casi nunca cambia.
- **application/**: Casos de uso (servicios de aplicación) que orquestan entidades de dominio para cumplir una acción concreta ("RegistrarVenta", "AjustarInventario"). Define DTOs de entrada/salida. Depende solo de `domain`.
- **infrastructure/**: Implementaciones concretas de las interfaces de dominio: modelos SQLAlchemy, repositorios concretos, adaptadores a impresoras, servicios externos. Depende de `domain` (implementa sus interfaces) pero el dominio nunca depende de infraestructura.
- **presentation/**: Vistas y widgets PySide6, view models (QObject con señales) que llaman a `application`. Depende de `application`.

Regla dura: **el dominio no importa nada de infraestructura ni de presentación.** Esto es lo que permite migrar de SQLite a PostgreSQL/MySQL cambiando solo `infrastructure/`, y es lo que hace testeable la lógica de negocio sin levantar una UI ni una base de datos real.

## 3. Núcleo compartido (`src/core/`)

Código transversal usado por todos los módulos, nunca al revés:

- `core/config/` — gestor de configuración (lee/escribe configuración del negocio: nombre, logo, moneda, impuestos, tema, etc. desde la base de datos, no desde archivos estáticos, para que sea editable desde la UI en caliente).
- `core/di/` — contenedor de inyección de dependencias simple (registro de fábricas/singletons, sin framework pesado tipo Spring).
- `core/database/` — engine SQLAlchemy, `Session` factory, clase base declarativa, gestor de migraciones Alembic.
- `core/security/` — hashing de contraseñas (Argon2), gestión de sesión activa, control de intentos fallidos.
- `core/events/` — bus de eventos interno en memoria (ver sección 5).
- `core/logging/` — configuración centralizada de logs (rotación, niveles, formato).
- `core/exceptions/` — jerarquía de excepciones de negocio compartida.

## 4. Módulos compartidos de presentación (`src/shared_ui/`)

Widgets reutilizables (teclado táctil numérico, tabla con paginación, selector de fecha, diálogo de confirmación, componentes de tema), el `ThemeManager` (claro/oscuro/personalizado vía QSS + tokens de color) y helpers de layout responsivo. Ningún módulo de negocio debe reimplementar un widget genérico; todo widget genérico vive aquí.

## 5. Comunicación entre módulos: bus de eventos interno

Los módulos **no importan la infraestructura de otro módulo directamente** (ver §12b), pero sí pueden depender de la capa `application` de otro módulo cuando esa dependencia es intencional y está documentada en MODULES.md (ej. Ventas depende de Inventario, Caja y Clientes). Cuando un módulo necesita reaccionar a algo que ocurre en otro sin que exista esa dependencia documentada (ej. Inventario inicializa el stock cuando Productos crea un producto nuevo), el módulo origen publica un evento de dominio en el bus (`core/events`) y el módulo interesado se suscribe a él — ver `InventoryProductEventHandlers` como referencia.

Esto evita el acoplamiento circular clásico de un POS ("Ventas importa Inventario importa Ventas para devoluciones...") y hace posible desactivar o reemplazar un módulo (ej. Cocina, en un negocio que no es restaurante) sin romper el resto.

Eventos son objetos inmutables simples (dataclasses) despachados de forma síncrona en el proceso local. Cuando el módulo de Sincronización esté activo, se suscribe también a estos eventos para propagarlos a otras estaciones.

### 5b. Cuándo usar un evento vs. una llamada directa a otro servicio de aplicación

No todo se resuelve con un evento. La regla:

- **Efecto derivado, no crítico, tolerante a consistencia eventual** → evento. Ejemplo: crear el `StockLevel` en 0 cuando se crea un producto — si ese handler tardara un instante o incluso fallara una vez, no compromete ninguna operación de negocio en curso.
- **Efecto que debe suceder atómicamente como parte de la misma operación de negocio, donde una falla debe abortar toda la operación** → llamada directa síncrona al servicio de aplicación del otro módulo, dejando que la excepción se propague. Ejemplo: al completar una venta, Ventas llama directamente a `InventoryService.register_exit(...)` (no hay stock suficiente → la venta no se completa), a `CashRegisterService` (no hay turno de caja abierto → la venta no se completa) y, si aplica, a `CustomerManagementService.register_credit_movement(...)` (excede el cupo → la venta no se completa). `SaleCompletedEvent` igual se publica al final, pero solo para consumidores de solo lectura que no deben poder bloquear la venta (Auditoría, Reportes, Notificaciones, Sincronización).

**Limitación conocida y aceptada**: cada servicio de aplicación abre su propia transacción (`session_scope()`) de forma independiente — no existe hoy una transacción distribuida real entre, por ejemplo, la inserción de la venta y el descuento de inventario. Para mitigar el riesgo se valida todo lo posible *antes* de mutar nada (stock suficiente, turno abierto, cupo de crédito disponible) y se ordenan las mutaciones de la menos reversible a la más reversible. Si en el futuro esto demuestra ser insuficiente (más probable con Sincronización multi-estación real), la solución es un patrón saga/outbox explícito — no se implementa preventivamente sin evidencia de que se necesita.

## 6. Acceso a datos y ruta de migración a PostgreSQL/MySQL

- ORM: **SQLAlchemy 2.0** (estilo declarativo + `Session`), nunca SQL crudo dependiente del dialecto en `application` o `domain`.
- Migraciones: **Alembic**, con generación de scripts revisada manualmente (no autogenerate ciego) para columnas sensibles.
- Patrón **Repositorio + Unit of Work**: cada módulo define su interfaz de repositorio en `domain/`, la implementa en `infrastructure/` usando SQLAlchemy. El `UnitOfWork` envuelve una transacción y expone los repositorios necesarios para un caso de uso.
- **SQLite es el motor por defecto** (archivo local, cero configuración, ideal para instalación de un solo usuario). El motor se selecciona por cadena de conexión en `core/config`; cambiar a PostgreSQL o MySQL es un cambio de configuración, no de código, siempre que no se haya usado SQL específico de dialecto.
- Identidad de filas: clave primaria `INTEGER` autoincremental local **más** una columna `uuid` (UUID4) globalmente única en toda tabla sincronizable. La PK local optimiza rendimiento e índices en SQLite; el `uuid` es lo que usa el módulo de Sincronización para identificar el mismo registro entre estaciones distintas y lo que usará una futura base central PostgreSQL como referencia externa.
- Columnas de auditoría estándar en toda tabla de negocio: `created_at`, `updated_at`, `created_by`, `updated_by`, `is_deleted` (soft delete — nunca se borra físicamente un registro con historial de negocio; ver DATABASE.md).

## 7. Interfaz gráfica (PySide6)

- Patrón **MVVM ligero**: `View` (QWidget/QMainWindow) es tonta y solo dibuja + emite señales de interacción; `ViewModel` (QObject con señales/slots) traduce interacción de usuario en llamadas a casos de uso de `application` y expone estado observable a la vista. Esto mantiene la lógica de UI testeable sin instanciar Qt.
- Estilos vía **QSS** generado a partir de un set de tokens de diseño (colores, radios, tipografía) definidos en `shared_ui/theme/`. Modo claro, oscuro y "personalizado" son tres conjuntos de tokens; cambiar de tema es cambiar el conjunto activo, nunca tocar QSS por pantalla.
- Diseño responsivo mediante layouts de Qt (`QGridLayout`, `QSizePolicy`) y breakpoints simples según tamaño de ventana/resolución, pensado primero para pantallas táctiles (controles grandes, sin dependencia de hover).

## 8. Seguridad

- Contraseñas con **Argon2id** (`argon2-cffi`), nunca MD5/SHA plano.
- Sesión activa gestionada en `core/security/session.py`: usuario autenticado, rol efectivo, expiración por inactividad configurable.
- Autorización: decorador/guardia `@require_permission("ventas.crear")` aplicado en la capa `application`, no solo oculto en la UI (ocultar un botón no es control de acceso).
- Toda acción sensible (login, cambios de configuración, ediciones de inventario, anulaciones de venta, cambios de permisos) publica un evento de auditoría consumido por el módulo de Auditoría, que lo persiste en una tabla append-only.
- Bloqueo de cuenta tras N intentos fallidos configurables, con desbloqueo temporizado o manual por administrador.

## 9. Licenciamiento (no depende únicamente del reloj del sistema)

Problema: si la validación de licencia solo compara la fecha actual del sistema contra una fecha de expiración, basta con atrasar el reloj de Windows para evadirla. Mecanismo propuesto:

1. Al activar una licencia, el servidor de licencias (o un generador offline controlado por el vendedor) emite un **token firmado** (Ed25519) que contiene: `license_id`, `hardware_fingerprint`, `tipo`, `fecha_emision`, `fecha_expiracion`, `checksum`. La app embebe la **clave pública** del vendedor; nunca la privada.
2. La app verifica la firma del token en cada arranque: si la firma no valida contra la clave pública embebida, la licencia se considera inválida sin importar su contenido.
3. **Anti-retroceso de reloj**: la app mantiene un "último timestamp visto" cifrado en almacenamiento local (actualizado en cada arranque y periódicamente mientras corre). Si el reloj del sistema retrocede respecto al último timestamp visto más allá de una tolerancia (ej. cambio de zona horaria legítimo), la app marca el estado como "no verificado" y exige una revalidación en línea.
4. **Verificación en línea oportunista**: si hay conexión a internet, la app contrasta la hora contra un servidor NTP/HTTPS de confianza (o el propio servidor de licencias) y refresca el "último timestamp visto". Sin conexión, opera en modo offline con un período de gracia limitado (ej. 7 días) desde la última verificación exitosa.
5. `hardware_fingerprint` (derivado de identificadores estables de la máquina, con hash de un solo sentido) ata la licencia a la estación activada, evitando copiar el token a otro equipo.
6. Al expirar: bloqueo elegante de las pantallas operativas (no un crash), con pantalla dedicada mostrando estado de la licencia y datos de contacto del proveedor; los datos del negocio **nunca se bloquean ni se pierden**, solo el acceso operativo.

Detalle completo de tablas y flujos en el módulo de Licencias (Fase 4).

## 10. Sincronización multi-estación

- Una estación se designa **servidor principal**: corre un proceso adicional embebido (**FastAPI** + WebSockets) expuesto en la red local.
- Las demás estaciones son **clientes de sincronización**: mantienen su propia SQLite local (operación offline-first) y sincronizan cambios contra el servidor principal vía WebSocket para tiempo real, con reintento/cola si se pierde la conexión.
- Unidad de sincronización: los mismos eventos de dominio del bus interno (sección 5), serializados y despachados a través de la red, aplicados de forma idempotente en el destino usando el `uuid` global del registro.
- Resolución de conflictos: **last-write-wins basado en `updated_at` + número de versión por fila**, con registro de todo conflicto detectado en auditoría para revisión manual — aceptable porque el dominio POS es mayormente de alta (ventas, pedidos) y las ediciones concurrentes del mismo registro son raras.
- La app funciona igual de bien sin este módulo activo (estación única, sin red): la sincronización es opt-in vía configuración, no una dependencia dura del núcleo.

### 10b. Implementación real (Fase M11) y su alcance

- **Captura genérica**: `EventBus` gana un segundo canal, `subscribe_all(handler)` (además de `subscribe(tipo, handler)`), invocado con TODO evento publicado sin importar su tipo. `SyncService.capture_event` se registra ahí en `bootstrap_core` — así ningún módulo nuevo necesita agregar a mano una suscripción de sincronización además de sus suscripciones de negocio; el outbox queda siempre completo por construcción.
- **Idempotencia práctica**: en vez de depender de que cada evento cargue el `uuid` propio de la fila que describe (la mayoría hoy usa el id local entero, no el `uuid` global), la deduplicación usa `event_id` — ya un UUID que el bus asigna a todo evento (`core/events/event.py`). Es la unidad de sincronización real: "no proceses el mismo evento dos veces", no "resuelve el mismo registro entre estaciones a nivel de fila". Documentado como decisión pragmática, no una desviación silenciosa del diseño original.
- **Protocolo**: un único endpoint WebSocket (`modules/sync/server/app.py`) con un intercambio `pull`/`push` **siempre iniciado por el cliente** (el servidor nunca empuja por su cuenta), repetido cada pocos segundos mientras la conexión está abierta. Es "casi tiempo real", no push instantáneo — simplificación deliberada que evita necesitar un mecanismo de difusión asíncrona entre hilos dentro del servidor embebido, a cambio de unos segundos de latencia aceptables para un POS.
- **Fuera de alcance, a propósito**: un aplicador genérico que reproduzca cada evento recibido sobre las tablas de negocio locales (crear el producto, aplicar la venta, etc. en la estación remota). Cada evento ya llega y se persiste completo (con su payload) en `sync_log` de la estación receptora — la mecánica de transporte está resuelta y probada de punta a punta (ver `tests/integration/sync/test_sync_transport_e2e.py`, dos procesos con bases SQLite independientes); construir el aplicador idempotente por tipo de entidad queda como trabajo futuro cuando haga falta reproducir el efecto de negocio, no solo verlo en el historial.

## 11. App Android (fase posterior)

Cliente delgado sin base de datos propia: consume la misma API HTTP/WebSocket que expone el servidor principal de sincronización. No se diseña una capa de dominio adicional para Android; reutiliza los contratos (DTOs) ya definidos por el módulo de Sincronización/API.

## 12. Pruebas

- `domain` y `application` se prueban con **pytest** puro, sin Qt ni base de datos real (repositorios falsos en memoria que implementan las mismas interfaces).
- `infrastructure` se prueba contra una SQLite en memoria real (no mocks del ORM) para detectar problemas reales de esquema/consulta.
- `presentation` se prueba con `pytest-qt` para los flujos críticos (login, venta, cierre de caja).

## 12b. Convención ORM para no acoplar módulos vía claves foráneas

Los modelos SQLAlchemy de un módulo pueden necesitar una clave foránea hacia una tabla de otro módulo (ej. `sale_items.product_id` → `products.id`). Para no violar la regla de "un módulo no importa la infraestructura de otro" (sección 5), la convención es:

- La `ForeignKey` se declara por **nombre de tabla en string** (`ForeignKey("products.id")`), nunca importando la clase ORM del otro módulo.
- No se declaran atributos `relationship()` de navegación **entre módulos distintos** (sí se permiten dentro del mismo módulo, ej. `Sale.items`). Para obtener datos relacionados de otro módulo se hace una consulta explícita a través del repositorio de ese módulo, o se consume vía evento.
- Todos los modelos comparten la misma `Base`/`MetaData` (`core/database/base.py`) para que Alembic pueda generar un único historial de migraciones consistente, aunque el código Python de cada módulo permanezca desacoplado.

## 13. Decisiones que se reconsiderarán y por qué

- **SQLite → PostgreSQL/MySQL**: la capa de repositorios está diseñada para que este cambio sea de configuración, pero se validará realmente cuando el volumen de estaciones sincronizadas lo justifique (documentado como deuda consciente, no ausencia de diseño).
- **Bus de eventos en memoria → cola real (ej. Redis) para sincronización a gran escala**: válido solo si el número de estaciones crece mucho; el diseño actual no lo bloquea porque la sincronización ya consume el bus de eventos como fuente, no está acoplada a que sea en memoria.
