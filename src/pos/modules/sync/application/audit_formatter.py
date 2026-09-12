"""Traduce entradas de `sync_log` (ver `SyncService.list_recent`) a una
línea legible para humanos, para la pantalla de Auditoría.

Reutiliza el outbox de Sincronización ya existente (todo evento de dominio
publicado en el proceso ya queda ahí con su payload completo, ver
`SyncService.capture_event`) — no agrega ninguna tabla ni servicio nuevo,
solo sabe traducir el `event_type`/`payload_json` ya guardados. Los tipos
de evento sin plantilla específica se muestran con su nombre crudo, para
que la pantalla nunca oculte información aunque falte una plantilla."""

from __future__ import annotations

import json
from collections.abc import Callable
from decimal import Decimal, InvalidOperation

from pos.modules.sync.application.dto import SyncLogEntryDTO
from pos.shared_ui.formatting import format_currency


def _money(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if value is None:
        return "?"
    try:
        formatted = format_currency(Decimal(str(value)))
    except InvalidOperation:
        return str(value)
    if formatted.startswith("-"):
        return f"-${formatted[1:]}"
    return f"${formatted}"


def _sale_completed(payload: dict[str, object]) -> str:
    text = f"Venta #{payload.get('sale_id', '?')} completada — {_money(payload, 'total')}"
    user_id = payload.get("created_by_user_id")
    if user_id:
        text += f" (usuario #{user_id})"
    return text


def _sale_voided(payload: dict[str, object]) -> str:
    text = f"Venta #{payload.get('sale_id', '?')} anulada"
    reason = payload.get("reason")
    if reason:
        text += f" — motivo: {reason}"
    user_id = payload.get("voided_by_user_id")
    if user_id:
        text += f" (usuario #{user_id})"
    return text


def _cash_session_opened(payload: dict[str, object]) -> str:
    return f"Turno de caja #{payload.get('cash_session_id', '?')} abierto"


def _cash_session_closed(payload: dict[str, object]) -> str:
    return (
        f"Turno de caja #{payload.get('cash_session_id', '?')} cerrado — "
        f"diferencia {_money(payload, 'difference')}"
    )


def _stock_level_changed(payload: dict[str, object]) -> str:
    quantity = payload.get("new_quantity", "?")
    warning = " (bajo mínimo)" if payload.get("is_below_minimum") else ""
    return f"Stock del producto #{payload.get('product_id', '?')} actualizado a {quantity}{warning}"


def _user_status_changed(payload: dict[str, object]) -> str:
    state = "activado" if payload.get("is_active") else "desactivado"
    return f"Usuario #{payload.get('user_id', '?')} {state}"


def _product_status_changed(payload: dict[str, object]) -> str:
    state = "activado" if payload.get("is_active") else "desactivado"
    return f"Producto #{payload.get('product_id', '?')} {state}"


_FORMATTERS: dict[str, Callable[[dict[str, object]], str]] = {
    "SaleCompletedEvent": _sale_completed,
    "SaleVoidedEvent": _sale_voided,
    "CashSessionOpenedEvent": _cash_session_opened,
    "CashSessionClosedEvent": _cash_session_closed,
    "StockLevelChangedEvent": _stock_level_changed,
    "UserStatusChangedEvent": _user_status_changed,
    "ProductStatusChangedEvent": _product_status_changed,
}


def format_audit_entry(entry: SyncLogEntryDTO) -> str:
    formatter = _FORMATTERS.get(entry.event_type)
    if formatter is None:
        return entry.event_type
    try:
        payload = json.loads(entry.payload_json)
    except (ValueError, TypeError):
        return entry.event_type
    try:
        return formatter(payload)
    except (KeyError, TypeError, ValueError):
        return entry.event_type
