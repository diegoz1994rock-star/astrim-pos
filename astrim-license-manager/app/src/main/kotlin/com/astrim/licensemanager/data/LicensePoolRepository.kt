package com.astrim.licensemanager.data

import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeFormatterBuilder
import java.time.temporal.ChronoField

private val poolTimestampFormatter = DateTimeFormatterBuilder()
    .appendPattern("yyyy-MM-dd HH:mm:ss")
    .appendFraction(ChronoField.MICRO_OF_SECOND, 0, 6, true)
    .toFormatter()

/** `licenses_pool.db` guarda las fechas como texto ("2026-07-31
 * 13:27:40.990964", UTC) — mismo formato que ya usa el escritorio. */
fun parsePoolDateTime(raw: String?): LocalDateTime? {
    if (raw.isNullOrBlank()) return null
    return try {
        LocalDateTime.parse(raw, poolTimestampFormatter)
    } catch (error: Exception) {
        null
    }
}

private fun formatPoolDateTime(value: LocalDateTime): String =
    value.format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss.SSSSSS"))

/**
 * Acceso a `license_pool_entries` (mismo esquema que el escritorio) y a
 * `app_movement_log` (solo de esta app) sobre la copia local del
 * teléfono — ver `LicensePoolDatabase`. Todas las escrituras (activar,
 * renovar, bloquear, desbloquear) quedan registradas también en el
 * historial local.
 */
class LicensePoolRepository(private val context: Context) {
    /** Se resuelve en cada acceso (no se guarda una sola vez) para que,
     * después de restaurar un respaldo — que cierra y reemplaza el
     * archivo físico (ver `BackupManager.restoreBackup`) —, esta
     * instancia ya existente vuelva a apuntar a la conexión nueva en vez
     * de quedarse con una referencia cerrada. */
    private val db: SQLiteDatabase
        get() = LicensePoolDatabase.get(context)

    /** Licencias ya entregadas a un cliente (no incluye el pool completo
     * de códigos disponibles) — es lo que muestran Licencias, Empresas y
     * Buscar como tarjetas. */
    fun getAssignedEntries(): List<LicensePoolEntry> =
        query("SELECT * FROM license_pool_entries WHERE status != 'AVAILABLE' ORDER BY id DESC")

    /** Una muestra acotada de códigos todavía DISPONIBLES — no tiene
     * sentido listar los 30.000 códigos del pool (son intercambiables
     * dentro de un mismo tipo), pero sí mostrar algunos listos para
     * entregar (ver Licencias, filtro "Disponibles"). */
    fun getAvailableSample(limit: Int = 30): List<LicensePoolEntry> =
        query("SELECT * FROM license_pool_entries WHERE status = 'AVAILABLE' ORDER BY id LIMIT ?", arrayOf(limit.toString()))

    fun getByCode(code: String): LicensePoolEntry? =
        query("SELECT * FROM license_pool_entries WHERE code = ? LIMIT 1", arrayOf(code)).firstOrNull()

    fun countByStatus(): Map<String, Int> {
        val counts = mutableMapOf<String, Int>()
        db.rawQuery("SELECT status, COUNT(*) FROM license_pool_entries GROUP BY status", null).use { cursor ->
            while (cursor.moveToNext()) {
                counts[cursor.getString(0)] = cursor.getInt(1)
            }
        }
        return counts
    }

    /** Conteo por tipo y estado — alimenta las 3 tarjetas de "Licencias
     * por tipo" del Dashboard (Disponible/Usada/Vencida por cada tipo). */
    fun countByTypeAndStatus(): Map<String, Map<String, Int>> {
        val result = mutableMapOf<String, MutableMap<String, Int>>()
        db.rawQuery(
            "SELECT license_type, status, COUNT(*) FROM license_pool_entries GROUP BY license_type, status",
            null,
        ).use { cursor ->
            while (cursor.moveToNext()) {
                val type = cursor.getString(0)
                val status = cursor.getString(1)
                val count = cursor.getInt(2)
                result.getOrPut(type) { mutableMapOf() }[status] = count
            }
        }
        return result
    }

