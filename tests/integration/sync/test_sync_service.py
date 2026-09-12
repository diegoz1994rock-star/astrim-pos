"""Pruebas de integración de `SyncService` contra SQLite real."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from pos.core.events.event import DomainEvent
from pos.modules.sync.domain.enums import SyncLogStatus, SyncMode
from tests.integration.sync.conftest import SyncFixtures


@dataclass(frozen=True, kw_only=True)
class _FakeProductCreatedEvent(DomainEvent):
    product_id: int
    sku: str


def _make_event(sku: str = "SKU-1") -> _FakeProductCreatedEvent:
    return _FakeProductCreatedEvent(product_id=1, sku=sku)


def test_capture_event_persists_entry_as_pending(sync_env: SyncFixtures) -> None:
    event = _make_event()

    sync_env.service.capture_event(event)

    recent = sync_env.service.list_recent()
    assert len(recent) == 1
    assert recent[0].entity_uuid == event.event_id
    assert recent[0].status is SyncLogStatus.PENDING
    assert recent[0].event_type == "_FakeProductCreatedEvent"


def test_capture_event_is_idempotent_by_event_id(sync_env: SyncFixtures) -> None:
    event = _make_event()

    sync_env.service.capture_event(event)
    sync_env.service.capture_event(event)

    assert len(sync_env.service.list_recent()) == 1


def test_event_bus_wiring_reaches_sync_service(sync_env: SyncFixtures) -> None:
    """Prueba de extremo a extremo del punto de extensión `subscribe_all`
    (ver `main.py::bootstrap_core`): publicar en el bus, sin llamar
    `capture_event` directamente, debe terminar en `sync_log`."""
    sync_env.event_bus.subscribe_all(sync_env.service.capture_event)

    sync_env.event_bus.publish(_make_event(sku="SKU-2"))

    recent = sync_env.service.list_recent()
    assert len(recent) == 1
    assert recent[0].event_type == "_FakeProductCreatedEvent"


def test_mode_and_peer_config_round_trip(sync_env: SyncFixtures) -> None:
    assert sync_env.service.get_mode() is SyncMode.DISABLED

    sync_env.service.set_mode(SyncMode.CLIENT)
    sync_env.service.set_peer_url("ws://192.168.1.10:8765/ws/sync")
    sync_env.service.set_server_port(9999)

    assert sync_env.service.get_mode() is SyncMode.CLIENT
    assert sync_env.service.get_peer_url() == "ws://192.168.1.10:8765/ws/sync"
    assert sync_env.service.get_server_port() == 9999


def test_record_remote_event_is_idempotent_by_entity_uuid(sync_env: SyncFixtures) -> None:
    now = datetime.now(UTC)
    kwargs = dict(
        event_type="SaleCompletedEvent",
        entity_type="sales",
        entity_uuid="11111111-1111-1111-1111-111111111111",
        payload_json="{}",
        origin_station_name="Estación Remota",
        created_at=now,
    )

    sync_env.service.record_remote_event(**kwargs)
    sync_env.service.record_remote_event(**kwargs)

    recent = sync_env.service.list_recent()
    assert len(recent) == 1
    assert recent[0].status is SyncLogStatus.APPLIED
    assert recent[0].origin_station_name == "Estación Remota"


def test_list_local_origin_since_only_returns_local_entries(sync_env: SyncFixtures) -> None:
    sync_env.service.set_local_station_name("Local")
    sync_env.service.capture_event(_make_event())
    sync_env.service.record_remote_event(
        event_type="X",
        entity_type="y",
        entity_uuid="22222222-2222-2222-2222-222222222222",
        payload_json="{}",
        origin_station_name="Otra Estación",
        created_at=datetime.now(UTC),
    )

    local_only = sync_env.service.list_local_origin_since(datetime(1970, 1, 1, tzinfo=UTC))

    assert len(local_only) == 1
    assert local_only[0].origin_station_name == "Local"


def test_list_since_excluding_station_omits_requesting_station(sync_env: SyncFixtures) -> None:
    sync_env.service.set_local_station_name("Servidor")
    sync_env.service.capture_event(_make_event(sku="local-origin"))
    sync_env.service.record_remote_event(
        event_type="X",
        entity_type="y",
        entity_uuid="33333333-3333-3333-3333-333333333333",
        payload_json="{}",
        origin_station_name="Cliente A",
        created_at=datetime.now(UTC),
    )

    for_client_a = sync_env.service.list_since_excluding_station(
        since=datetime(1970, 1, 1, tzinfo=UTC), excluded_station_name="Cliente A"
    )

    assert len(for_client_a) == 1
    assert for_client_a[0].origin_station_name == "Servidor"


def _status(sync_env: SyncFixtures, *, running: bool = False, connected: bool = False):
    return sync_env.service.get_status(
        running=running,
        connected=connected,
        local_ip="127.0.0.1",
        websocket_url="ws://127.0.0.1:8765/ws/sync",
        uptime_seconds=None,
        last_error=None,
        connections_count=0,
    )


def test_status_reports_pending_outbound_count(sync_env: SyncFixtures) -> None:
    sync_env.service.capture_event(_make_event())

    status = _status(sync_env, running=True, connected=False)

    assert status.pending_outbound_count == 1
    assert status.running is True
    assert status.connected is False


def test_register_and_offline_station_lifecycle(sync_env: SyncFixtures) -> None:
    station = sync_env.service.register_peer_station("Cliente B")
    assert station.name == "Cliente B"

    sync_env.service.mark_station_offline("Cliente B")

    stations = sync_env.service.list_stations()
    offline = next(s for s in stations if s.name == "Cliente B")
    from pos.modules.sync.domain.enums import SyncStationStatus

    assert offline.status is SyncStationStatus.OFFLINE


def test_mark_local_station_online_fixes_the_local_row(sync_env: SyncFixtures) -> None:
    """El bug raíz que hacía que la propia estación mostrara "Fuera de
    línea" para siempre: `_ensure_local_station` (usado por
    `capture_event`) nunca tocaba `status`, solo `mark_local_station_online`
    lo hace de verdad."""
    sync_env.service.set_local_station_name("Esta estación")
    sync_env.service.capture_event(_make_event())
    local_before = next(
        s for s in sync_env.service.list_stations() if s.name == "Esta estación"
    )
    from pos.modules.sync.domain.enums import SyncStationStatus

    assert local_before.status is SyncStationStatus.OFFLINE

    sync_env.service.mark_local_station_online()

    local_after = sync_env.service.get_local_station()
    assert local_after is not None
    assert local_after.status is SyncStationStatus.ONLINE

    sync_env.service.mark_local_station_offline()

    assert sync_env.service.get_local_station().status is SyncStationStatus.OFFLINE


def test_count_sent_and_received(sync_env: SyncFixtures) -> None:
    sync_env.service.set_local_station_name("Local")
    sync_env.service.capture_event(_make_event(sku="sent-1"))
    sync_env.service.capture_event(_make_event(sku="sent-2"))
    sync_env.service.record_remote_event(
        event_type="X",
        entity_type="y",
        entity_uuid="44444444-4444-4444-4444-444444444444",
        payload_json="{}",
        origin_station_name="Otra Estación",
        created_at=datetime.now(UTC),
    )

    assert sync_env.service.count_received() == 1
    assert sync_env.service.count_sent() == 0  # nada confirmado como enviado todavía

    sync_env.service.set_last_pushed_at(datetime.now(UTC))

    assert sync_env.service.count_sent() == 2
    assert sync_env.service.count_failed() == 0


def test_auto_start_enabled_defaults_true_and_round_trips(sync_env: SyncFixtures) -> None:
    assert sync_env.service.get_auto_start_enabled() is True

    sync_env.service.set_auto_start_enabled(False)

    assert sync_env.service.get_auto_start_enabled() is False


def test_last_received_and_pushed_watermarks_default_to_epoch(sync_env: SyncFixtures) -> None:
    assert sync_env.service.get_last_received_at() < datetime(1971, 1, 1, tzinfo=UTC)

    checkpoint = datetime.now(UTC)
    sync_env.service.set_last_received_at(checkpoint)

    assert sync_env.service.get_last_received_at() == checkpoint
