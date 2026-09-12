package com.astrim.licensemanager.ui.search

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
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.HorizontalDivider
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
import com.astrim.licensemanager.data.LicenseDisplayStatus
import com.astrim.licensemanager.data.LicensePoolEntry
import com.astrim.licensemanager.data.LicensePoolViewModel
import com.astrim.licensemanager.data.daysRemainingLabel
import com.astrim.licensemanager.data.displayStatus
import com.astrim.licensemanager.data.formatDisplayDate
import com.astrim.licensemanager.data.licenseTypeLabel
import com.astrim.licensemanager.data.movementActionLabel
import com.astrim.licensemanager.ui.common.AppBackground
import com.astrim.licensemanager.ui.common.AppCardBackground
import com.astrim.licensemanager.ui.common.AppOutline
import com.astrim.licensemanager.ui.common.AppTextMuted
import com.astrim.licensemanager.ui.common.AppTextSecondary
import com.astrim.licensemanager.ui.common.DarkOutlinedField
import com.astrim.licensemanager.ui.common.GradientButtonStart
import com.astrim.licensemanager.ui.common.SectionTitle
import com.astrim.licensemanager.ui.common.copyToClipboard
import com.astrim.licensemanager.ui.common.shareLicenseText
import com.astrim.licensemanager.ui.common.showToast

private data class RecentSearch(val companyName: String, val searchType: String, val date: String)

private val recentSearches = listOf(
    RecentSearch("Ferretería Central", "Empresa", "23/07/2026"),
    RecentSearch("ASTR-3KQP-7XLD-M4RT", "Código de licencia", "22/07/2026"),
    RecentSearch("HW-77AC-330F-9921", "Hardware ID", "21/07/2026"),
    RecentSearch("Distribuidora La Economía", "Empresa", "20/07/2026"),
    RecentSearch("900.456.789-1", "NIT", "19/07/2026"),
)

private val quickFilters = listOf(
    "Todos", "Empresas", "Licencias", "Hardware ID", "Activas", "Vencidas", "Bloqueadas",
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SearchScreen(viewModel: LicensePoolViewModel) {
    val context = LocalContext.current
    val assignedEntries by viewModel.assignedEntries.collectAsStateWithLifecycle()
    val movementLog by viewModel.movementLog.collectAsStateWithLifecycle()

    var searchQuery by remember { mutableStateOf("") }
    var selectedFilter by remember { mutableStateOf("Todos") }
    var selectedResult by remember { mutableStateOf<LicensePoolEntry?>(null) }

    val results = remember(assignedEntries, searchQuery, selectedFilter) {
        assignedEntries.filter { entry ->
            val matchesSearch = searchQuery.isBlank() || when (selectedFilter) {
                "Empresas" -> entry.companyName.orEmpty().contains(searchQuery, ignoreCase = true) ||
                    entry.companyNit.orEmpty().contains(searchQuery, ignoreCase = true)
                "Licencias" -> entry.code.contains(searchQuery, ignoreCase = true)
                "Hardware ID" -> entry.hardwareFingerprint.orEmpty().contains(searchQuery, ignoreCase = true)
                else -> entry.companyName.orEmpty().contains(searchQuery, ignoreCase = true) ||
                    entry.companyNit.orEmpty().contains(searchQuery, ignoreCase = true) ||
                    entry.code.contains(searchQuery, ignoreCase = true) ||
                    entry.hardwareFingerprint.orEmpty().contains(searchQuery, ignoreCase = true)
            }
            val matchesFilter = when (selectedFilter) {
                "Activas" -> entry.displayStatus() == LicenseDisplayStatus.ACTIVE ||
                    entry.displayStatus() == LicenseDisplayStatus.UPCOMING_EXPIRATION
                "Vencidas" -> entry.displayStatus() == LicenseDisplayStatus.EXPIRED
                "Bloqueadas" -> entry.displayStatus() == LicenseDisplayStatus.BLOCKED
                else -> true
            }
            matchesSearch && matchesFilter
        }
    }

    fun renew(entry: LicensePoolEntry) {
        if (entry.status == "BLOCKED") {
            showToast(context, "Desbloquéala antes de renovarla.")
        } else {
            val updated = viewModel.renewLicense(entry)
            if (selectedResult?.id == entry.id) selectedResult = updated
            showToast(context, "Licencia renovada correctamente.")
        }
    }

    fun share(entry: LicensePoolEntry) {
        shareLicenseText(
            context,
            "Licencia ASTRIM\nEmpresa: ${entry.companyName}\nCódigo: ${entry.code}\n" +
                "Vence: ${formatDisplayDate(entry.expiresAt)}",
        )
    }

    fun copyCode(code: String) {
        copyToClipboard(context, "Código de licencia", code)
        showToast(context, "Código copiado: $code")
    }

    Scaffold(
        containerColor = AppBackground,
        topBar = {
            TopAppBar(
                title = { Text("Buscar") },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = AppBackground),
            )
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
                "Encuentra rápidamente empresas, licencias y dispositivos registrados.",
                color = AppTextSecondary,
                fontSize = 14.sp,
            )
            Spacer(modifier = Modifier.height(16.dp))

            SearchBarRow(searchQuery, onQueryChange = { searchQuery = it })
            Spacer(modifier = Modifier.height(16.dp))

            QuickFiltersRow(selectedFilter, onFilterSelected = { selectedFilter = it })
            Spacer(modifier = Modifier.height(20.dp))

            SectionTitle(icon = null, emoji = "🕓", text = "Búsquedas recientes")
            Spacer(modifier = Modifier.height(10.dp))
            RecentSearchesList()
            Spacer(modifier = Modifier.height(20.dp))

            SectionTitle(icon = null, emoji = "📄", text = "Resultados")
            Spacer(modifier = Modifier.height(10.dp))
            if (results.isEmpty()) {
                Text(
                    "No se encontraron resultados para esta búsqueda.",
                    color = AppTextMuted,
                    fontSize = 13.sp,
                )
            }
            results.forEach { result ->
                SearchResultCard(
                    result = result,
                    onOpenDetails = { selectedResult = result },
                    onCopyCode = { copyCode(result.code) },
                    onShare = { share(result) },
                    onRenew = { renew(result) },
                )
                Spacer(modifier = Modifier.height(12.dp))
            }
            Spacer(modifier = Modifier.height(24.dp))
        }
    }

    val detailsResult = selectedResult
    if (detailsResult != null) {
        val history = movementLog.filter { it.code == detailsResult.code }
        SearchResultDetailsDialog(
            result = detailsResult,
            history = history,
            onDismiss = { selectedResult = null },
            onCopyCode = { copyCode(detailsResult.code) },
            onShare = { share(detailsResult) },
            onRenew = { renew(detailsResult) },
        )
    }
}

