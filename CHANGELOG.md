# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).
La versión de referencia es `[project].version` en `pyproject.toml` — es la
única fuente de verdad; el instalador y el `.exe` la leen de ahí (ver
`README_BUILD.md`).

## [2.1.0]

### Agregado
- Botón "Acerca de" en la barra superior (junto a "Cerrar sesión") que abre
  un diálogo con la versión instalada y el aviso de copyright completo.

## [2.0.0] — primera versión distribuible con instalador de Windows

### Agregado
- Instalador profesional de Windows (PyInstaller + Inno Setup): el cliente
  final ya no necesita Python instalado. Crea accesos directos de
  Escritorio y Menú Inicio, permite elegir carpeta de instalación,
  registra la app en "Programas y características" con desinstalador, y
  soporta actualizar una instalación existente sin perder datos.
- Validación de licencia por Hardware ID: la app Android generadora de
  licencias antepone un prefijo derivado del Hardware ID del equipo del
  cliente al código del pool (`XXXX-XXXX-ASTR-XXXX-XXXX-XXXX-XXXX`); el
  POS lo valida antes de consultar el pool de licencias.
- Módulo de facturación: comprobante en PDF generado a partir de una venta.
- Módulo de restaurante: gestión de mesas, pedidos y pantalla de cocina.
- Módulo de promociones y descuentos con aplicación automática en Ventas.
- Sincronización multi-estación real vía WebSocket.
- Módulo de copias de seguridad (VACUUM INTO, restauración, programación
  automática con APScheduler).
- Módulo de licencias por pool de códigos pre-generados (reemplaza el
  esquema anterior de firma Ed25519), con verificación periódica
  anti-retroceso de reloj.
- Módulos de reportes, ventas, caja, clientes/proveedores, inventario,
  productos/categorías, usuarios/roles, autenticación y el núcleo de la
  aplicación (configuración de arranque, logging, eventos, DI, seguridad,
  temas).

### Notas de la primera instalación
El primer arranque aplica las migraciones de Alembic automáticamente y
muestra una pantalla de configuración inicial (creación del usuario
administrador) en vez de un login vacío. La licencia se activa aparte,
antes de esa pantalla.
