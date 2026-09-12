package com.astrim.licensemanager.data

import android.content.Context
import android.database.sqlite.SQLiteDatabase

/**
 * Copia local y privada de `licenses_pool.db` — el mismo archivo que ya
 * genera el escritorio (`scripts/generate_license_pool.py`, ver
 * `src/pos/modules/licensing/infrastructure/pool_models.py`), empaquetada
 * como asset y copiada una sola vez al almacenamiento privado de esta
 * instalación de la app. A partir de ahí se lee y se escribe únicamente
 * esa copia: no hay sincronización con el escritorio ni con el
 * repositorio, tal como se pidió (sin Internet, sin servidor).
 *
 * `app_movement_log` es una tabla adicional, solo del lado de la app
 * (no existe en el esquema del escritorio): registra cada acción real
 * hecha desde ASTRIM License Manager para alimentar la pantalla de
 * Historial con datos reales.
 */
object LicensePoolDatabase {
    const val DATABASE_NAME = "licenses_pool.db"

    @Volatile
    private var instance: SQLiteDatabase? = null

    fun get(context: Context): SQLiteDatabase {
        return instance ?: synchronized(this) {
            instance ?: open(context.applicationContext).also { instance = it }
        }
    }

    /** Cierra la conexión activa (si existe) — se usa antes de reemplazar el
     * archivo físico al restaurar un respaldo (ver `BackupManager`). La
     * próxima llamada a [get] vuelve a abrirlo, ya con el archivo nuevo. */
    fun close() {
        synchronized(this) {
            instance?.close()
            instance = null
        }
    }

    private fun open(context: Context): SQLiteDatabase {
        val dbFile = context.getDatabasePath(DATABASE_NAME)
        if (!dbFile.exists()) {
            dbFile.parentFile?.mkdirs()
            context.assets.open(DATABASE_NAME).use { input ->
                dbFile.outputStream().use { output -> input.copyTo(output) }
            }
        }
        val database = SQLiteDatabase.openDatabase(
            dbFile.absolutePath,
            null,
            SQLiteDatabase.OPEN_READWRITE,
        )
        database.execSQL(
            """
            CREATE TABLE IF NOT EXISTS app_movement_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                company_name TEXT,
                company_nit TEXT,
                license_type TEXT NOT NULL,
                action TEXT NOT NULL,
                performed_by TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                notes TEXT
            )
            """.trimIndent(),
        )
        return database
    }
}
