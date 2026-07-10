"""Helper de proceso separado para `test_sync_transport_e2e.py`.

No es un archivo de pruebas de pytest (no empieza con `test_`, pytest no
lo recolecta). Arranca un servidor de sincronización real contra su propia
base de datos SQLite en un proceso de Python independiente — necesario
porque `core.database.session` usa un engine global por proceso, así que
dos "estaciones" con bases de datos distintas no pueden coexistir dentro
del mismo proceso de pytest. Con `--dump` no arranca ningún servidor: solo
imprime el log de sincronización de la base indicada como JSON y termina,
usado por la prueba para verificar qué quedó persistido del lado del
"servidor" después de la conversación por WebSocket.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from datetime import datetime
from enum import Enum

from pos.core.database import model_registry
from pos.core.database.session import init_engine
from pos.core.events.bus import get_event_bus
from pos.modules.products.domain.events import ProductCreatedEvent
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.modules.sync.application.sync_service import SyncService
from pos.modules.sync.domain.enums import SyncMode
from pos.modules.sync.server.runner import SyncServer


def _json_default(value: object) -> str:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--station-name", required=True)
    parser.add_argument("--port", type=int)
    parser.add_argument("--seed-event", action="store_true")
    parser.add_argument("--dump", action="store_true")
    args = parser.parse_args()

    engine = init_engine(f"sqlite:///{args.db_path}")
    model_registry.metadata.create_all(engine)

    settings = BusinessSettingsService(get_event_bus())
    sync_service = SyncService(get_event_bus(), settings)
    sync_service.set_local_station_name(args.station_name)

    if args.dump:
        entries = [dataclasses.asdict(e) for e in sync_service.list_recent()]
        print(json.dumps(entries, default=_json_default))
        return

    assert args.port is not None
    sync_service.set_mode(SyncMode.PRIMARY)
    sync_service.set_server_port(args.port)

    if args.seed_event:
        sync_service.capture_event(
            ProductCreatedEvent(
                product_id=1, sku="SKU-1", name="Producto de prueba", track_inventory=True
            )
        )

    server = SyncServer(sync_service, host="127.0.0.1")
    server.start()
    print("READY", flush=True)
    try:
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


if __name__ == "__main__":
    sys.exit(main())
