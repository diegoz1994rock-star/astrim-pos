# TECHNOLOGIES.md

Stack tecnológico del proyecto y justificación de cada elección. No agregar una dependencia nueva sin registrarla aquí.

## Lenguaje

- **Python 3.11+** — lenguaje principal, exigido por el spec. 3.11 por mejoras de rendimiento sobre 3.10 y `tomllib` en stdlib.

## Interfaz gráfica

- **PySide6** (Qt 6) — exigido por el spec. Licencia LGPL, apta para distribución comercial sin costo de licenciamiento adicional (a diferencia de PyQt6 en proyectos cerrados). Soporte nativo para pantallas táctiles, QSS para theming, buen rendimiento en escritorio.

## Persistencia

- **SQLAlchemy 2.0** (ORM + Core) — capa de acceso a datos independiente del motor, requisito para la futura migración a PostgreSQL/MySQL sin reescribir la aplicación.
- **SQLite** — motor por defecto, cero configuración, un archivo por instalación.
- **Alembic** — migraciones versionadas del esquema.
- Motor alterno soportado desde el día uno a nivel de configuración: `psycopg` (PostgreSQL) / `mysqlclient` o `pymysql` (MySQL) se agregan como dependencias opcionales cuando se active esa fase, sin cambios de código en `domain`/`application`.

## Validación y DTOs

- **Pydantic v2** — validación de datos de entrada/salida en la capa `application` (DTOs), y para la carga/validación de archivos de configuración y tokens de licencia.

## Seguridad

- **argon2-cffi** — hashing de contraseñas (Argon2id).
- **cryptography** — firma/verificación Ed25519 para tokens de licencia, cifrado del almacenamiento local sensible (último timestamp visto, credenciales de sincronización).

## Servidor de sincronización / API

- **FastAPI** — servidor HTTP embebido en la estación designada como servidor principal.
- **Uvicorn** — servidor ASGI para correr FastAPI.
- **websockets** (vía FastAPI) — canal de sincronización en tiempo real entre estaciones y futura app Android.
- **httpx** — cliente HTTP en las estaciones/clientes para hablar con el servidor principal.

## Reportes y exportación

- **ReportLab** — generación de PDF.
- **openpyxl** — generación de archivos Excel (.xlsx).

## Tareas programadas

- **APScheduler** — backups automáticos programados, verificación periódica de licencia, limpieza de logs antiguos.

## Logging

- **logging** de stdlib con configuración centralizada en `core/logging` (handlers de archivo rotativo + consola). Se evita una dependencia externa de logging salvo que se demuestre necesidad real.

## Testing

- **pytest** — framework de pruebas.
- **pytest-qt** — pruebas de flujos de interfaz PySide6.
- **pytest-cov** — cobertura de pruebas.
- **factory_boy** o fábricas propias simples — generación de datos de prueba consistentes.

## Empaquetado y distribución

- **PyInstaller** — empaquetado de la app de escritorio como ejecutable Windows independiente (no requiere Python instalado en el equipo del cliente).
- **Inno Setup** — generación del instalador Windows tipo asistente ("Siguiente → Siguiente → Instalar → Finalizar").

## Calidad de código (herramientas de desarrollo, no runtime)

- **ruff** — linting y formateo (reemplaza flake8 + black + isort en una sola herramienta, más rápido).
- **mypy** — chequeo de tipos estático; el spec exige código mantenible y explícito, y el tipado ayuda a sostenerlo a lo largo de cientos de horas de desarrollo.

## App Android (fase posterior)

- Se define en detalle cuando se llegue a esa fase. Consumirá la misma API HTTP/WebSocket del módulo de Sincronización; la tecnología del cliente Android (Kotlin nativo vs. framework multiplataforma) se decidirá y documentará en ese momento, no antes.

## Gestión de dependencias

- **pyproject.toml** como única fuente de verdad de dependencias (formato PEP 621), gestionado con `uv` o `pip` + entorno virtual estándar. Sin `requirements.txt` duplicado y desincronizado.
