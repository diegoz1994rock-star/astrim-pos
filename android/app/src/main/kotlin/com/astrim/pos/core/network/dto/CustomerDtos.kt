package com.astrim.pos.core.network.dto

import com.google.gson.annotations.SerializedName

/**
 * Espejo exacto de los DTOs de la API documentados en API.md §3.9 — mismos
 * nombres de campo que `sync/server/api/customers_schemas.py`. Los montos
 * quedan como `String` a propósito, igual que en el resto de la app: el
 * backend serializa todo `Decimal` como string (ver API.md §1).
 */
data class CustomerDto(
    val id: Int,
    @SerializedName("full_name") val fullName: String,
    @SerializedName("document_id") val documentId: String?,
    val email: String?,
    val phone: String?,
    val address: String?,
    @SerializedName("credit_limit") val creditLimit: String,
    @SerializedName("current_debt") val currentDebt: String,
    @SerializedName("loyalty_points_balance") val loyaltyPointsBalance: Int,
)

data class CreateCustomerRequest(
    @SerializedName("full_name") val fullName: String,
    @SerializedName("document_id") val documentId: String? = null,
    val email: String? = null,
    val phone: String? = null,
    val address: String? = null,
    @SerializedName("credit_limit") val creditLimit: String = "0",
)

data class RegisterCreditPaymentRequest(
    val amount: String,
    val reference: String? = null,
)