@Composable
private fun SearchBarRow(query: String, onQueryChange: (String) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        DarkOutlinedField(
            value = query,
            onValueChange = onQueryChange,
            label = "Buscar por empresa, NIT, código o Hardware ID...",
            modifier = Modifier.weight(1f),
        )
        Spacer(modifier = Modifier.width(8.dp))
        Box(
            modifier = Modifier
                .size(56.dp)
                .clip(RoundedCornerShape(16.dp))
                .background(GradientButtonStart),
            contentAlignment = Alignment.Center,
        ) {
            Text("🔍", fontSize = 20.sp)
        }
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
private fun RecentSearchesList() {
    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = AppCardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(vertical = 4.dp)) {
            recentSearches.forEachIndexed { index, recent ->
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("🕓", fontSize = 16.sp)
                    Column(modifier = Modifier.weight(1f).padding(start = 12.dp)) {
                        Text(recent.companyName, color = Color.White, fontSize = 14.sp)
                        Text(recent.searchType, color = AppTextMuted, fontSize = 12.sp)
                    }
                    Text(recent.date, color = AppTextMuted, fontSize = 12.sp)
                }
                if (index != recentSearches.lastIndex) {
                    HorizontalDivider(color = AppOutline)
                }
            }
        }
    }
}

@Composable
private fun StatusBadge(status: LicenseDisplayStatus) {
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
private fun SearchResultCard(
    result: LicensePoolEntry,
    onOpenDetails: () -> Unit,
    onCopyCode: () -> Unit,
    onShare: () -> Unit,
    onRenew: () -> Unit,
) {
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
                    result.companyName ?: "Sin asignar",
                    color = Color.White,
                    fontWeight = FontWeight.Bold,
                    fontSize = 16.sp,
                    modifier = Modifier.weight(1f),
                )
                StatusBadge(result.displayStatus())
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text("NIT: ${result.companyNit ?: "—"}", color = AppTextSecondary, fontSize = 13.sp)
            Text(result.code, color = AppTextSecondary, fontSize = 13.sp)
            Spacer(modifier = Modifier.height(8.dp))

            Row(modifier = Modifier.fillMaxWidth()) {
                ResultField("Tipo de licencia", licenseTypeLabel(result.licenseType), Modifier.weight(1f))
                ResultField("Días restantes", result.daysRemainingLabel(), Modifier.weight(1f))
            }
            Spacer(modifier = Modifier.height(8.dp))
            Row(modifier = Modifier.fillMaxWidth()) {
                ResultField("Hardware ID", result.hardwareFingerprint ?: "—", Modifier.weight(1f))
                ResultField("Vencimiento", formatDisplayDate(result.expiresAt), Modifier.weight(1f))
            }

            Spacer(modifier = Modifier.height(12.dp))
            HorizontalDivider(color = AppOutline)
            Spacer(modifier = Modifier.height(8.dp))

            Row(modifier = Modifier.fillMaxWidth()) {
                CardActionButton("ℹ️", "Ver detalles", Modifier.weight(1f), onClick = onOpenDetails)
                CardActionButton("📋", "Copiar código", Modifier.weight(1f), onClick = onCopyCode)
                CardActionButton("💬", "WhatsApp", Modifier.weight(1f), onClick = onShare)
                CardActionButton("🔄", "Renovar", Modifier.weight(1f), onClick = onRenew)
            }
        }
    }
}

