"""Carrito de venta en construcción — vive en memoria del proceso del
servidor, nunca en la base de datos.

El escritorio mantiene su carrito en memoria del proceso Qt
(`SaleViewModel._items`, ver `sales/presentation/sale_view_model.py`) hasta
completar la venta (`SalesService.complete_sale`, que sí persiste) o
descartarlo sin guardar nada a medio camino. La Fase 3 de la API
explícitamente no completa ventas (eso es cobro, Fase 4) — el equivalente
correcto para un cliente remoto es el mismo tipo de estado efímero, solo
que vive acá en vez de en un proceso Qt. No es una tabla nueva ni un
concepto de dominio nuevo: es la misma idea de "carrito en memoria" que ya
existe, en el lugar que le corresponde para un cliente sin proceso propio.

Se reinicia cada vez que arranca el servidor — igual que cerrar la app de
escritorio sin completar una venta pierde ese carrito.

Fase 4 agrega `completed_sale_id`: una vez que `POST .../complete` llama a
`SalesService.complete_sale` con éxito, el carrito queda marcado con el
`id` de la venta ya persistida — y una segunda solicitud de finalización
sobre el MISMO carrito (reintento de red, doble tap del cajero) devuelve
esa misma venta sin volver a llamar `complete_sale` (ver
`completion_lock`), que es lo que evita ventas duplicadas."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from pos.modules.sales.application.dto import SaleItemInput


@dataclass
class SaleDraft:
    id: str
    owner_user_id: int
    items: list[SaleItemInput] = field(default_factory=list)
    completed_sale_id: int | None = None


class SaleDraftStore:
    """`_lock` protege el diccionario de carritos y las lecturas/escrituras
    de cada uno — la contención esperada es mínima (cada carrito lo opera
    secuencialmente un único usuario desde un único dispositivo), así que
    un lock simple es suficiente para eso (ver DEVELOPMENT_RULES.md, SOLID
    pragmático).

    `completion_lock` es aparte: un lock *por carrito*, tomado durante todo
    `POST .../complete` (que hace trabajo real de base de datos, más lento
    que una mutación de lista en memoria) — así una segunda solicitud para
    ESE MISMO carrito espera a que la primera termine en vez de arrancar
    otra `complete_sale` en paralelo, sin bloquear las solicitudes de
    otros carritos mientras tanto."""

    def __init__(self) -> None:
        self._drafts: dict[str, SaleDraft] = {}
        self._completion_locks: dict[str, threading.Lock] = {}
        self._lock = threading.Lock()

    def create(self, *, owner_user_id: int) -> SaleDraft:
        with self._lock:
            draft = SaleDraft(id=str(uuid.uuid4()), owner_user_id=owner_user_id)
            self._drafts[draft.id] = draft
            self._completion_locks[draft.id] = threading.Lock()
            return draft

    def _find(self, draft_id: str, *, owner_user_id: int) -> SaleDraft | None:
        draft = self._drafts.get(draft_id)
        if draft is None or draft.owner_user_id != owner_user_id:
            return None
        return draft

    def get(self, draft_id: str, *, owner_user_id: int) -> SaleDraft | None:
        """Copia superficial de solo lectura (nunca el objeto interno
        mutable) — `None` si el carrito no existe o no le pertenece a
        `owner_user_id`, mismo tratamiento para ambos casos (ver
        `sales_router.py`), para no filtrar si un id ajeno existe."""
        with self._lock:
            draft = self._find(draft_id, owner_user_id=owner_user_id)
            if draft is None:
                return None
            return SaleDraft(
                id=draft.id,
                owner_user_id=draft.owner_user_id,
                items=list(draft.items),
                completed_sale_id=draft.completed_sale_id,
            )

    def get_items(self, draft_id: str, *, owner_user_id: int) -> list[SaleItemInput] | None:
        draft = self.get(draft_id, owner_user_id=owner_user_id)
        return draft.items if draft is not None else None

    def set_items(
        self, draft_id: str, *, owner_user_id: int, items: list[SaleItemInput]
    ) -> list[SaleItemInput] | None:
        """`None` también si el carrito ya fue finalizado — una venta ya
        cobrada no se puede seguir editando localmente, aunque el registro
        persistido no se vea afectado de todas formas (ver
        `sales_router.py`, que valida esto explícito para dar un mensaje
        claro antes de intentar escribir)."""
        with self._lock:
            draft = self._find(draft_id, owner_user_id=owner_user_id)
            if draft is None or draft.completed_sale_id is not None:
                return None
            draft.items = items
            return list(draft.items)

    @contextmanager
    def completion_lock(
        self, draft_id: str, *, owner_user_id: int
    ) -> Iterator[SaleDraft | None]:
        """Sección crítica de "completar este carrito" — ver docstring de
        la clase. Cede `None` si el carrito no existe/no es del dueño;
        si existe, toma su lock individual (bloqueando otra finalización
        concurrente del mismo carrito, nunca la de otro) y cede el estado
        más reciente ya con el lock tomado."""
        with self._lock:
            exists = self._find(draft_id, owner_user_id=owner_user_id) is not None
            lock = self._completion_locks.get(draft_id)
        if not exists or lock is None:
            yield None
            return
        with lock:
            yield self.get(draft_id, owner_user_id=owner_user_id)

    def mark_completed(self, draft_id: str, *, owner_user_id: int, sale_id: int) -> None:
        with self._lock:
            draft = self._find(draft_id, owner_user_id=owner_user_id)
            if draft is not None:
                draft.completed_sale_id = sale_id
