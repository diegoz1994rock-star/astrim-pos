"""Caso de uso central del módulo de Sincronización (ARCHITECTURE.md §10).

**Alcance de esta versión** (documentado también en PROGRESS.md): esta
primera pasada implementa el *transporte* — captura de cada evento de
dominio publicado en el bus local como entrada de un log de sincronización
(«outbox»), propagación entre estaciones vía WebSocket (`server/`,
`infrastructure/ws_client.py`) e inserción idempotente en el destino
(deduplicada por `entity_uuid`, que aquí es el `event_id` — ya un UUID
global de cada evento, ver `core/events/event.py`). Lo que queda **fuera**
de esta pasada, a propósito: un "aplicador" genérico que reproduzca cada
evento recibido sobre las tablas de negocio locales (crear el producto,
aplicar la venta, etc.) — eso requiere un aplicador idempotente por tipo de
entidad y se deja como punto de extensión futuro (cada evento ya queda
persistido en `sync_log` con su payload completo, listo para que un
aplicador futuro lo consuma). Por ahora el valor entregado es real:
visibilidad completa y en casi-tiempo-real de la actividad de todas las
estaciones de la red, con la mecánica de transporte ya resuelta.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.events.event import DomainEvent
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.modules.settings.infrastructure.models import SettingValueType
from pos.modules.sync.application.dto import SyncLogEntryDTO, SyncStationDTO, SyncStatusDTO
from pos.modules.sync.domain.enums import SyncLogStatus, SyncMode, SyncStationStatus
from pos.modules.sync.infrastructure.models import SyncLog, SyncStation
from pos.modules.sync.infrastructure.repository import SyncRepository

logger = logging.getLogger(__name__)

_DEFAULT_STATION_NAME_KEY = "sync_local_station_name"
_MODE_KEY = "sync_mode"
_PEER_URL_KEY = "sync_peer_url"
_SERVER_PORT_KEY = "sync_server_port"
_LAST_RECEIVED_AT_KEY = "sync_last_received_at"
_LAST_PUSHED_AT_KEY = "sync_last_pushed_at"
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, frozenset | set):
        return sorted(value)
    return str(value)


def _station_to_dto(station: SyncStation) -> SyncStationDTO:
    return SyncStationDTO(
        id=station.id,
        name=station.name,
        is_primary=station.is_primary,
        status=station.status,
        last_seen_at=station.last_seen_at,
    )


def _log_to_dto(entry: SyncLog, origin_name: str) -> SyncLogEntryDTO:
    return SyncLogEntryDTO(
        id=entry.id,
        event_type=entry.event_type,
        entity_type=entry.entity_type,
        entity_uuid=entry.entity_uuid,
        payload_json=entry.payload_json,
        status=entry.status,
        origin_station_name=origin_name,
        created_at=entry.created_at,
        applied_at=entry.applied_at,
    )


class SyncService:
    """Orquesta la configuración de sincronización y el log de eventos.

    No sabe nada de WebSockets: `server/app.py` y `infrastructure/ws_client.py`
    son los únicos que hablan el protocolo de red y lo hacen exclusivamente
    a través de los métodos públicos de esta clase.
    """

    def __init__(self, event_bus: EventBus, settings: BusinessSettingsService) -> None:
        self._event_bus = event_bus
        self._settings = settings

    # -- Captura de eventos locales (outbox) ---------------------------

    def capture_event(self, event: DomainEvent) -> None:
        """Suscrito globalmente al bus (`EventBus.subscribe_all`, ver
        `bootstrap_core`): persiste cada evento de dominio publicado en el
        proceso local como una entrada de outbox, sin bloquear al
        publicador si algo falla."""
        try:
            station = self._ensure_local_station()
            payload_json = json.dumps(dataclasses.asdict(event), default=_json_default)
            entity_type = type(event).__module__.split(".")[2]
            with session_scope() as session:
                repo = SyncRepository(session)
                if repo.has_entry_with_uuid(event.event_id):
                    return
                repo.append_log(
                    event_type=type(event).__name__,
                    entity_type=entity_type,
                    entity_uuid=event.event_id,
                    payload_json=payload_json,
                    origin_station_id=station.id,
                    created_at=event.occurred_at,
                    status=SyncLogStatus.PENDING,
                )
        except Exception:
            logger.exception("No se pudo registrar el evento %r en el log de sincronización", event)

    # -- Estación local --------------------------------------------------

    def get_local_station_name(self) -> str:
        return self._settings.get_str(_DEFAULT_STATION_NAME_KEY) or "Estación principal"

    def set_local_station_name(self, name: str) -> None:
        """Cambia el nombre configurado y, si la fila de estación local ya
        existe, la renombra en el momento (en vez de esperar a la próxima
        captura de evento) — evita una fila con el nombre viejo si se
        consulta `list_stations`/`list_local_origin_since` antes de que
        ocurra otro evento.

        Deliberadamente no usa `BusinessSettingsService` para nada que
        identifique la fila (ver `SyncStation.is_local`): escribir un
        parámetro de negocio publica `BusinessSettingChangedEvent`, que
        `capture_event` también captura — usar el mismo canal para
        bookkeeping puramente interno de este método terminaría
        registrando ese evento interno en el propio log de sincronización.
        """
        self._settings.set_value(_DEFAULT_STATION_NAME_KEY, name, SettingValueType.STRING)
        with session_scope() as session:
            repo = SyncRepository(session)
            station = repo.get_local_station()
            if station is not None:
                station.name = name

    def _ensure_local_station(self) -> SyncStationDTO:
        """Crea la fila de estación local (marcada `is_local=True`) una
        única vez y la reutiliza siempre, nunca por nombre — para no crear
        una fila duplicada si el nombre configurado cambia (el nombre de
        esa misma fila se actualiza en su lugar)."""
        name = self.get_local_station_name()
        is_primary = self.get_mode() is SyncMode.PRIMARY
        with session_scope() as session:
            repo = SyncRepository(session)
            station = repo.get_local_station()
            if station is None:
                station = repo.create_station(name=name, is_primary=is_primary, is_local=True)
            else:
                if station.name != name:
                    station.name = name
                if station.is_primary != is_primary:
                    station.is_primary = is_primary
            return _station_to_dto(station)

    # -- Configuración -----------------------------------------------------

    def get_mode(self) -> SyncMode:
        return SyncMode(self._settings.get_str(_MODE_KEY, SyncMode.DISABLED.value))

    def set_mode(self, mode: SyncMode) -> None:
        self._settings.set_value(_MODE_KEY, mode.value, SettingValueType.STRING)

    def get_peer_url(self) -> str | None:
        return self._settings.get_str(_PEER_URL_KEY)

    def set_peer_url(self, url: str) -> None:
        self._settings.set_value(_PEER_URL_KEY, url, SettingValueType.STRING)

    def get_server_port(self) -> int:
        return self._settings.get_int(_SERVER_PORT_KEY, 8765)

    def set_server_port(self, port: int) -> None:
        self._settings.set_value(_SERVER_PORT_KEY, str(port), SettingValueType.NUMBER)

    # -- Marcas de agua del cliente (cursores de reanudación) ------------

    def get_last_received_at(self) -> datetime:
        raw = self._settings.get_str(_LAST_RECEIVED_AT_KEY)
        return datetime.fromisoformat(raw) if raw else _EPOCH

    def set_last_received_at(self, value: datetime) -> None:
        self._settings.set_value(_LAST_RECEIVED_AT_KEY, value.isoformat(), SettingValueType.STRING)

    def get_last_pushed_at(self) -> datetime:
        raw = self._settings.get_str(_LAST_PUSHED_AT_KEY)
        return datetime.fromisoformat(raw) if raw else _EPOCH

    def set_last_pushed_at(self, value: datetime) -> None:
        self._settings.set_value(_LAST_PUSHED_AT_KEY, value.isoformat(), SettingValueType.STRING)

    # -- Registro de estaciones remotas ----------------------------------

    def register_peer_station(self, name: str) -> SyncStationDTO:
        with session_scope() as session:
            repo = SyncRepository(session)
            station = repo.get_station_by_name(name)
            if station is None:
                station = repo.create_station(name=name, is_primary=False)
            repo.set_station_status(
                station, status=SyncStationStatus.ONLINE, seen_at=datetime.now(UTC)
            )
            return _station_to_dto(station)

    def mark_station_offline(self, name: str) -> None:
        with session_scope() as session:
            repo = SyncRepository(session)
            station = repo.get_station_by_name(name)
            if station is not None:
                repo.set_station_status(
                    station, status=SyncStationStatus.OFFLINE, seen_at=datetime.now(UTC)
                )

    def list_stations(self) -> list[SyncStationDTO]:
        with session_scope() as session:
            repo = SyncRepository(session)
            return [_station_to_dto(station) for station in repo.list_stations()]

    # -- Intercambio de eventos (usado por server/ y ws_client.py) -------

    def record_remote_event(
        self,
        *,
        event_type: str,
        entity_type: str,
        entity_uuid: str,
        payload_json: str,
        origin_station_name: str,
        created_at: datetime,
    ) -> None:
        """Inserta de forma idempotente un evento recibido de un par remoto.

        Deduplica por `entity_uuid` (el `event_id` original del evento): si
        ya se registró antes —por este mismo par u otro—, no hace nada.
        """
        with session_scope() as session:
            repo = SyncRepository(session)
            if repo.has_entry_with_uuid(entity_uuid):
                return
            origin = repo.get_station_by_name(origin_station_name)
            if origin is None:
                origin = repo.create_station(name=origin_station_name, is_primary=False)
            repo.append_log(
                event_type=event_type,
                entity_type=entity_type,
                entity_uuid=entity_uuid,
                payload_json=payload_json,
                origin_station_id=origin.id,
                created_at=created_at,
                status=SyncLogStatus.APPLIED,
            )

    def list_local_origin_since(self, since: datetime) -> list[SyncLogEntryDTO]:
        """Entradas de origen local más recientes que `since` — lo que esta
        estación tiene para *enviar* a su par."""
        local_name = self.get_local_station_name()
        with session_scope() as session:
            repo = SyncRepository(session)
            local_station = repo.get_local_station()
            if local_station is None:
                return []
            entries = repo.list_local_origin_since(
                origin_station_id=local_station.id, since=since
            )
            return [_log_to_dto(entry, local_name) for entry in entries]

    def list_since_excluding_station(
        self, *, since: datetime, excluded_station_name: str
    ) -> list[SyncLogEntryDTO]:
        """Entradas más recientes que `since`, excluyendo las originadas por
        `excluded_station_name` — lo que se le responde a un par que hace
        `pull` (no tiene sentido reenviarle sus propios eventos)."""
        with session_scope() as session:
            repo = SyncRepository(session)
            excluded_station = repo.get_station_by_name(excluded_station_name)
            entries = repo.list_since_excluding_origin(
                since=since,
                excluded_origin_station_id=excluded_station.id if excluded_station else None,
            )
            names_by_id = {s.id: s.name for s in repo.list_stations()}
            return [
                _log_to_dto(entry, names_by_id.get(entry.origin_station_id, "?"))
                for entry in entries
            ]

    def list_recent(self, limit: int = 50) -> list[SyncLogEntryDTO]:
        with session_scope() as session:
            repo = SyncRepository(session)
            names_by_id = {s.id: s.name for s in repo.list_stations()}
            return [
                _log_to_dto(entry, names_by_id.get(entry.origin_station_id, "?"))
                for entry in repo.list_recent(limit)
            ]

    # -- Estado para la UI -------------------------------------------------

    def get_status(self, *, running: bool, connected: bool) -> SyncStatusDTO:
        pending = len(self.list_local_origin_since(self.get_last_pushed_at()))
        return SyncStatusDTO(
            mode=self.get_mode(),
            local_station_name=self.get_local_station_name(),
            peer_url=self.get_peer_url(),
            server_port=self.get_server_port(),
            running=running,
            connected=connected,
            pending_outbound_count=pending,
        )
