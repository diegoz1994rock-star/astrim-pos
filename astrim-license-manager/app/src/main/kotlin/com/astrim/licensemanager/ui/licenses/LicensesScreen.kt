package com.astrim.licensemanager.ui.licenses

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.astrim.licensemanager.data.LicensePoolEntry
import com.astrim.licensemanager.data.LicensePoolViewModel
import com.astrim.licensemanager.data.daysRemainingLabel
import com.astrim.licensemanager.data.formatDisplayDate
import com.astrim.licensemanager.data.formatDisplayDateTime
import com.astrim.licensemanager.data.licenseTypeLabel
import com.astrim.licensemanager.ui.common.AppBackground
import com.astrim.licensemanager.ui.common.AppCardBackground
import com.astrim.licensemanager.ui.common.AppOutline
import com.astrim.licensemanager.ui.common.AppTextMuted
import com.astrim.licensemanager.ui.common.AppTextSecondary
import com.astrim.licensemanager.ui.common.DarkOutlinedField
import com.astrim.licensemanager.ui.common.GradientButtonStart
import com.astrim.licensemanager.ui.common.KpiCard
import com.astrim.licensemanager.ui.common.copyToClipboard
import com.astrim.licensemanager.ui.common.shareLicenseText
import com.astrim.licensemanager.ui.common.showToast

/** Estado visual de una licencia — mismos 4 colores del diseño original
 * (Disponible=verde, Activa=azul, Vencida=rojo, Bloqueada=gris), leído
 * directamente del estado crudo de `license_pool_entries` (sin el
 * matiz "próxima a vencer" que sí usan Empresas/Buscar, para no cambiar
 * el diseño de esta pantalla). */
private enum class LicenseStatus(val label: String, val color: Color) {
    AVAILABLE("Disponible", Color(0xFF66BB6A)),
    ACTIVE("Activa", Color(0xFF64B5F6)),
    EXPIRED("Vencida", Color(0xFFE57373)),
    BLOCKED("Bloqueada", Color(0xFFB0BEC5)),
}

private fun LicensePoolEntry.toUiStatus(): LicenseStatus = when (status) {
    "AVAILABLE" -> LicenseStatus.AVAILABLE
    "EXPIRED" -> LicenseStatus.EXPIRED
    "BLOCKED" -> LicenseStatus.BLOCKED
    else -> LicenseStatus.ACTIVE
}