    fun countDistinctCompanies(): Int = scalarInt(
        "SELECT COUNT(DISTINCT company_nit) FROM license_pool_entries " +
            "WHERE status != 'AVAILABLE' AND company_nit IS NOT NULL",
    )

    fun countDevices(): Int = scalarInt(
        "SELECT COUNT(DISTINCT hardware_fingerprint) FROM license_pool_entries " +
            "WHERE hardware_fingerprint IS NOT NULL",
    )

    /** Entrega el primer código DISPONIBLE del tipo pedido a una empresa
     * nueva — null si el pool ya no tiene códigos libres de ese tipo. */
    fun activate(
        licenseType: String,
        companyName: String,
        companyNit: String,
        ownerName: String,
        performedBy: String,
    ): LicensePoolEntry? {
        val candidate = query(
            "SELECT * FROM license_pool_entries WHERE status = 'AVAILABLE' AND license_type = ? " +
                "ORDER BY id LIMIT 1",
            arrayOf(licenseType),
        ).firstOrNull() ?: return null

        val now = LocalDateTime.now()
        val expiresAt = now.plusDays(durationDaysFor(licenseType))
        val values = ContentValues().apply {
            put("status", "ACTIVATED")
            put("company_name", companyName)
            put("company_nit", companyNit)
            put("owner_name", ownerName)
            put("activated_at", formatPoolDateTime(now))
            put("expires_at", formatPoolDateTime(expiresAt))
            put("last_verified_at", formatPoolDateTime(now))
        }
        db.update("license_pool_entries", values, "id = ?", arrayOf(candidate.id.toString()))
        logMovement(candidate.code, companyName, companyNit, licenseType, "ACTIVATION", performedBy, "Licencia entregada desde ASTRIM License Manager.")
        return getByCode(candidate.code)
    }

    fun renew(entry: LicensePoolEntry, performedBy: String): LicensePoolEntry {
        val now = LocalDateTime.now()
        val expiresAt = parsePoolDateTime(entry.expiresAt)
        val base = if (expiresAt == null || expiresAt.isBefore(now)) now else expiresAt
        val newExpiresAt = base.plusDays(durationDaysFor(entry.licenseType))
        val values = ContentValues().apply {
            put("status", "ACTIVATED")
            put("expires_at", formatPoolDateTime(newExpiresAt))
            put("last_verified_at", formatPoolDateTime(now))
        }
        db.update("license_pool_entries", values, "id = ?", arrayOf(entry.id.toString()))
        logMovement(entry.code, entry.companyName, entry.companyNit, entry.licenseType, "RENEWAL", performedBy, "Renovación desde ASTRIM License Manager.")
        return getByCode(entry.code)!!
    }

    fun block(entry: LicensePoolEntry, performedBy: String): LicensePoolEntry {
        db.update(
            "license_pool_entries",
            ContentValues().apply { put("status", "BLOCKED") },
            "id = ?",
            arrayOf(entry.id.toString()),
        )
        logMovement(entry.code, entry.companyName, entry.companyNit, entry.licenseType, "BLOCK", performedBy, "Bloqueada desde ASTRIM License Manager.")
        return getByCode(entry.code)!!
    }

    fun unblock(entry: LicensePoolEntry, performedBy: String): LicensePoolEntry {
        val now = LocalDateTime.now()
        val expiresAt = parsePoolDateTime(entry.expiresAt)
        val newStatus = if (expiresAt != null && expiresAt.isBefore(now)) "EXPIRED" else "ACTIVATED"
        db.update(
            "license_pool_entries",
            ContentValues().apply { put("status", newStatus) },
            "id = ?",
            arrayOf(entry.id.toString()),
        )
        logMovement(entry.code, entry.companyName, entry.companyNit, entry.licenseType, "UNBLOCK", performedBy, "Desbloqueada desde ASTRIM License Manager.")
        return getByCode(entry.code)!!
    }

