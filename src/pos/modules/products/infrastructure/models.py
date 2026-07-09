"""Modelos SQLAlchemy de catálogo: categorías, productos, recetas, combos e impuestos."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pos.core.database.base import AuditedEntity, Base, TimestampMixin
from pos.modules.products.domain.enums import ProductType


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
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    track_inventory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    """False para productos/servicios que no descuentan stock (ej. un servicio)."""

    taxes: Mapped[list[ProductTax]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


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


class ProductTax(Base):
    """Asociación producto ↔ impuesto aplicable."""

    __tablename__ = "product_taxes"
    __table_args__ = (UniqueConstraint("product_id", "tax_id", name="uq_product_tax"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    tax_id: Mapped[int] = mapped_column(ForeignKey("taxes.id"), nullable=False)

    product: Mapped[Product] = relationship(back_populates="taxes")
