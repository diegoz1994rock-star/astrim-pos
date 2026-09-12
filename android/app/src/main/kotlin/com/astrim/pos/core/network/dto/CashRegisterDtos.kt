package com.astrim.pos.core.network.dto

import com.google.gson.annotations.SerializedName

/**
 * Espejo exacto de los DTOs de la API de Caja documentados en API.md
 * §3.10 — mismos nombres de campo que el backend (snake_case, mapeado acá
 * vía [SerializedName]). `expected_amount`/`difference` llegan `null`
 * mientras el turno está abierto, igual que el escritorio.
 */
data class CashRegisterDto(
    val id: Int,
    val name: String,
    val location: String?,
    @SerializedName("is_active") val isActive: Boolean,
)

data class CashSessionDto(
    val id: Int,
    @SerializedName("cash_register_id") val cashRegisterId: Int,
    @SerializedName("cash_register_name") val cashRegisterName: String,
    val status: String,
    @SerializedName("opened_by_user_id") val openedByUserId: Int,
    @SerializedName("opened_at") val openedAt: String,
    @SerializedName("opening_amount") val openingAmount: String,
    @SerializedName("closed_at") val closedAt: String?,
    @SerializedName("closing_amount") val closingAmount: String?,
    @SerializedName("expected_amount") val expectedAmount: String?,
    val difference: String?,
)

data class CashRegisterStatusDto(
    @SerializedName("cash_register") val cashRegister: CashRegisterDto,
    val session: CashSessionDto?,
)

data class OpenCashSessionRequest(
    @SerializedName("opening_amount") val openingAmount: String,
)

data class CloseCashSessionRequest(
    @SerializedName("counted_amount") val countedAmount: String,
)
