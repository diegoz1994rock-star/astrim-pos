# FOLDER_STRUCTURE.md

Árbol de carpetas del proyecto. Refleja directamente las decisiones de ARCHITECTURE.md. Esta es la estructura objetivo; se construye en la Fase 2 y se puebla módulo por módulo en la Fase 4.

```
SUPER APP/
├── PROJECT_SPEC.md
├── ROADMAP.md
├── ARCHITECTURE.md
├── DATABASE.md
├── MODULES.md
├── FOLDER_STRUCTURE.md
├── TECHNOLOGIES.md
├── DEVELOPMENT_RULES.md
├── PROGRESS.md                     # estado de avance, se actualiza en cada sesión de trabajo
├── pyproject.toml                  # dependencias, metadata del paquete, configuración de herramientas
├── alembic.ini
├── .gitignore
│
├── src/
│   └── pos/                        # paquete raíz importable
│       ├── __init__.py
│       ├── main.py                 # entrypoint de la app de escritorio
│       │
│       ├── core/                   # núcleo transversal (sección 3 de ARCHITECTURE.md)
│       │   ├── config/
│       │   ├── di/
│       │   ├── database/
│       │   ├── security/
│       │   ├── events/
│       │   ├── logging/
│       │   └── exceptions/
│       │
│       ├── shared_ui/               # widgets, temas y helpers de UI reutilizables
│       │   ├── theme/
│       │   ├── widgets/
│       │   └── resources/           # iconos, imágenes de fondo, fuentes
│       │
│       └── modules/
│           ├── auth/                 # Login / autenticación / sesiones
│           ├── users/                # Usuarios
│           ├── roles/                # Roles y permisos
│           ├── customers/            # Clientes
│           ├── suppliers/            # Proveedores
│           ├── products/             # Productos, categorías, recetas, combos
│           ├── inventory/            # Inventario: entradas, salidas, lotes, vencimientos
│           ├── purchasing/           # Compras
│           ├── sales/                # Ventas
│           ├── billing/              # Facturación, impuestos
│           ├── cash_register/        # Caja
│           ├── restaurant/           # Mesas, pedidos, división de cuentas
│           ├── kitchen/              # Pantalla de cocina
│           ├── promotions/           # Promociones y descuentos
│           ├── reports/              # Reportes y exportación PDF/Excel
│           ├── settings/             # Configuración del negocio (panel admin)
│           ├── licensing/            # Licencias
│           ├── backups/              # Copias de seguridad
│           ├── audit/                # Bitácora / auditoría
│           ├── notifications/        # Notificaciones internas
│           └── sync/                 # Sincronización + servidor principal (API)
│               ├── domain/
│               ├── application/
│               ├── infrastructure/
│               ├── server/           # app FastAPI embebida, rutas, websockets
│               └── presentation/
│
│           # cada carpeta de módulo de negocio replica internamente:
│           #   domain/         entidades, value objects, interfaces de repositorio
│           #   application/    casos de uso, DTOs
│           #   infrastructure/ modelos SQLAlchemy, repositorios, adaptadores externos
│           #   presentation/   vistas y view models PySide6
│
├── migrations/                     # scripts Alembic (versionados, un historial único para toda la app)
│   └── versions/
│
├── tests/
│   ├── unit/                       # domain + application, por módulo, sin Qt ni DB real
│   ├── integration/                # infrastructure, SQLite en memoria
│   └── ui/                         # pytest-qt, flujos críticos
│
├── scripts/                        # utilidades de desarrollo (seed de datos demo, generación de licencias de prueba, etc.)
│
├── docs/                           # documentación ampliada por módulo (una vez exista código)
│   └── modules/
│
├── resources/                      # activos de marca por defecto (logo placeholder, temas de ejemplo)
│
├── installer/                      # script de Inno Setup y assets del instalador de Windows
│
└── android/                        # app cliente Android (fase posterior, proyecto independiente)
```

## Convenciones de nombres

- Carpetas y módulos Python: `snake_case`, en inglés (ver DEVELOPMENT_RULES.md para la razón).
- Un módulo de negocio nunca importa directamente la carpeta `infrastructure/` de otro módulo; solo su `domain/` (interfaces) si es estrictamente necesario, y preferentemente ni eso — se prefiere el bus de eventos (ver ARCHITECTURE.md sección 5).
- Todo módulo nuevo se agrega como una carpeta hermana bajo `modules/`, nunca anidado dentro de otro módulo.