private val quickFilters = listOf(
    "Todos", "30 días", "6 meses", "1 año", "Disponibles", "Activas", "Vencidas", "Bloqueadas",
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LicensesScreen(viewModel: LicensePoolViewModel, onNewLicenseClick: () -> Unit = {}) {
    val context = LocalContext.current
    val summary by viewModel.summary.collectAsStateWithLifecycle()
    val assignedEntries by viewModel.assignedEntries.collectAsStateWithLifecycle()
    val availableSample by viewModel.availableSample.collectAsStateWithLifecycle()

    var searchQuery by remember { mutableStateOf("") }
    var selectedFilter by remember { mutableStateOf("Todos") }
    var selectedLicense by remember { mutableStateOf<LicensePoolEntry?>(null) }

    val displayedLicenses = remember(assignedEntries, availableSample, searchQuery, selectedFilter) {
        val base = if (selectedFilter == "Disponibles") availableSample else assignedEntries
        base.filter { entry ->
            val matchesSearch = searchQuery.isBlank() ||
                entry.code.contains(searchQuery, ignoreCase = true) ||
                entry.companyName.orEmpty().contains(searchQuery, ignoreCase = true) ||
                entry.companyNit.orEmpty().contains(searchQuery, ignoreCase = true)
            val matchesFilter = when (selectedFilter) {
                "Todos", "Disponibles" -> true
                "30 días" -> entry.licenseType == "TRIAL"
                "6 meses" -> entry.licenseType == "SEMIANNUAL"
                "1 año" -> entry.licenseType == "ANNUAL"
                "Activas" -> entry.status == "ACTIVATED"
                "Vencidas" -> entry.status == "EXPIRED"
                "Bloqueadas" -> entry.status == "BLOCKED"
                else -> true
            }
            matchesSearch && matchesFilter
        }
    }

    fun copyCode(code: String) {
        copyToClipboard(context, "Código de licencia", code)
        showToast(context, "Código copiado: $code")
    }

    fun shareCode(entry: LicensePoolEntry) {
        val message = "Licencia ASTRIM\nCódigo: ${entry.code}\nEmpresa: ${entry.companyName ?: "Sin asignar"}\n" +
            "Tipo: ${licenseTypeLabel(entry.licenseType)}\nVence: ${formatDisplayDate(entry.expiresAt)}"
        shareLicenseText(context, message)
    }

    fun renew(entry: LicensePoolEntry) {
        when (entry.status) {
            "AVAILABLE" -> showToast(context, "Esta licencia todavía no ha sido entregada.")
            "BLOCKED" -> showToast(context, "Desbloquéala antes de renovarla.")
            else -> {
                val updated = viewModel.renewLicense(entry)
                if (selectedLicense?.id == entry.id) selectedLicense = updated
                showToast(context, "Licencia renovada correctamente.")
            }
        }
    }

    fun toggleBlock(entry: LicensePoolEntry) {
        when (entry.status) {
            "AVAILABLE" -> showToast(context, "Esta licencia todavía no ha sido entregada.")
            "BLOCKED" -> {
                val updated = viewModel.unblockLicense(entry)
                if (selectedLicense?.id == entry.id) selectedLicense = updated
                showToast(context, "Licencia desbloqueada.")
            }
            else -> {
                val updated = viewModel.blockLicense(entry)
                if (selectedLicense?.id == entry.id) selectedLicense = updated
                showToast(context, "Licencia bloqueada.")
            }
        }
    }

    Scaffold(
        containerColor = AppBackground,
        topBar = {
            TopAppBar(
                title = { Text("Licencias") },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = AppBackground),
            )
        },
        floatingActionButton = {
            FloatingActionButton(
                onClick = onNewLicenseClick,
                containerColor = GradientButtonStart,
                contentColor = Color.White,
            ) {
                Icon(Icons.Default.Add, contentDescription = "Entregar nueva licencia")
            }
        },
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp),
        ) {
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                "Administra todas las licencias de ASTRIM.",
                color = AppTextSecondary,
                fontSize = 14.sp,
            )
            Spacer(modifier = Modifier.height(16.dp))

            SearchBarRow(searchQuery, onQueryChange = { searchQuery = it })
            Spacer(modifier = Modifier.height(16.dp))

            SummaryCountsRow(summary)
            Spacer(modifier = Modifier.height(16.dp))

            QuickFiltersRow(selectedFilter, onFilterSelected = { selectedFilter = it })
            Spacer(modifier = Modifier.height(8.dp))

            if (displayedLicenses.isEmpty()) {
                Spacer(modifier = Modifier.height(24.dp))
                Text(
                    "No hay licencias que coincidan con la búsqueda o el filtro seleccionado.",
                    color = AppTextMuted,
                    fontSize = 13.sp,
                )
            }
            displayedLicenses.forEach { license ->
                LicenseCard(
                    license = license,
                    onOpenDetails = { selectedLicense = license },
                    onCopyCode = { copyCode(license.code) },
                    onRenew = { renew(license) },
                    onToggleBlock = { toggleBlock(license) },
                )
                Spacer(modifier = Modifier.height(12.dp))
            }
            Spacer(modifier = Modifier.height(72.dp))
        }
    }

    val detailsLicense = selectedLicense
    if (detailsLicense != null) {
        LicenseDetailsDialog(
            license = detailsLicense,
            onDismiss = { selectedLicense = null },
            onCopyCode = { copyCode(detailsLicense.code) },
            onShare = { shareCode(detailsLicense) },
            onRenew = { renew(detailsLicense) },
        )
    }
}

