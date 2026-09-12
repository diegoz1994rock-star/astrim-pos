package com.astrim.pos.core.network.dto

import com.google.gson.annotations.SerializedName

/**
 * Espejo exacto de los DTOs de la API documentados en API.md §3.1 — mismos
 * nombres de campo que el backend (snake_case, mapeado acá vía
 * [SerializedName]). Nunca se inventa un campo nuevo ni se recalcula nada
 * acá: esta app no tiene lógica de negocio propia.
 */
data class LoginRequest(
    val username: String,
    val password: String,
)

data class LoginResponse(
    val token: String,
    @SerializedName("expires_at") val expiresAt: String,
    val session: SessionInfoDto,
)

data class SessionInfoDto(
    @SerializedName("user_id") val userId: Int,
    val username: String,
    @SerializedName("full_name") val fullName: String,
    @SerializedName("is_admin") val isAdmin: Boolean,
    @SerializedName("permission_codes") val permissionCodes: List<String>,
    @SerializedName("logged_in_at") val loggedInAt: String,
    @SerializedName("job_position_name") val jobPositionName: String? = null,
)
