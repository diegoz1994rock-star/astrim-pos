"""Registro central de todos los modelos ORM del sistema.

Importar este módulo (una sola vez, al arrancar la app o desde
`migrations/env.py`) registra todas las tablas sobre `Base.metadata`, sin
que ningún módulo de negocio necesite importar a otro directamente
(ver ARCHITECTURE.md §12b). Si se agrega un módulo nuevo con modelos
propios, su import se agrega aquí.
"""

from __future__ import annotations

from pos.core.database.base import Base

# ruff: noqa: F401 -- los imports registran las tablas por efecto secundario.
from pos.modules.audit.infrastructure import models as audit_models
from pos.modules.auth.infrastructure import models as auth_models
from pos.modules.backups.infrastructure import models as backups_models
from pos.modules.barcode_scanners.infrastructure import models as barcode_scanners_models
from pos.modules.billing.infrastructure import models as billing_models
from pos.modules.bre_b_payments.infrastructure import models as bre_b_payments_models
from pos.modules.cash_drawers.infrastructure import models as cash_drawers_models
from pos.modules.cash_register.infrastructure import models as cash_register_models
from pos.modules.customers.infrastructure import models as customers_models
from pos.modules.inventory.infrastructure import models as inventory_models
from pos.modules.invoice_settings.infrastructure import models as invoice_settings_models
from pos.modules.job_positions.infrastructure import models as job_positions_models
from pos.modules.licensing.infrastructure import models as licensing_models
from pos.modules.nequi_payments.infrastructure import models as nequi_payments_models
from pos.modules.notifications.infrastructure import models as notifications_models
from pos.modules.printers.infrastructure import models as printers_models
from pos.modules.products.infrastructure import models as products_models
from pos.modules.purchasing.infrastructure import models as purchasing_models
from pos.modules.qr_payments.infrastructure import models as qr_payments_models
from pos.modules.restaurant.infrastructure import models as restaurant_models
from pos.modules.sales.infrastructure import models as sales_models
from pos.modules.scales.infrastructure import models as scales_models
from pos.modules.settings.infrastructure import models as settings_models
from pos.modules.suppliers.infrastructure import models as suppliers_models
from pos.modules.sync.infrastructure import models as sync_models
from pos.modules.users.infrastructure import models as users_models

metadata = Base.metadata