@Composable
private fun SearchBarRow(query: String, onQueryChange: (String) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        DarkOutlinedField(
            value = query,
            onValueChange = onQueryChange,
            label = "Buscar por código, empresa o NIT...",
            leadingIcon = { Text("🔍", fontSize = 16.sp) },
            modifier = Modifier.weight(1f),
        )
        Spacer(modifier = Modifier.width(8.dp))
        Box(
            modifier = Modifier
                .size(56.dp)
                .clip(RoundedCornerShape(16.dp))
                .background(AppOutline),
            contentAlignment = Alignment.Center,
        ) {
            Text("🎚️", fontSize = 20.sp)
        }
    }
}

@Composable
private fun SummaryCountsRow(summary: com.astrim.licensemanager.data.LicensePoolSummary) {
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        KpiCard("Disponibles", summary.available.toString(), accentColor = LicenseStatus.AVAILABLE.color, modifier = Modifier.weight(1f))
        KpiCard("Activas", summary.active.toString(), accentColor = LicenseStatus.ACTIVE.color, modifier = Modifier.weight(1f))
        KpiCard("Vencidas", summary.expired.toString(), accentColor = LicenseStatus.EXPIRED.color, modifier = Modifier.weight(1f))
        KpiCard("Bloqueadas", summary.blocked.toString(), accentColor = LicenseStatus.BLOCKED.color, modifier = Modifier.weight(1f))
    }
}

@Composable
private fun QuickFiltersRow(selectedFilter: String, onFilterSelected: (String) -> Unit) {
    Row(
        modifier = Modifier.horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        quickFilters.forEach { filter ->
            FilterChip(
                selected = selectedFilter == filter,
                onClick = { onFilterSelected(filter) },
                label = { Text(filter) },
                colors = FilterChipDefaults.filterChipColors(
                    containerColor = AppCardBackground,
                    labelColor = AppTextSecondary,
                    selectedContainerColor = GradientButtonStart,
                    selectedLabelColor = Color.White,
                ),
            )
        }
    }
}

@Composable
private fun StatusBadge(status: LicenseStatus) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(50))
            .background(status.color.copy(alpha = 0.18f))
            .padding(horizontal = 10.dp, vertical = 4.dp),
    ) {
        Text(status.label, color = status.color, fontSize = 12.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun LicenseCard(
    license: LicensePoolEntry,
    onOpenDetails: () -> Unit,
    onCopyCode: () -> Unit,
    onRenew: () -> Unit,
    onToggleBlock: () -> Unit,
) {
    val uiStatus = license.toUiStatus()
    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = AppCardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onOpenDetails() },
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    license.code,
                    color = Color.White,
                    fontWeight = FontWeight.Bold,
                    fontSize = 16.sp,
                    modifier = Modifier.weight(1f),
                )
                StatusBadge(uiStatus)
            }
            Spacer(modifier = Modifier.height(8.dp))
            Text(license.companyName ?: "Sin asignar", color = Color.White, fontSize = 14.sp)
            Text("NIT: ${license.companyNit ?: "—"}", color = AppTextSecondary, fontSize = 13.sp)
            Spacer(modifier = Modifier.height(8.dp))

            Row(modifier = Modifier.fillMaxWidth()) {
                LicenseField("Tipo", licenseTypeLabel(license.licenseType), Modifier.weight(1f))
                LicenseField("Días restantes", license.daysRemainingLabel(), Modifier.weight(1f))
            }
            Spacer(modifier = Modifier.height(8.dp))
            Row(modifier = Modifier.fillMaxWidth()) {
                LicenseField("Activación", formatDisplayDate(license.activatedAt), Modifier.weight(1f))
                LicenseField("Vencimiento", formatDisplayDate(license.expiresAt), Modifier.weight(1f))
            }
            Spacer(modifier = Modifier.height(8.dp))
            Text("Hardware ID: ${license.hardwareFingerprint ?: "—"}", color = AppTextMuted, fontSize = 12.sp)

            Spacer(modifier = Modifier.height(12.dp))
            HorizontalDivider(color = AppOutline)
            Spacer(modifier = Modifier.height(8.dp))

            Row(modifier = Modifier.fillMaxWidth()) {
                CardActionButton("📋", "Copiar código", Modifier.weight(1f), onClick = onCopyCode)
                CardActionButton("🔄", "Renovar", Modifier.weight(1f), onClick = onRenew)
                CardActionButton(
                    if (uiStatus == LicenseStatus.BLOCKED) "🔓" else "🔒",
                    if (uiStatus == LicenseStatus.BLOCKED) "Desbloquear" else "Bloquear",
                    Modifier.weight(1f),
                    onClick = onToggleBlock,
                )
                CardActionButton("ℹ️", "Detalles", Modifier.weight(1f), onClick = onOpenDetails)
            }
        }
    }
}

