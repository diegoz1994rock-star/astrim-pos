package com.astrim.pos.core.network.dto

import com.google.gson.annotations.SerializedName

/**
 * Espejo exacto de los DTOs de la API documentados en API.md §3.7 —
 * mismos nombres de campo que `sync/server/api/dispatch_schemas.py`.
 */
data class DispatchOrderItemDto(
    val id: Int,
    @SerializedName("order_id") val orderId: Int,
    @SerializedName("product_id") val productId: Int,
    @SerializedName("product_name") val productName: String,
    val quantity: Int,
    val notes: String?,
    val status: String,
    @SerializedName("product_image_path") val productImagePath: String?,
)

/** Un pedido/venta como tarjeta de Despacho — una tarjeta por cliente/pedido,
 * no por producto (misma unidad que muestra `kitchen_view.py` del escritorio). */
data class DispatchOrderCardDto(
    @SerializedName("order_id") val orderId: Int,
    val origin: String,
    @SerializedName("customer_name") val customerName: String,
    @SerializedName("customer_document") val customerDocument: String?,
    @SerializedName("is_paid") val isPaid: Boolean,
    @SerializedName("caja_name") val cajaName: String?,
    @SerializedName("dispatch_status") val dispatchStatus: String,
    @SerializedName("item_count") val itemCount: Int,
    @SerializedName("total_units") val totalUnits: Int,
    val items: List<DispatchOrderItemDto>,
    @SerializedName("created_at") val createdAt: String?,
    @SerializedName("created_by_user_name") val createdByUserName: String?,
    @SerializedName("dispatched_by_user_name") val dispatchedByUserName: String?,
    @SerializedName("sale_id") val saleId: Int?,
)
