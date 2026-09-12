package com.astrim.licensemanager.data

/**
 * Una fila de `license_pool_entries` — mismas columnas que ya define el
 * escritorio (`src/pos/modules/licensing/infrastructure/pool_models.py`).
 * `status`/`licenseType` llegan tal cual están en la base ("AVAILABLE",
 * "ACTIVATED", "EXPIRED", "BLOCKED" / "TRIAL", "SEMIANNUAL", "ANNUAL").
 */
data class LicensePoolEntry(
    val id: Long,
    val code: String,
    val licenseType: String,
    val status: String,
    val companyName: String?,
    val companyNit: String?,
    val ownerName: String?,
    val hardwareFingerprint: String?,
    val createdAt: String,
    val activatedAt: String?,
    val expiresAt: String?,
    val lastVerifiedAt: String?,
    val notes: String?,
)

/** Un evento del registro local de movimientos (`app_movement_log`) — solo
 * existe en la copia del teléfono, no en el esquema del escritorio: es el
 * historial de lo que se hizo desde esta app (ver `LicensePoolDatabase`). */
data class MovementLogEntry(
    val id: Long,
    val code: String,
    val companyName: String?,
    val companyNit: String?,
    val licenseType: String,
    val action: String,
    val performedBy: String,
    val occurredAt: String,
    val notes: String?,
)
