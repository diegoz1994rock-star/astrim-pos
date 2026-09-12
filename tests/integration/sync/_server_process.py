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
from pos.core.security.session import SessionManager
from pos.modules.auth.application.authentication_service import AuthenticationService
from pos.modules.bre_b_payments.application.breb_payment_service import BreBPaymentService
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.kitchen.application.kitchen_service import KitchenService
from pos.modules.nequi_payments.application.nequi_payment_service import NequiPaymentService
from pos.modules.products.application.category_service import CategoryManagementService
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.products.domain.events import ProductCreatedEvent
from pos.modules.qr_payments.application.qr_payment_service import QrPaymentService
from pos.modules.restaurant.application.restaurant_service import RestaurantService
from pos.modules.sales.application.sale_service import SalesService
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.modules.sync.application.sync_service import SyncService
from pos.modules.sync.domain.enums import SyncMode
from pos.modules.sync.server.runner import SyncServer
from pos.modules.users.application.user_management_service import UserManagementService


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

    auth_service = AuthenticationService(SessionManager(), get_event_bus())
    product_service = ProductManagementService(get_event_bus())
    category_service = CategoryManagementService()
    inventory_service = InventoryService(get_event_bus())
    cash_register_service = CashRegisterService(get_event_bus())
    customer_service = CustomerManagementService()
    sales_service = SalesService(
        get_event_bus(), inventory_service, cash_register_service, customer_service
    )
    restaurant_service = RestaurantService(get_event_bus())
    user_service = UserManagementService(get_event_bus())
    kitchen_service = KitchenService(
        user_service, restaurant_service, sales_service, cash_register_service
    )
    qr_payment_service = QrPaymentService()
    nequi_payment_service = NequiPaymentService()
    breb_payment_service = BreBPaymentService()
    server = SyncServer(
        sync_service,
        auth_service=auth_service,
        product_service=product_service,
        category_service=category_service,
        sales_service=sales_service,
        inventory_service=inventory_service,
        cash_register_service=cash_register_service,
        kitchen_service=kitchen_service,
        customer_service=customer_service,
        user_service=user_service,
        restaurant_service=restaurant_service,
        qr_payment_service=qr_payment_service,
        nequi_payment_service=nequi_payment_service,
        breb_payment_service=breb_payment_service,
        host="127.0.0.1",
    )
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
