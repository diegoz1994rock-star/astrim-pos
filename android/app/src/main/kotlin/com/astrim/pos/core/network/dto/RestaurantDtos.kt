package com.astrim.pos.core.network.dto

import com.google.gson.annotations.SerializedName

/**
 * Espejo exacto de los DTOs de la API documentados en API.md §3.11 —
 * mismos nombres de campo que `sync/server/api/restaurant_schemas.py`.
 * Cantidades y montos van como `String` (nunca `Float`/`Double`), mismo
 * criterio que `SalesDtos.kt`.
 */
data class OrderItemLineRequest(
    @SerializedName("product_id") val productId: Int,
    val quantity: String,
    val note: String? = null,
)

data class OrderPreviewRequest(
    val items: List<OrderItemLineRequest>,
)

/** Total en vivo del pedido en construcción — misma forma que
 * [SaleDraftDto] sin `draft_id`: acá no hay carrito persistido en el
 * servidor, el pedido vive en memoria de este cliente hasta confirmarlo. */
data class OrderPreviewDto(
    val subtotal: String,
    @SerializedName("discount_total") val discountTotal: String,
    @SerializedName("tax_total") val taxTotal: String,
    val total: String,
    val items: List<SaleDraftLineDto>,
)

data class CreateOrderRequest(
    val items: List<OrderItemLineRequest>,
    @SerializedName("customer_name") val customerName: String? = null,
    @SerializedName("customer_document") val customerDocument: String? = null,
)

data class OrderItemDto(
    val id: Int,
    @SerializedName("product_id") val productId: Int,
    @SerializedName("product_name") val productName: String,
    val quantity: Int,
    val notes: String?,
    val status: String,
    @SerializedName("product_image_path") val productImagePath: String?,
)

/** El pedido ya confirmado — misma forma que devuelve `POST
 * /restaurant/orders`. Nace `status: "pending"`, sin venta asociada
 * (`sale_id: null`), y aparece automáticamente en Despacho. */
data class OrderDto(
    val id: Int,
    @SerializedName("table_session_id") val tableSessionId: Int?,
    @SerializedName("order_type") val orderType: String,
    val status: String,
    val items: List<OrderItemDto>,
    @SerializedName("created_at") val createdAt: String?,
    @SerializedName("created_by_user_id") val createdByUserId: Int?,
    @SerializedName("sale_id") val saleId: Int?,
    @SerializedName("customer_name") val customerName: String?,
    @SerializedName("customer_document") val customerDocument: String?,
    val origin: String,
    @SerializedName("dispatched_by_user_id") val dispatchedByUserId: Int?,
)
