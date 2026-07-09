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

Los módulos **no se importan entre sí directamente** salvo a través de sus interfaces de dominio publicadas. Cuando un módulo necesita reaccionar a algo que ocurre en otro (ej. Inventario debe descontar stock cuando Ventas registra una venta), el módulo origen publica un evento de dominio (`SaleCompletedEvent`) en el bus (`core/events`), y el módulo interesado se suscribe a él en su capa de infraestructura/aplicación.

Esto evita el acoplamiento circular clásico de un POS ("Ventas importa Inventario importa Ventas para devoluciones...") y hace posible desactivar o reemplazar un módulo (ej. Cocina, en un negocio que no es restaurante) sin romper el resto.

Eventos son objetos inmutables simples (dataclasses) despachados de forma síncrona en el proceso local. Cuando el módulo de Sincronización esté activo, se suscribe también a estos eventos para propagarlos a otras estaciones.

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

## 11. App Android (fase posterior)

Cliente delgado sin base de datos propia: consume la misma API HTTP/WebSocket que expone el servidor principal de sincronización. No se diseña una capa de dominio adicional para Android; reutiliza los contratos (DTOs) ya definidos por el módulo de Sincronización/API.

## 12. Pruebas

- `domain` y `application` se prueban con **pytest** puro, sin Qt ni base de datos real (repositorios falsos en memoria que implementan las mismas interfaces).
- `infrastructure` se prueba contra una SQLite en memoria real (no mocks del ORM) para detectar problemas reales de esquema/consulta.
- `presentation` se prueba con `pytest-qt` para los flujos críticos (login, venta, cierre de caja).

## 13. Decisiones que se reconsiderarán y por qué

- **SQLite → PostgreSQL/MySQL**: la capa de repositorios está diseñada para que este cambio sea de configuración, pero se validará realmente cuando el volumen de estaciones sincronizadas lo justifique (documentado como deuda consciente, no ausencia de diseño).
- **Bus de eventos en memoria → cola real (ej. Redis) para sincronización a gran escala**: válido solo si el número de estaciones crece mucho; el diseño actual no lo bloquea porque la sincronización ya consume el bus de eventos como fuente, no está acoplada a que sea en memoria.
