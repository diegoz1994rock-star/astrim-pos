"""Acceso a datos de configuración de básculas y su historial de eventos."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from pos.modules.scales.domain.enums import (
    ConnectionStatus,
    ConnectionType,
    ScaleDeviceEventType,
    UnitOfMeasure,
    WeightReadingStatus,
)
from pos.modules.scales.infrastructure.models import (
    ScaleDeviceConfig,
    ScaleDeviceEvent,
    ScaleWeightRead,
)


class ScaleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[ScaleDeviceConfig]:
        return list(
            self._session.scalars(select(ScaleDeviceConfig).order_by(ScaleDeviceConfig.name))
        )

    def get(self, device_id: int) -> ScaleDeviceConfig | None:
        return self._session.get(ScaleDeviceConfig, device_id)

    def get_by_name(self, name: str) -> ScaleDeviceConfig | None:
        return self._session.scalar(
            select(ScaleDeviceConfig).where(ScaleDeviceConfig.name == name)
        )

    def get_default(self) -> ScaleDeviceConfig | None:
        return self._session.scalar(
            select(ScaleDeviceConfig).where(
                ScaleDeviceConfig.is_default.is_(True), ScaleDeviceConfig.is_active.is_(True)
            )
        )

    def create(
        self,
        *,
        name: str,
        kind: str,
        brand: str | None,
        model: str | None,
        serial_number: str | None,
        description: str | None,
        location: str | None,
        cash_register_id: int | None,
        station_label: str | None,
        assigned_user_id: int | None,
        connection_type: ConnectionType,
        port: str | None,
        baud_rate: int | None,
        data_bits: int | None,
        stop_bits: int | None,
        parity: str | None,
        ip_address: str | None,
        ip_port: int | None,
        bluetooth_address: str | None,
        unit_of_measure: UnitOfMeasure,
        decimal_places: int,
        timeout_seconds: int,
        read_frequency_seconds: int,
        auto_read: bool,
        stability_required: bool,
        min_stable_seconds: Decimal,
        auto_reconnect: bool,
    ) -> ScaleDeviceConfig:
        device = ScaleDeviceConfig(
            name=name,
            kind=kind,
            brand=brand,
            model=model,
            serial_number=serial_number,
            description=description,
            location=location,
            cash_register_id=cash_register_id,
            station_label=station_label,
            assigned_user_id=assigned_user_id,
            connection_type=connection_type,
            port=port,
            baud_rate=baud_rate,
            data_bits=data_bits,
            stop_bits=stop_bits,
            parity=parity,
            ip_address=ip_address,
            ip_port=ip_port,
            bluetooth_address=bluetooth_address,
            unit_of_measure=unit_of_measure,
            decimal_places=decimal_places,
            timeout_seconds=timeout_seconds,
            read_frequency_seconds=read_frequency_seconds,
            auto_read=auto_read,
            stability_required=stability_required,
            min_stable_seconds=min_stable_seconds,
            auto_reconnect=auto_reconnect,
            is_active=True,
            is_default=False,
        )
        self._session.add(device)
        self._session.flush()
        return device

    def update(
        self,
        device: ScaleDeviceConfig,
        *,
        name: str,
        kind: str,
        brand: str | None,
        model: str | None,
        serial_number: str | None,
        description: str | None,
        location: str | None,
        cash_register_id: int | None,
        station_label: str | None,
        assigned_user_id: int | None,
        connection_type: ConnectionType,
        port: str | None,
        baud_rate: int | None,
        data_bits: int | None,
        stop_bits: int | None,
        parity: str | None,
        ip_address: str | None,
        ip_port: int | None,
        bluetooth_address: str | None,
        unit_of_measure: UnitOfMeasure,
        decimal_places: int,
        timeout_seconds: int,
        read_frequency_seconds: int,
        auto_read: bool,
        stability_required: bool,
        min_stable_seconds: Decimal,
        auto_reconnect: bool,
    ) -> None:
        device.name = name
        device.kind = kind
        device.brand = brand
        device.model = model
        device.serial_number = serial_number
        device.description = description
        device.location = location
        device.cash_register_id = cash_register_id
        device.station_label = station_label
        device.assigned_user_id = assigned_user_id
        device.connection_type = connection_type
        device.port = port
        device.baud_rate = baud_rate
        device.data_bits = data_bits
        device.stop_bits = stop_bits
        device.parity = parity
        device.ip_address = ip_address
        device.ip_port = ip_port
        device.bluetooth_address = bluetooth_address
        device.unit_of_measure = unit_of_measure
        device.decimal_places = decimal_places
        device.timeout_seconds = timeout_seconds
        device.read_frequency_seconds = read_frequency_seconds
        device.auto_read = auto_read
        device.stability_required = stability_required
        device.min_stable_seconds = min_stable_seconds
        device.auto_reconnect = auto_reconnect
        self._session.flush()

    def set_active(self, device: ScaleDeviceConfig, is_active: bool) -> None:
        device.is_active = is_active
        if not is_active and device.is_default:
            device.is_default = False

    def clear_default_flag_for_all(self) -> None:
        self._session.execute(update(ScaleDeviceConfig).values(is_default=False))

    def set_default(self, device: ScaleDeviceConfig) -> None:
        device.is_default = True

    def set_connection_status(
        self, device: ScaleDeviceConfig, status: ConnectionStatus, *, occurred_at: datetime
    ) -> None:
        device.connection_status = status
        if status is ConnectionStatus.CONNECTED:
            device.last_successful_communication_at = occurred_at

    def reset_all_connection_statuses(self) -> None:
        self._session.execute(
            update(ScaleDeviceConfig).values(connection_status=ConnectionStatus.DISCONNECTED)
        )

    def set_current_tare(self, device: ScaleDeviceConfig, tare: Decimal) -> None:
        device.current_tare = tare

    def set_simulator_target_weight(self, device: ScaleDeviceConfig, weight: Decimal) -> None:
        device.simulator_target_weight = weight

    def delete(self, device: ScaleDeviceConfig) -> None:
        self._session.delete(device)


class ScaleDeviceEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_device(self, scale_device_id: int, limit: int = 50) -> list[ScaleDeviceEvent]:
        return list(
            self._session.scalars(
                select(ScaleDeviceEvent)
                .where(ScaleDeviceEvent.scale_device_id == scale_device_id)
                .order_by(ScaleDeviceEvent.occurred_at.desc())
                .limit(limit)
            )
        )

    def create(
        self,
        *,
        scale_device_id: int,
        event_type: ScaleDeviceEventType,
        message: str | None,
        occurred_at: datetime,
    ) -> ScaleDeviceEvent:
        event = ScaleDeviceEvent(
            scale_device_id=scale_device_id,
            event_type=event_type,
            message=message,
            occurred_at=occurred_at,
        )
        self._session.add(event)
        self._session.flush()
        return event


class ScaleWeightReadRepository:
    """Acceso a datos del registro centralizado de pesadas
    (`scale_weight_reads`) — independiente del inventario de dispositivos,
    mismo rol que `BarcodeReadRepository` en barcode_scanners."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def insert_read(
        self,
        *,
        scale_device_id: int | None,
        product_id: int | None,
        user_id: int | None,
        username: str | None,
        cash_register_id: int | None,
        cash_register_name: str | None,
        gross_weight: Decimal | None,
        net_weight: Decimal | None,
        tare: Decimal,
        unit: UnitOfMeasure,
        status: WeightReadingStatus,
        is_stable: bool,
        duration_ms: int | None,
        error_message: str | None,
        reconnected: bool,
        occurred_at: datetime,
    ) -> ScaleWeightRead:
        entry = ScaleWeightRead(
            scale_device_id=scale_device_id,
            product_id=product_id,
            user_id=user_id,
            username=username,
            cash_register_id=cash_register_id,
            cash_register_name=cash_register_name,
            gross_weight=gross_weight,
            net_weight=net_weight,
            tare=tare,
            unit=unit,
            status=status,
            is_stable=is_stable,
            duration_ms=duration_ms,
            error_message=error_message,
            reconnected=reconnected,
            occurred_at=occurred_at,
        )
        self._session.add(entry)
        self._session.flush()
        return entry

    def list_recent(
        self, scale_device_id: int | None = None, limit: int = 200
    ) -> list[ScaleWeightRead]:
        stmt = select(ScaleWeightRead).order_by(ScaleWeightRead.occurred_at.desc()).limit(limit)
        if scale_device_id is not None:
            stmt = stmt.where(ScaleWeightRead.scale_device_id == scale_device_id)
        return list(self._session.scalars(stmt))

    def count_total(self, scale_device_id: int | None = None) -> int:
        stmt = select(func.count(ScaleWeightRead.id))
        if scale_device_id is not None:
            stmt = stmt.where(ScaleWeightRead.scale_device_id == scale_device_id)
        return self._session.scalar(stmt) or 0

    def count_errors(self, scale_device_id: int | None = None) -> int:
        stmt = select(func.count(ScaleWeightRead.id)).where(
            ScaleWeightRead.status.in_(
                (WeightReadingStatus.INVALID, WeightReadingStatus.OUT_OF_RANGE)
            )
        )
        if scale_device_id is not None:
            stmt = stmt.where(ScaleWeightRead.scale_device_id == scale_device_id)
        return self._session.scalar(stmt) or 0

    def count_reconnections(self, scale_device_id: int | None = None) -> int:
        stmt = select(func.count(ScaleWeightRead.id)).where(ScaleWeightRead.reconnected.is_(True))
        if scale_device_id is not None:
            stmt = stmt.where(ScaleWeightRead.scale_device_id == scale_device_id)
        return self._session.scalar(stmt) or 0

    def most_recent(self, scale_device_id: int | None = None) -> ScaleWeightRead | None:
        stmt = select(ScaleWeightRead).order_by(ScaleWeightRead.occurred_at.desc()).limit(1)
        if scale_device_id is not None:
            stmt = stmt.where(ScaleWeightRead.scale_device_id == scale_device_id)
        return self._session.scalar(stmt)

    def recent_durations_ms(
        self, scale_device_id: int | None = None, limit: int = 500
    ) -> list[int]:
        stmt = (
            select(ScaleWeightRead.duration_ms)
            .where(ScaleWeightRead.duration_ms.is_not(None))
            .order_by(ScaleWeightRead.occurred_at.desc())
            .limit(limit)
        )
        if scale_device_id is not None:
            stmt = stmt.where(ScaleWeightRead.scale_device_id == scale_device_id)
        return [value for value in self._session.scalars(stmt) if value is not None]
