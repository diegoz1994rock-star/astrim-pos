package com.astrim.pos.core.network.dto

import com.google.gson.annotations.SerializedName

/**
 * Espejo exacto de los DTOs de la API documentados en API.md §3.12 —
 * mismos nombres de campo que `sync/server/api/payment_methods_schemas.py`.
 * Solo el método predeterminado de cada tipo, de solo lectura.
 */
data class QrPaymentConfigDto(
    val id: Int,
    val name: String,
    @SerializedName("has_image") val hasImage: Boolean,
)

data class NequiPaymentConfigDto(
    val id: Int,
    val number: String,
)

data class BreBPaymentConfigDto(
    val id: Int,
    val key: String,
)
