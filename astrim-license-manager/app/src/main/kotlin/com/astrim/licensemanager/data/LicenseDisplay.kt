package com.astrim.licensemanager.data

import androidx.compose.ui.graphics.Color
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit

/** Estado visual derivado de una licencia real — mismos 5 colores que ya
 * usan las pantallas de Licencias/Empresas/Buscar. `ACTIVATED` en la base
 * se reparte en Activa/Próxima a vencer/Vencida según la fecha real de
 * vencimiento (la base solo guarda 4 estados crudos: AVAILABLE, ACTIVATED,
 * EXPIRED, BLOCKED). */
enum class LicenseDisplayStatus(val label: String, val color: Color) {
    AVAILABLE("Disponible", Color(0xFF66BB6A)),
    ACTIVE("Activa", Color(0xFF64B5F6)),
    UPCOMING_EXPIRATION("Próxima a vencer", Color(0xFFFFC107)),
    EXPIRED("Vencida", Color(0xFFE57373)),
    BLOCKED("Bloqueada", Color(0xFFB0BEC5)),
}

private const val UPCOMING_EXPIRATION_THRESHOLD_DAYS = 30L

fun LicensePoolEntry.displayStatus(referenceDate: LocalDateTime = LocalDateTime.now()): LicenseDisplayStatus =
    when (status) {
        "AVAILABLE" -> LicenseDisplayStatus.AVAILABLE
        "BLOCKED" -> LicenseDisplayStatus.BLOCKED
        "EXPIRED" -> LicenseDisplayStatus.EXPIRED
        "ACTIVATED" -> {
            val expires = parsePoolDateTime(expiresAt)
            when {
                expires == null -> LicenseDisplayStatus.ACTIVE
                expires.isBefore(referenceDate) -> LicenseDisplayStatus.EXPIRED
                expires.isBefore(referenceDate.plusDays(UPCOMING_EXPIRATION_THRESHOLD_DAYS)) ->
                    LicenseDisplayStatus.UPCOMING_EXPIRATION
                else -> LicenseDisplayStatus.ACTIVE
            }
        }
        else -> LicenseDisplayStatus.ACTIVE
    }

/** Días que faltan para vencer (negativo si ya venció) — null si la
 * licencia nunca fue activada. */
fun LicensePoolEntry.daysRemaining(referenceDate: LocalDateTime = LocalDateTime.now()): Long? {
    val expires = parsePoolDateTime(expiresAt) ?: return null
    return ChronoUnit.DAYS.between(referenceDate.toLocalDate(), expires.toLocalDate())
}

fun LicensePoolEntry.daysRemainingLabel(referenceDate: LocalDateTime = LocalDateTime.now()): String {
    val days = daysRemaining(referenceDate) ?: return "—"
    return when {
        days < 0 -> "Vencida hace ${-days} días"
        days == 0L -> "Vence hoy"
        else -> "$days días"
    }
}

fun licenseTypeLabel(rawType: String): String = when (rawType) {
    "TRIAL" -> "30 días"
    "SEMIANNUAL" -> "6 meses"
    "ANNUAL" -> "1 año"
    else -> rawType
}

fun licenseTypeRawValue(label: String): String = when (label) {
    "30 días" -> "TRIAL"
    "6 meses" -> "SEMIANNUAL"
    "1 año" -> "ANNUAL"
    else -> "TRIAL"
}

private val displayDateFormatter: DateTimeFormatter = DateTimeFormatter.ofPattern("dd/MM/yyyy")
private val displayDateTimeFormatter: DateTimeFormatter = DateTimeFormatter.ofPattern("dd/MM/yyyy · HH:mm")

fun formatDisplayDate(raw: String?): String = parsePoolDateTime(raw)?.format(displayDateFormatter) ?: "—"

fun formatDisplayDateTime(raw: String?): String = parsePoolDateTime(raw)?.format(displayDateTimeFormatter) ?: "—"

fun movementActionLabel(rawAction: String): String = when (rawAction) {
    "ACTIVATION" -> "Activación"
    "RENEWAL" -> "Renovación"
    "BLOCK" -> "Bloqueo"
    "UNBLOCK" -> "Desbloqueo"
    "EXPIRATION" -> "Vencimiento"
    else -> rawAction
}

fun relativeTimeLabel(raw: String?, referenceDate: LocalDateTime = LocalDateTime.now()): String {
    val parsed = parsePoolDateTime(raw) ?: return "—"
    val minutes = ChronoUnit.MINUTES.between(parsed, referenceDate)
    val hours = minutes / 60
    val days = minutes / (60 * 24)
    return when {
        minutes < 1 -> "Hace instantes"
        minutes < 60 -> "Hace $minutes ${if (minutes == 1L) "minuto" else "minutos"}"
        hours < 24 -> "Hace $hours ${if (hours == 1L) "hora" else "horas"}"
        else -> "Hace $days ${if (days == 1L) "día" else "días"}"
    }
}

fun movementActionColor(rawAction: String): Color = when (rawAction) {
    "ACTIVATION" -> LicenseDisplayStatus.AVAILABLE.color
    "RENEWAL" -> LicenseDisplayStatus.ACTIVE.color
    "BLOCK" -> LicenseDisplayStatus.EXPIRED.color
    "UNBLOCK" -> LicenseDisplayStatus.UPCOMING_EXPIRATION.color
    "EXPIRATION" -> LicenseDisplayStatus.BLOCKED.color
    else -> LicenseDisplayStatus.BLOCKED.color
}
