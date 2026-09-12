# ROADMAP.md

Hoja de ruta por hitos (no por fechas de calendario — este es un proyecto de alcance abierto, "cientos de horas" según el spec, y comprometerse a fechas sin datos reales de velocidad sería una promesa vacía). El estado vivo y detallado de cada hito se lleva en `PROGRESS.md`.

## M0 — Documentos de fundación (Fase 1 del spec)
ROADMAP.md, ARCHITECTURE.md, DATABASE.md, MODULES.md, FOLDER_STRUCTURE.md, TECHNOLOGIES.md, DEVELOPMENT_RULES.md.

## M1 — Estructura de carpetas (Fase 2 del spec)
Árbol de carpetas físico según FOLDER_STRUCTURE.md, `pyproject.toml`, configuración de linting/testing, esqueleto de `src/pos/main.py` sin lógica de negocio aún.

## M2 — Base de datos completa (Fase 3 del spec)
Modelos SQLAlchemy de todas las tablas descritas en DATABASE.md, primera migración Alembic, script de datos semilla.

## M3 — Núcleo y configuración inicial
`core/` completo: DI, config editable desde UI, gestor de temas, logging, bus de eventos, sesión.

## M4 — Identidad y acceso
Login, Usuarios, Roles y Permisos — funcionales de punta a punta (UI + aplicación + persistencia).

## M5 — Catálogo e inventario
Productos, Categorías, Inventario (entradas/salidas/lotes/vencimientos/alertas).

## M6 — Terceros
Clientes, Proveedores.

## M7 — Operación de venta
Ventas, Facturación/Impuestos, Caja.

## M8 — Operación de restaurante
Mesas y Pedidos, Cocina (KDS), Notificaciones.

## M9 — Reportes
Todos los reportes exigidos por el spec, exportación PDF/Excel.

## M10 — Comercialización
Licencias, Backups, Auditoría.

## M11 — Multi-estación
Sincronización y servidor principal.

## M12 — Distribución
Instalador Windows (PyInstaller + Inno Setup).

## M13 — Fase posterior
App Android (cliente delgado sobre la API del servidor principal).

## Orden de ejecución

El orden sigue el sugerido por PROJECT_SPEC.md ("DESARROLLO POR FASES"), con Clientes/Proveedores insertados antes de Ventas porque Ventas depende de Clientes, y Auditoría/Notificaciones como módulos transversales que se activan progresivamente a medida que otros módulos empiezan a emitir eventos, en vez de construirse de una sola vez al final.

## Política de avance

Modo de trabajo confirmado por el usuario: **autonomía total**, sin pausas de aprobación entre fases ni entre módulos. El progreso, las decisiones tomadas y el punto exacto donde retomar tras un corte de contexto se registran en `PROGRESS.md`, que debe leerse antes de continuar cualquier sesión de trabajo sobre este proyecto.
