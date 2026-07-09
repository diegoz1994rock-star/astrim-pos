"""Modelos SQLAlchemy de configuración del negocio: parámetros, impresoras y temas.

Todo lo listado en PROJECT_SPEC.md bajo "CONFIGURACIÓN" (nombre, logo,
dirección, moneda, impuestos, etc.) se guarda en `business_settings` como
pares clave/valor tipados, para que agregar un nuevo parámetro configurable
no requiera una migración de esquema.
"""

from __future__ import annotations

import enum

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import Base, TimestampMixin


class SettingValueType(enum.Enum):
    """Tipo de dato del valor almacenado en `BusinessSetting.value`."""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    JSON = "json"


class BusinessSetting(Base, TimestampMixin):
    """Parámetro de configuración del negocio (clave/valor tipado)."""

    __tablename__ = "business_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_type: Mapped[SettingValueType] = mapped_column(
        Enum(SettingValueType, native_enum=False), default=SettingValueType.STRING, nullable=False
    )


class PrinterConnectionType(enum.Enum):
    """Tipo de conexión de una impresora configurada."""

    USB = "usb"
    NETWORK = "network"
    BLUETOOTH = "bluetooth"


class PrinterConfig(Base, TimestampMixin):
    """Impresora configurada (recibos, comandas de cocina, facturas)."""

    __tablename__ = "printers_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    connection_type: Mapped[PrinterConnectionType] = mapped_column(
        Enum(PrinterConnectionType, native_enum=False), nullable=False
    )
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ThemeMode(enum.Enum):
    """Modo de tema visual (PROJECT_SPEC.md, "INTERFAZ")."""

    LIGHT = "light"
    DARK = "dark"
    CUSTOM = "custom"


class ThemeConfig(Base, TimestampMixin):
    """Tema visual configurado: colores, logo y modo claro/oscuro/personalizado."""

    __tablename__ = "themes_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    mode: Mapped[ThemeMode] = mapped_column(Enum(ThemeMode, native_enum=False), nullable=False)
    primary_color: Mapped[str] = mapped_column(String(20), nullable=False)
    secondary_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    logo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