    /** Pasa a EXPIRED cualquier licencia ACTIVATED cuya fecha de
     * vencimiento ya pasó — se llama al recargar los datos para que el
     * estado mostrado siempre sea el real. */
    fun refreshExpirations() {
        val now = formatPoolDateTime(LocalDateTime.now())
        val expiring = query(
            "SELECT * FROM license_pool_entries WHERE status = 'ACTIVATED' " +
                "AND expires_at IS NOT NULL AND expires_at < ?",
            arrayOf(now),
        )
        expiring.forEach { entry ->
            db.update(
                "license_pool_entries",
                ContentValues().apply { put("status", "EXPIRED") },
                "id = ?",
                arrayOf(entry.id.toString()),
            )
            logMovement(entry.code, entry.companyName, entry.companyNit, entry.licenseType, "EXPIRATION", "Sistema", "Vencimiento automático.")
        }
    }

    fun countMovementLog(): Int = scalarInt("SELECT COUNT(*) FROM app_movement_log")

    fun getMovementLog(limit: Int = 300): List<MovementLogEntry> {
        val entries = mutableListOf<MovementLogEntry>()
        db.rawQuery(
            "SELECT id, code, company_name, company_nit, license_type, action, performed_by, occurred_at, notes " +
                "FROM app_movement_log ORDER BY id DESC LIMIT ?",
            arrayOf(limit.toString()),
        ).use { cursor ->
            while (cursor.moveToNext()) {
                entries += MovementLogEntry(
                    id = cursor.getLong(0),
                    code = cursor.getString(1),
                    companyName = cursor.getStringOrNull(2),
                    companyNit = cursor.getStringOrNull(3),
                    licenseType = cursor.getString(4),
                    action = cursor.getString(5),
                    performedBy = cursor.getString(6),
                    occurredAt = cursor.getString(7),
                    notes = cursor.getStringOrNull(8),
                )
            }
        }
        return entries
    }

    private fun logMovement(
        code: String,
        companyName: String?,
        companyNit: String?,
        licenseType: String,
        action: String,
        performedBy: String,
        notes: String?,
    ) {
        val values = ContentValues().apply {
            put("code", code)
            put("company_name", companyName)
            put("company_nit", companyNit)
            put("license_type", licenseType)
            put("action", action)
            put("performed_by", performedBy)
            put("occurred_at", formatPoolDateTime(LocalDateTime.now()))
            put("notes", notes)
        }
        db.insert("app_movement_log", null, values)
    }

    private fun scalarInt(sql: String): Int {
        db.rawQuery(sql, null).use { cursor ->
            return if (cursor.moveToFirst()) cursor.getInt(0) else 0
        }
    }

    private fun query(sql: String, args: Array<String>? = null): List<LicensePoolEntry> {
        val entries = mutableListOf<LicensePoolEntry>()
        db.rawQuery(sql, args).use { cursor ->
            while (cursor.moveToNext()) {
                entries += cursor.toLicensePoolEntry()
            }
        }
        return entries
    }

    companion object {
        fun durationDaysFor(licenseType: String): Long = when (licenseType) {
            "TRIAL" -> 30L
            "SEMIANNUAL" -> 182L
            "ANNUAL" -> 365L
            else -> 30L
        }
    }
}

private fun Cursor.toLicensePoolEntry(): LicensePoolEntry = LicensePoolEntry(
    id = getLong(getColumnIndexOrThrow("id")),
    code = getString(getColumnIndexOrThrow("code")),
    licenseType = getString(getColumnIndexOrThrow("license_type")),
    status = getString(getColumnIndexOrThrow("status")),
    companyName = getStringOrNull(getColumnIndexOrThrow("company_name")),
    companyNit = getStringOrNull(getColumnIndexOrThrow("company_nit")),
    ownerName = getStringOrNull(getColumnIndexOrThrow("owner_name")),
    hardwareFingerprint = getStringOrNull(getColumnIndexOrThrow("hardware_fingerprint")),
    createdAt = getString(getColumnIndexOrThrow("created_at")),
    activatedAt = getStringOrNull(getColumnIndexOrThrow("activated_at")),
    expiresAt = getStringOrNull(getColumnIndexOrThrow("expires_at")),
    lastVerifiedAt = getStringOrNull(getColumnIndexOrThrow("last_verified_at")),
    notes = getStringOrNull(getColumnIndexOrThrow("notes")),
)

private fun Cursor.getStringOrNull(index: Int): String? = if (isNull(index)) null else getString(index)
