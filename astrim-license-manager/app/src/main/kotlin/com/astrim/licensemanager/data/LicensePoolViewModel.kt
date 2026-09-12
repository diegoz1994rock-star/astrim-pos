package com.astrim.licensemanager.data

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** Conteos reales del pool completo (incluye los códigos todavía
 * DISPONIBLES, que no se listan como tarjetas en ninguna pantalla). */
data class LicensePoolSummary(
    val available: Int = 0,
    val active: Int = 0,
    val expired: Int = 0,
    val blocked: Int = 0,
    val totalCompanies: Int = 0,
    val totalDevices: Int = 0,
)

private const val PERFORMED_BY = "ASTRIM License Manager"

/**
 * Única instancia compartida entre todas las pantallas (se crea una vez
 * en [com.astrim.licensemanager.ui.LicenseManagerApp] y se pasa hacia
 * abajo) — así una acción en una pantalla (por ejemplo renovar en
 * Licencias) se refleja de inmediato en el Dashboard, Empresas, Buscar e
 * Historial sin necesidad de recargar la app.
 */
class LicensePoolViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = LicensePoolRepository(application)

    private val _assignedEntries = MutableStateFlow<List<LicensePoolEntry>>(emptyList())
    val assignedEntries: StateFlow<List<LicensePoolEntry>> = _assignedEntries.asStateFlow()

    private val _summary = MutableStateFlow(LicensePoolSummary())
    val summary: StateFlow<LicensePoolSummary> = _summary.asStateFlow()

    private val _movementLog = MutableStateFlow<List<MovementLogEntry>>(emptyList())
    val movementLog: StateFlow<List<MovementLogEntry>> = _movementLog.asStateFlow()

    private val _typeBreakdown = MutableStateFlow<Map<String, Map<String, Int>>>(emptyMap())
    val typeBreakdown: StateFlow<Map<String, Map<String, Int>>> = _typeBreakdown.asStateFlow()

    private val _availableSample = MutableStateFlow<List<LicensePoolEntry>>(emptyList())
    val availableSample: StateFlow<List<LicensePoolEntry>> = _availableSample.asStateFlow()

    init {
        reload()
    }

    fun reload() {
        viewModelScope.launch(Dispatchers.IO) {
            repository.refreshExpirations()
            pushState()
        }
    }

    private fun pushState() {
        val counts = repository.countByStatus()
        _assignedEntries.value = repository.getAssignedEntries()
        _summary.value = LicensePoolSummary(
            available = counts["AVAILABLE"] ?: 0,
            active = counts["ACTIVATED"] ?: 0,
            expired = counts["EXPIRED"] ?: 0,
            blocked = counts["BLOCKED"] ?: 0,
            totalCompanies = repository.countDistinctCompanies(),
            totalDevices = repository.countDevices(),
        )
        _movementLog.value = repository.getMovementLog()
        _typeBreakdown.value = repository.countByTypeAndStatus()
        _availableSample.value = repository.getAvailableSample()
    }

    /** Entrega el primer código disponible del tipo pedido — null si el
     * pool ya no tiene códigos libres de ese tipo. */
    fun activateLicense(
        licenseTypeLabel: String,
        companyName: String,
        companyNit: String,
        ownerName: String,
    ): LicensePoolEntry? {
        val result = repository.activate(
            licenseType = licenseTypeRawValue(licenseTypeLabel),
            companyName = companyName,
            companyNit = companyNit,
            ownerName = ownerName,
            performedBy = PERFORMED_BY,
        )
        reload()
        return result
    }

    fun renewLicense(entry: LicensePoolEntry): LicensePoolEntry {
        val result = repository.renew(entry, PERFORMED_BY)
        reload()
        return result
    }

    fun blockLicense(entry: LicensePoolEntry): LicensePoolEntry {
        val result = repository.block(entry, PERFORMED_BY)
        reload()
        return result
    }

    fun unblockLicense(entry: LicensePoolEntry): LicensePoolEntry {
        val result = repository.unblock(entry, PERFORMED_BY)
        reload()
        return result
    }
}
