package com.astrim.pos.core.network.dto

import com.google.gson.annotations.SerializedName

/**
 * Espejo exacto de los DTOs de la API documentados en API.md §3.3/§3.4 —
 * mismos nombres de campo que el backend, sin recalcular ni inventar nada
 * acá (esta app no tiene lógica de negocio propia). `unitPrice` queda como
 * `String` a propósito: el backend serializa todo campo monetario como
 * string para evitar redondeo de punto flotante (ver API.md §1) — el
 * cliente lo parsea a `BigDecimal` recién al mostrarlo, nunca a
 * `Float`/`Double`.
 */
data class CategoryDto(
    val id: Int,
    val name: String,
    @SerializedName("is_active") val isActive: Boolean,
)

/**
 * Usado tanto para `GET /products` como para `GET /products/by-barcode/{code}`
 * — este último responde `ProductDetail` (un superconjunto de campos), pero
 * Gson ignora los campos extra que no declara esta clase (`description`,
 * receta/combo, etc.), que esta fase del catálogo no necesita mostrar.
 */
data class ProductSummaryDto(
    val id: Int,
    val sku: String,
    val name: String,
    @SerializedName("category_id") val categoryId: Int?,
    @SerializedName("category_name") val categoryName: String?,
    @SerializedName("product_type") val productType: String,
    @SerializedName("unit_price") val unitPrice: String,
    @SerializedName("unit_of_measure") val unitOfMeasure: String,
    @SerializedName("sale_unit") val saleUnit: String,
    @SerializedName("is_active") val isActive: Boolean,
    @SerializedName("track_inventory") val trackInventory: Boolean,
    @SerializedName("image_path") val imagePath: String?,
    val barcodes: List<String>,
)