@Composable
private fun ResultField(label: String, value: String, modifier: Modifier = Modifier) {
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
private fun SearchResultDetailsDialog(
    result: LicensePoolEntry,
    history: List<com.astrim.licensemanager.data.MovementLogEntry>,
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
                    Text("🔍", fontSize = 20.sp)
                    Text(
                        result.companyName ?: "Sin asignar",
                        color = Color.White,
                        fontWeight = FontWeight.Bold,
                        fontSize = 18.sp,
                        modifier = Modifier
                            .padding(start = 8.dp)
                            .weight(1f),
                    )
                    StatusBadge(result.displayStatus())
                }
                Spacer(modifier = Modifier.height(16.dp))

                SectionTitle(icon = null, emoji = "🏢", text = "Información de la empresa")
                Spacer(modifier = Modifier.height(8.dp))
                DetailRow("NIT", result.companyNit ?: "—")
                DetailRow("Propietario", result.ownerName ?: "—")
                DetailRow("Teléfono", "—")
                DetailRow("Correo electrónico", "—")
                DetailRow("Dirección", "—")
                DetailRow("Ciudad", "—")

                Spacer(modifier = Modifier.height(16.dp))
                SectionTitle(icon = null, emoji = "🔑", text = "Información de la licencia")
                Spacer(modifier = Modifier.height(8.dp))
                DetailRow("Código de licencia", result.code)
                DetailRow("Tipo de licencia", licenseTypeLabel(result.licenseType))
                DetailRow("Estado", result.displayStatus().label)
                DetailRow("Fecha de activación", formatDisplayDate(result.activatedAt))
                DetailRow("Fecha de vencimiento", formatDisplayDate(result.expiresAt))
                DetailRow("Días restantes", result.daysRemainingLabel())

                Spacer(modifier = Modifier.height(16.dp))
                SectionTitle(icon = null, emoji = "💻", text = "Hardware ID")
                Spacer(modifier = Modifier.height(8.dp))
                Text(result.hardwareFingerprint ?: "—", color = Color.White, fontSize = 13.sp)

                Spacer(modifier = Modifier.height(16.dp))
                SectionTitle(icon = null, emoji = "🕓", text = "Historial resumido")
                Spacer(modifier = Modifier.height(8.dp))
                if (history.isEmpty()) {
                    Text("Sin movimientos registrados todavía.", color = AppTextMuted, fontSize = 13.sp)
                }
                history.forEach { entry ->
                    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                        Text(movementActionLabel(entry.action), color = AppTextSecondary, fontSize = 13.sp, modifier = Modifier.weight(1f))
                        Text(formatDisplayDate(entry.occurredAt), color = AppTextMuted, fontSize = 13.sp)
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))
                SectionTitle(icon = null, emoji = "📝", text = "Observaciones")
                Spacer(modifier = Modifier.height(8.dp))
                Text(result.notes ?: "Sin observaciones.", color = AppTextSecondary, fontSize = 13.sp)

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
