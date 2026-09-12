package com.astrim.pos.core.network.dto

import com.google.gson.annotations.SerializedName

/**
 * Espejo exacto de los DTOs de la API documentados en API.md §3.5/§3.6 —
 * mismos nombres de campo que `sync/server/api/sales_schemas.py`. Cantidades
 * y montos van como `String` (nunca `Float`/`Double`) tanto al enviar como
 * al recibir: el backend serializa/parsea todo `Decimal` como string (ver
 * API.md §1) para evitar el redondeo de punto flotante en dinero.
 */
data class AddSaleItemRequest(
    @SerializedName("product_id") val productId: Int,
    val quantity: String,
    val note: String? = null,
)

data class UpdateSaleItemRequest(
    val quantity: String,
    val note: String? = null,
)

data class SaleDraftLineDto(
    @SerializedName("product_id") val productId: Int,
    @SerializedName("product_name") val productName: String,
    val quantity: String,
    @SerializedName("unit_price") val unitPrice: String,
    @SerializedName("discount_amount") val discountAmount: String,
    @SerializedName("tax_amount") val taxAmount: String,
    @SerializedName("line_total") val lineTotal: String,
    val note: String?,
)

/** Carrito en curso, recalculado por el backend (`SalesService.preview_sale`)
 * en cada operación — ningún total se computa acá, siempre se refleja el
 * que ya viene en la respuesta. */
data class SaleDraftDto(
    @SerializedName("draft_id") val draftId: String,
    val subtotal: String,
    @SerializedName("discount_total") val discountTotal: String,
    @SerializedName("tax_total") val taxTotal: String,
    val total: String,
    val items: List<SaleDraftLineDto>,
)

data class SalePaymentRequest(
    @SerializedName("payment_method") val paymentMethod: String,
    val amount: String,
    val reference: String? = null,
)

data class CompleteSaleRequest(
    val payments: List<SalePaymentRequest>,
    @SerializedName("customer_id") val customerId: Int? = null,
    @SerializedName("customer_name") val customerName: String? = null,
    @SerializedName("customer_document") val customerDocument: String? = null,
)

data class SaleItemDto(
    val id: Int,
    @SerializedName("product_id") val productId: Int,
    @SerializedName("product_name") val productName: String,
    val quantity: String,
    @SerializedName("unit_price") val unitPrice: String,
    @SerializedName("discount_amount") val discountAmount: String,
    @SerializedName("tax_amount") val taxAmount: String,
    @SerializedName("line_total") val lineTotal: String,
    val note: String?,
    @SerializedName("sale_unit") val saleUnit: String,
    @SerializedName("unit_of_measure") val unitOfMeasure: String,
)

data class SalePaymentDto(
    val id: Int,
    @SerializedName("payment_method") val paymentMethod: String,
    val amount: String,
    val reference: String?,
)

/** Venta ya persistida — misma forma que devuelven tanto `POST
 * .../complete` como `GET /sales/{id}` (`CompletedSaleSchema`). */
data class CompletedSaleDto(
    val id: Int,
    val status: String,
    @SerializedName("sale_type") val saleType: String,
    @SerializedName("customer_id") val customerId: Int?,
    val subtotal: String,
    @SerializedName("discount_total") val discountTotal: String,
    @SerializedName("tax_total") val taxTotal: String,
    val total: String,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("created_by_user_id") val createdByUserId: Int?,
    @SerializedName("cash_session_id") val cashSessionId: Int?,
    @SerializedName("customer_name") val customerName: String?,
    @SerializedName("customer_document") val customerDocument: String?,
    val items: List<SaleItemDto>,
    val payments: List<SalePaymentDto>,
)
