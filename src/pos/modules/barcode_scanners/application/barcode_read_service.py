"""Módulo centralizado de código de barras: normaliza, valida, busca el
producto, evita dobles lecturas (rebote del lector), registra cada evento
y expone diagnóstico agregado. Ventas, "Probar lector" y el formulario de
producto pasan por este único servicio — ninguno vuelve a implementar esta
lógica por su cuenta.

Deliberadamente no sabe nada de Qt/PySide ni de dispositivos registrados
(`BarcodeScanner`): funciona igual con cero lectores registrados, uno o
veinte — cualquier texto que llegue seguido de Enter es una lectura
válida a resolver."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pos.core.database.session import session_scope
from pos.modules.barcode_scanners.application.dto import (
    BarcodeDiagnosticsDTO,
    BarcodeReadLogEntryDTO,
    BarcodeReadResultDTO,
    BarcodeSettingsDTO,
)
from pos.modules.barcode_scanners.domain.enums import BarcodeReadSource
from pos.modules.barcode_scanners.domain.scan_parsing import normalize_scan
from pos.modules.barcode_scanners.domain.symbology import detect_symbology
from pos.modules.barcode_scanners.infrastructure.barcode_read_repository import (
    BarcodeReadRepository,
)
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.modules.settings.infrastructure.models import SettingValueType

_KEY_READER_ENABLED = "barcode_reader_enabled"
_KEY_AUTO_ENTER_ENABLED = "barcode_auto_enter_enabled"
_KEY_DEBOUNCE_MS = "barcode_duplicate_debounce_ms"
_KEY_SOUND_ON_SUCCESS = "barcode_sound_on_success"
_KEY_SOUND_ON_NOT_FOUND = "barcode_sound_on_not_found"
_KEY_SHOW_VISUAL_NOTIFICATION = "barcode_show_visual_notification"

_DEFAULT_DEBOUNCE_MS = 150
_RECENT_ACTIVITY_WINDOW = timedelta(minutes=5)
_DIAGNOSTICS_SAMPLE_SIZE = 500
_MAX_CODE_LENGTH = 64
"""Igual al límite de `product_barcodes.code`/`barcode_reads.code`
(`String(64)`) — duplicada a propósito (ver el mismo criterio documentado
en `barcode_scanners/domain/enums.py` para `ConnectionType`) para no
acoplar este servicio al módulo de productos por una sola constante.
SQLite no aplica el límite de un `VARCHAR(N)` por sí solo, así que sin
este control una lectura de basura muy larga (lector mal configurado)
se registraría sin límite en el historial."""
_DEBOUNCE_ENTRY_MAX_AGE = timedelta(seconds=10)
"""Cuánto se conserva cada código en el diccionario de rebote en memoria
antes de descartarse — muy por encima de cualquier valor razonable de
`duplicate_debounce_ms` (el límite configurable en la UI es 5000 ms), así
que nunca se pierde una lectura que siga dentro de su ventana real. Sin
esto, `_last_read_at` crecería sin límite en una jornada larga con miles de
códigos distintos escaneados (fuga de memoria)."""


class BarcodeReadService:
    def __init__(
        self, settings: BusinessSettingsService, product_service: ProductManagementService
    ) -> None:
        self._settings = settings
        self._product_service = product_service
        self._last_read_at: dict[str, datetime] = {}

    # -- Configuración global ---------------------------------------------

    def get_settings(self) -> BarcodeSettingsDTO:
        return BarcodeSettingsDTO(
            reader_enabled=self._settings.get_bool(_KEY_READER_ENABLED, True),
            auto_enter_enabled=self._settings.get_bool(_KEY_AUTO_ENTER_ENABLED, True),
            duplicate_debounce_ms=self._get_debounce_ms(),
            sound_on_success=self._settings.get_bool(_KEY_SOUND_ON_SUCCESS, True),
            sound_on_not_found=self._settings.get_bool(_KEY_SOUND_ON_NOT_FOUND, True),
            show_visual_notification=self._settings.get_bool(
                _KEY_SHOW_VISUAL_NOTIFICATION, True
            ),
        )

    def _get_debounce_ms(self) -> int:
        """`BusinessSettingsService.get_int` no tolera un valor corrupto
        (`int(raw)` sin capturar `ValueError`) — acá sí, porque un valor
        dañado en esta clave puntual (edición manual de la base, migración
        futura, etc.) no debe tumbar cada lectura de código de barras del
        negocio; cae al valor por defecto en vez de propagar la excepción."""
        try:
            return self._settings.get_int(_KEY_DEBOUNCE_MS, _DEFAULT_DEBOUNCE_MS)
        except (TypeError, ValueError):
            return _DEFAULT_DEBOUNCE_MS

    def save_settings(self, settings: BarcodeSettingsDTO) -> None:
        self._settings.set_value(
            _KEY_READER_ENABLED,
            "true" if settings.reader_enabled else "false",
            SettingValueType.BOOLEAN,
        )
        self._settings.set_value(
            _KEY_AUTO_ENTER_ENABLED,
            "true" if settings.auto_enter_enabled else "false",
            SettingValueType.BOOLEAN,
        )
        self._settings.set_value(
            _KEY_DEBOUNCE_MS, str(settings.duplicate_debounce_ms), SettingValueType.NUMBER
        )
        self._settings.set_value(
            _KEY_SOUND_ON_SUCCESS,
            "true" if settings.sound_on_success else "false",
            SettingValueType.BOOLEAN,
        )
        self._settings.set_value(
            _KEY_SOUND_ON_NOT_FOUND,
            "true" if settings.sound_on_not_found else "false",
            SettingValueType.BOOLEAN,
        )
        self._settings.set_value(
            _KEY_SHOW_VISUAL_NOTIFICATION,
            "true" if settings.show_visual_notification else "false",
            SettingValueType.BOOLEAN,
        )

    def _prune_stale_debounce_entries(self, current_time: datetime) -> None:
        stale_codes = [
            code
            for code, seen_at in self._last_read_at.items()
            if current_time - seen_at > _DEBOUNCE_ENTRY_MAX_AGE
        ]
        for code in stale_codes:
            del self._last_read_at[code]

    # -- Lectura centralizada -----------------------------------------------

    def resolve_scan(
        self,
        raw_code: str,
        *,
        source: BarcodeReadSource,
        user_id: int | None = None,
        username: str | None = None,
        cash_register_id: int | None = None,
        cash_register_name: str | None = None,
        now: datetime | None = None,
    ) -> BarcodeReadResultDTO:
        settings = self.get_settings()
        empty_symbology = detect_symbology("")

        if not settings.reader_enabled:
            return BarcodeReadResultDTO(
                code=raw_code,
                symbology=empty_symbology,
                found=False,
                product=None,
                ignored=True,
                reason="El lector está desactivado en Configuración.",
            )

        code = normalize_scan(raw_code)
        if not code:
            return BarcodeReadResultDTO(
                code=code, symbology=empty_symbology, found=False, product=None,
                ignored=True, reason="Código vacío.",
            )
        if len(code) > _MAX_CODE_LENGTH:
            return BarcodeReadResultDTO(
                code=code, symbology=empty_symbology, found=False, product=None,
                ignored=True,
                reason=f"Código demasiado largo (máximo {_MAX_CODE_LENGTH} caracteres).",
            )

        current_time = now if now is not None else datetime.now(UTC)
        self._prune_stale_debounce_entries(current_time)
        last_seen = self._last_read_at.get(code)
        if last_seen is not None:
            elapsed_ms = (current_time - last_seen) / timedelta(milliseconds=1)
            if elapsed_ms < settings.duplicate_debounce_ms:
                return BarcodeReadResultDTO(
                    code=code, symbology=detect_symbology(code), found=False, product=None,
                    ignored=True, reason="Lectura duplicada (rebote del lector).",
                )
        self._last_read_at[code] = current_time

        symbology = detect_symbology(code)
        product = self._product_service.find_product_by_barcode(code)

        with session_scope() as session:
            BarcodeReadRepository(session).insert_read(
                code=code,
                symbology=symbology,
                found=product is not None,
                product_id=product.id if product is not None else None,
                source=source,
                user_id=user_id,
                username=username,
                cash_register_id=cash_register_id,
                cash_register_name=cash_register_name,
                occurred_at=current_time,
            )

        return BarcodeReadResultDTO(
            code=code, symbology=symbology, found=product is not None, product=product,
            ignored=False, reason=None,
        )

    # -- Diagnóstico y log ---------------------------------------------------

    def get_diagnostics(self) -> BarcodeDiagnosticsDTO:
        with session_scope() as session:
            repo = BarcodeReadRepository(session)
            last = repo.most_recent()
            total = repo.count_total()
            errors = repo.count_errors()
            timestamps = repo.recent_timestamps(_DIAGNOSTICS_SAMPLE_SIZE)
            has_recent_activity = repo.count_since(datetime.now(UTC) - _RECENT_ACTIVITY_WINDOW) > 0

        average_interval_ms: float | None = None
        if len(timestamps) >= 2:
            deltas = [
                (timestamps[index] - timestamps[index + 1]) / timedelta(milliseconds=1)
                for index in range(len(timestamps) - 1)
            ]
            average_interval_ms = sum(deltas) / len(deltas)

        return BarcodeDiagnosticsDTO(
            last_code=last.code if last is not None else None,
            last_read_at=last.occurred_at if last is not None else None,
            total_reads=total,
            error_count=errors,
            average_interval_ms=average_interval_ms,
            has_recent_activity=has_recent_activity,
        )

    def list_recent_reads(self, limit: int = 200) -> list[BarcodeReadLogEntryDTO]:
        with session_scope() as session:
            entries = BarcodeReadRepository(session).list_recent(limit)
            product_ids = [entry.product_id for entry in entries if entry.product_id is not None]

        names = self._product_service.get_product_names(product_ids)
        return [
            BarcodeReadLogEntryDTO(
                id=entry.id,
                code=entry.code,
                symbology=entry.symbology,
                found=entry.found,
                product_id=entry.product_id,
                product_name=names.get(entry.product_id) if entry.product_id is not None else None,
                source=entry.source,
                username=entry.username,
                cash_register_name=entry.cash_register_name,
                occurred_at=entry.occurred_at,
            )
            for entry in entries
        ]
