"""Modelos SQLAlchemy de catálogo: categorías, productos, recetas, combos e impuestos."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pos.core.database.base import AuditedEntity, Base, TimestampMixin
from pos.modules.products.domain.enums import ProductType, SaleUnit


class Category(Base, AuditedEntity):
    """Categoría de producto, jerárquica vía `parent_id` autorreferenciado."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Product(Base, AuditedEntity):
    """Producto del catálogo: simple, compuesto (con receta) o combo."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    product_type: Mapped[ProductType] = mapped_column(
        Enum(ProductType, native_enum=False), default=ProductType.SIMPLE, nullable=False
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(20), default="unidad", nullable=False)
    sale_unit: Mapped[SaleUnit] = mapped_column(
        Enum(SaleUnit, native_enum=False), default=SaleUnit.UNIT, server_default="unit", nullable=False
    )
    """Unidad o peso — campo obligatorio y explícito (reemplaza la
    heurística de texto que existía antes sobre `unit_of_measure`)."""
    min_weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    max_weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    """Solo tienen sentido cuando `sale_unit is SaleUnit.WEIGHT` — límites
    de peso que `ScaleWeightDialog`/`SaleService` rechazan al vender (ver
    `weight_reading.classify_reading`, `WeightReadingStatus.OUT_OF_RANGE`)."""
    weight_decimal_places: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """Si es `None`, se usa `ScaleDeviceConfig.decimal_places` de la
    báscula activa al momento de pesar — permite que un producto puntual
    (ej. algo que se vende en gramos exactos) anule la precisión general."""
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    track_inventory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    """False para productos/servicios que no descuentan stock (ej. un servicio)."""
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    """Ruta de la imagen del producto (ver `products/infrastructure/image_storage.py`),
    reutilizada por Catálogo, Vendedor y Despacho — una sola imagen por
    producto, nunca duplicada entre módulos."""

    barcodes: Mapped[list[ProductBarcode]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductBarcode.created_at"
    )
    """Códigos de barras del producto — cero, uno o varios (proveedor A,
    proveedor B, cambio de presentación...). Nunca una columna única en
    esta tabla: ver `ProductBarcode`, la fuente única de verdad para
    resolver un código escaneado a un producto (Ventas, Catálogo,
    Inventario)."""


class ProductBarcode(Base, TimestampMixin):
    """Un código de barras de un producto. Relación uno-a-muchos real (no
    una columna `barcode` en `Product`): un producto puede tener varios
    códigos, pero cada código pertenece a un único producto — `code` es
    único a nivel de toda la tabla, lo que además es el índice que hace
    `find_by_barcode` prácticamente instantáneo sin importar cuántos
    productos existan (ver `ProductRepository.find_by_barcode`)."""

    __tablename__ = "product_barcodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    """Texto exacto entregado por el lector, sin asumir ninguna simbología
    (EAN-13/EAN-8/UPC-A/UPC-E/Code128/Code39/GS1/lo que sea) — se guarda
    tal cual, sin normalizar longitud ni formato."""

    product: Mapped[Product] = relationship(back_populates="barcodes")


class RecipeItem(Base):
    """Insumo de la receta de un producto compuesto.

    `recipe_product_id` es el producto compuesto que se vende;
    `ingredient_product_id` es el producto/insumo que se descuenta de
    inventario en la cantidad indicada al vender el compuesto.
    """

    __tablename__ = "recipe_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    ingredient_product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(20), nullable=False)


class Combo(Base, TimestampMixin):
    """Combo: agrupa varios productos bajo un único producto vendible.

    `product_id` referencia el `Product` con `product_type=COMBO` que
    representa el combo en el catálogo y en las ventas.
    """

    __tablename__ = "combos"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), unique=True, nullable=False)

    items: Mapped[list[ComboItem]] = relationship(
        back_populates="combo", cascade="all, delete-orphan"
    )


class ComboItem(Base):
    """Producto incluido dentro de un combo, con la cantidad correspondiente."""

    __tablename__ = "combo_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    combo_id: Mapped[int] = mapped_column(ForeignKey("combos.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=1, nullable=False)

    combo: Mapped[Combo] = relationship(back_populates="items")


class Tax(Base, TimestampMixin):
    """Impuesto configurable (ej. IVA 19%, exento, etc.)."""

    __tablename__ = "taxes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    rate_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
