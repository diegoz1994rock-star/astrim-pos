"""Catálogo por defecto de áreas y cargos, pensado para cubrir los tipos
de negocio más comunes desde el primer arranque (PROJECT_SPEC.md: el
sistema debe servir para "cualquier tipo de negocio"). No es una lista
fija: es solo el punto de partida — una vez sembrado, el catálogo vive
por completo en `job_areas`/`job_positions` y es editable desde la UI
("Áreas y cargos" dentro de Administración): crear, renombrar y eliminar
áreas y cargos personalizados no toca este módulo para nada.

Se ejecuta en dos escenarios: el script de sembrado (desarrollo/demos) y
el arranque real de la app empaquetada (`bootstrap_core` en `main.py`,
de forma incondicional en cada arranque — no solo en el primer run, para
que instalaciones ya existentes que todavía no tengan ninguna área
también reciban el catálogo por defecto)."""

from __future__ import annotations

from pos.core.database.session import session_scope
from pos.modules.job_positions.infrastructure.repository import JobPositionRepository

ADMIN_AREA_NAME = "Administración"
ADMIN_POSITION_NAME = "Administrador General"
"""El cargo de mayor jerarquía del sistema: reemplaza al antiguo rol de
administrador. Es el único con `grants_full_access=True` (ver
`JobPosition` en `infrastructure/models.py`) — ve todas las pantallas,
incluyendo Administración, Licencia, Backups y Sincronización."""

DEFAULT_JOB_CATALOG: list[tuple[str, list[str]]] = [
    (ADMIN_AREA_NAME, [ADMIN_POSITION_NAME]),
    (
        "Dirección y Administración",
        [
            "Propietario",
            "Socio",
            "Gerente General",
            "Administrador",
            "Jefe de Sucursal",
            "Supervisor",
            "Coordinador",
        ],
    ),
    (
        "Ventas y Atención al Cliente",
        [
            "Cajero",
            "Vendedor",
            "Asesor Comercial",
            "Ejecutivo de Ventas",
            "Atención al Cliente",
            "Recepcionista",
            "Anfitrión",
            "Mesero",
        ],
    ),
    (
        "Cocina y Alimentos",
        [
            "Chef",
            "Cocinero",
            "Auxiliar de Cocina",
            "Parrillero",
            "Panadero",
            "Pastelero",
            "Barista",
            "Bartender",
        ],
    ),
    (
        "Inventario y Logística",
        [
            "Jefe de Bodega",
            "Bodeguero",
            "Auxiliar de Bodega",
            "Almacenista",
            "Comprador",
            "Auxiliar de Compras",
            "Empacador",
            "Despachador",
            "Domiciliario",
            "Conductor",
        ],
    ),
    (
        "Producción",
        [
            "Operario",
            "Operador de Máquina",
            "Ensamblador",
            "Técnico de Producción",
            "Supervisor de Producción",
        ],
    ),
    (
        "Contabilidad y Finanzas",
        ["Contador", "Auxiliar Contable", "Tesorero", "Auditor", "Analista Financiero"],
    ),
    (
        "Recursos Humanos",
        [
            "Director de Recursos Humanos",
            "Jefe de Recursos Humanos",
            "Auxiliar de Recursos Humanos",
            "Reclutador",
            "Nómina",
        ],
    ),
    (
        "Tecnología",
        [
            "Administrador de Sistemas",
            "Soporte Técnico",
            "Desarrollador",
            "Analista de Sistemas",
            "Ingeniero de Software",
            "Administrador de Base de Datos",
        ],
    ),
    ("Compras", ["Jefe de Compras", "Comprador", "Analista de Compras"]),
    (
        "Mantenimiento",
        ["Técnico", "Electricista", "Mecánico", "Auxiliar de Mantenimiento", "Personal de Aseo"],
    ),
    ("Seguridad", ["Vigilante", "Guarda de Seguridad", "Portero"]),
    (
        "Transporte y Distribución",
        ["Conductor", "Repartidor", "Auxiliar de Ruta", "Coordinador Logístico"],
    ),
    (
        "Salud (para clínicas)",
        ["Médico", "Enfermero", "Auxiliar de Enfermería", "Odontólogo", "Recepcionista Médica"],
    ),
    (
        "Educación",
        ["Rector", "Director Académico", "Profesor", "Coordinador", "Secretaria Académica"],
    ),
    (
        "Hotelería",
        ["Recepcionista", "Camarero de Hotel", "Ama de Llaves", "Botones", "Gerente de Hotel"],
    ),
    (
        "Taller Automotriz",
        [
            "Mecánico",
            "Electricista Automotriz",
            "Jefe de Taller",
            "Asesor de Servicio",
            "Lavador de Vehículos",
        ],
    ),
    ("Farmacia", ["Regente de Farmacia", "Auxiliar de Farmacia", "Dependiente", "Cajero"]),
    (
        "Peluquería y Belleza",
        ["Estilista", "Barbero", "Manicurista", "Cosmetóloga", "Recepcionista"],
    ),
]


def ensure_default_job_catalog() -> None:
    """Crea el catálogo de áreas y cargos por defecto si todavía no existe
    ninguna área. Idempotente: si ya hay al menos un área (sembrada antes,
    o creada manualmente por el usuario), no hace nada."""
    with session_scope() as session:
        repo = JobPositionRepository(session)
        if repo.list_areas():
            return

        for area_name, position_names in DEFAULT_JOB_CATALOG:
            area = repo.create_area(name=area_name, description=None)
            for position_name in position_names:
                grants_full_access = (
                    area_name == ADMIN_AREA_NAME and position_name == ADMIN_POSITION_NAME
                )
                repo.create_position(
                    area_id=area.id, name=position_name, grants_full_access=grants_full_access
                )


def ensure_admin_position() -> None:
    """Garantiza que exista el área "Administración" con el cargo
    "Administrador General" marcado con `grants_full_access=True`, sin
    importar si el catálogo ya tenía áreas propias del usuario cuando se
    ejecutó `ensure_default_job_catalog` (que solo siembra en un catálogo
    completamente vacío). A diferencia de esa función, esta es idempotente
    por nombre específico, no por "¿ya hay áreas?" — puede llamarse en
    cada arranque sin duplicar nada, y además autorepara el flag si por
    alguna razón se hubiera perdido."""
    with session_scope() as session:
        repo = JobPositionRepository(session)
        area = repo.get_area_by_name(ADMIN_AREA_NAME)
        if area is None:
            area = repo.create_area(name=ADMIN_AREA_NAME, description=None)

        position = repo.get_position_by_area_and_name(area.id, ADMIN_POSITION_NAME)
        if position is None:
            repo.create_position(
                area_id=area.id, name=ADMIN_POSITION_NAME, grants_full_access=True
            )
        elif not position.grants_full_access:
            repo.set_grants_full_access(position, True)