@Composable
private fun LicenseField(label: String, value: String, modifier: Modifier = Modifier) {
    Column(modifier = modifier) {
        Text(label, color = AppTextMuted, fontSize = 11.sp)
        Text(value, color = AppTextSecondary, fontSize = 13.sp)
    }
}

@Composable
private fun CardActionButton(emoji: String, label: String, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(12.dp))
            .clickable { onClick() }
            .padding(vertical = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(emoji, fontSize = 16.sp)
        Spacer(modifier = Modifier.height(2.dp))
        Text(label, color = AppTextSecondary, fontSize = 10.sp, textAlign = TextAlign.Center)
    }
}

@Composable
private fun LicenseDetailsDialog(
    license: LicensePoolEntry,
    onDismiss: () -> Unit,
    onCopyCode: () -> Unit,
    onShare: () -> Unit,
    onRenew: () -> Unit,
) {
    Dialog(onDismissRequest = onDismiss) {
        Card(
            shape = RoundedCornerShape(20.dp),
            colors = CardDefaults.cardColors(containerColor = AppCardBackground),
            elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState()),
        ) {
            Column(modifier = Modifier.padding(20.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("🔑", fontSize = 20.sp)
                    Text(
                        "Información general",
                        color = Color.White,
                        fontWeight = FontWeight.Bold,
                        fontSize = 18.sp,
                        modifier = Modifier
                            .padding(start = 8.dp)
                            .weight(1f),
                    )
                    StatusBadge(license.toUiStatus())
                }
                Spacer(modifier = Modifier.height(16.dp))

                DetailRow("Empresa", license.companyName ?: "Sin asignar")
                DetailRow("NIT", license.companyNit ?: "—")
                DetailRow("Código", license.code)
                DetailRow("Tipo de licencia", licenseTypeLabel(license.licenseType))
                DetailRow("Hardware ID", license.hardwareFingerprint ?: "—")
                DetailRow("Fecha de creación", formatDisplayDate(license.createdAt))
                DetailRow("Fecha de activación", formatDisplayDate(license.activatedAt))
                DetailRow("Fecha de vencimiento", formatDisplayDate(license.expiresAt))
                DetailRow("Última verificación", formatDisplayDateTime(license.lastVerifiedAt))
                DetailRow("Observaciones", license.notes ?: "Sin observaciones.")

                Spacer(modifier = Modifier.height(16.dp))
                HorizontalDivider(color = AppOutline)
                Spacer(modifier = Modifier.height(12.dp))

                Row(modifier = Modifier.fillMaxWidth()) {
                    CardActionButton("🔄", "Renovar licencia", Modifier.weight(1f), onClick = onRenew)
                    CardActionButton("📋", "Copiar código", Modifier.weight(1f), onClick = onCopyCode)
                    CardActionButton("💬", "Compartir WhatsApp", Modifier.weight(1f), onClick = onShare)
                    CardActionButton("✖️", "Cerrar", Modifier.weight(1f), onClick = onDismiss)
                }
            }
        }
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp),
    ) {
        Text(label, color = AppTextMuted, fontSize = 13.sp, modifier = Modifier.weight(1f))
        Text(value, color = Color.White, fontSize = 13.sp, modifier = Modifier.weight(1.2f))
    }
}
