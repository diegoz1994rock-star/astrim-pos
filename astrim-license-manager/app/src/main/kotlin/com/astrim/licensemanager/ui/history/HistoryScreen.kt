package com.astrim.licensemanager.ui.history

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
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
import com.astrim.licensemanager.data.LicensePoolViewModel
import com.astrim.licensemanager.data.MovementLogEntry
import com.astrim.licensemanager.data.formatDisplayDateTime
import com.astrim.licensemanager.data.licenseTypeLabel
import com.astrim.licensemanager.data.movementActionColor
import com.astrim.licensemanager.data.movementActionLabel
import com.astrim.licensemanager.ui.common.AppBackground
import com.astrim.licensemanager.ui.common.AppCardBackground
import com.astrim.licensemanager.ui.common.AppOutline
import com.astrim.licensemanager.ui.common.AppTextMuted
import com.astrim.licensemanager.ui.common.AppTextSecondary
import com.astrim.licensemanager.ui.common.DarkOutlinedField
import com.astrim.licensemanager.ui.common.GradientButtonStart
import com.astrim.licensemanager.ui.common.KpiCard
import com.astrim.licensemanager.ui.common.copyToClipboard
import com.astrim.licensemanager.ui.common.showToast

private val historyActionFilters = listOf(
    "Todos", "Activaciones", "Renovaciones", "Bloqueos", "Desbloqueos", "Vencimientos",
)

private fun filterToAction(filter: String): String? = when (filter) {
    "Activaciones" -> "ACTIVATION"
    "Renovaciones" -> "RENEWAL"
    "Bloqueos" -> "BLOCK"
    "Desbloqueos" -> "UNBLOCK"
    "Vencimientos" -> "EXPIRATION"
    else -> null
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HistoryScreen(viewModel: LicensePoolViewModel) {
    val context = LocalContext.current
    val movementLog by viewModel.movementLog.collectAsStateWithLifecycle()

    var searchQuery by remember { mutableStateOf("") }
    var selectedFilter by remember { mutableStateOf("Todos") }
    var selectedEntry by remember { mutableStateOf<MovementLogEntry?>(null) }

    val filteredEntries = remember(movementLog, searchQuery, selectedFilter) {
        val actionFilter = filterToAction(selectedFilter)
        movementLog.filter { entry ->
            val matchesSearch = searchQuery.isBlank() ||
                entry.companyName.orEmpty().contains(searchQuery, ignoreCase = true) ||
                entry.code.contains(searchQuery, ignoreCase = true) ||
                movementActionLabel(entry.action).contains(searchQuery, ignoreCase = true)
            val matchesFilter = actionFilter == null || entry.action == actionFilter
            matchesSearch && matchesFilter
        }
    }

    val totalMovements = movementLog.size
    val activations = movementLog.count { it.action == "ACTIVATION" }
    val renewals = movementLog.count { it.action == "RENEWAL" }
    val blocks = movementLog.count { it.action == "BLOCK" }

    Scaffold(
        containerColor = AppBackground,
        topBar = {
            TopAppBar(
                title = { Text("Historial") },
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
                "Consulta todos los movimientos de licencias en ASTRIM.",
                color = AppTextSecondary,
                fontSize = 14.sp,
            )
            Spacer(modifier = Modifier.height(16.dp))

            SearchBarRow(searchQuery, onQueryChange = { searchQuery = it })
            Spacer(modifier = Modifier.height(16.dp))

            SummaryCountsRow(totalMovements, activations, renewals, blocks)
            Spacer(modifier = Modifier.height(16.dp))

            QuickFiltersRow(selectedFilter, onFilterSelected = { selectedFilter = it })
            Spacer(modifier = Modifier.height(16.dp))

            if (filteredEntries.isEmpty()) {
                Text(
                    "Aún no hay movimientos registrados. Activa, renueva o bloquea una licencia para verla aquí.",
                    color = AppTextMuted,
                    fontSize = 13.sp,
                )
            }
            filteredEntries.forEachIndexed { index, entry ->
                TimelineRow(
                    entry = entry,
                    isLast = index == filteredEntries.lastIndex,
                    onOpenDetails = { selectedEntry = entry },
                    onCopyCode = {
                        copyToClipboard(context, "Código de licencia", entry.code)
                        showToast(context, "Código copiado: ${entry.code}")
                    },
                )
            }
            Spacer(modifier = Modifier.height(24.dp))
        }
    }

    val detailsEntry = selectedEntry
    if (detailsEntry != null) {
        MovementDetailsDialog(
            entry = detailsEntry,
            onDismiss = { selectedEntry = null },
            onCopyCode = {
                copyToClipboard(context, "Código de licencia", detailsEntry.code)
                showToast(context, "Código copiado: ${detailsEntry.code}")
            },
        )
    }
}

@Composable
private fun SearchBarRow(query: String, onQueryChange: (String) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        DarkOutlinedField(
            value = query,
            onValueChange = onQueryChange,
            label = "Buscar por empresa, código o acción...",
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
private fun SummaryCountsRow(total: Int, activations: Int, renewals: Int, blocks: Int) {
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        KpiCard("Total movimientos", total.toString(), accentColor = GradientButtonStart, modifier = Modifier.weight(1f))
        KpiCard("Activaciones", activations.toString(), accentColor = movementActionColor("ACTIVATION"), modifier = Modifier.weight(1f))
        KpiCard("Renovaciones", renewals.toString(), accentColor = movementActionColor("RENEWAL"), modifier = Modifier.weight(1f))
        KpiCard("Bloqueos", blocks.toString(), accentColor = movementActionColor("BLOCK"), modifier = Modifier.weight(1f))
    }
}

@Composable
private fun QuickFiltersRow(selectedFilter: String, onFilterSelected: (String) -> Unit) {
    Row(
        modifier = Modifier.horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        historyActionFilters.forEach { filter ->
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
private fun TimelineRow(entry: MovementLogEntry, isLast: Boolean, onOpenDetails: () -> Unit, onCopyCode: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(IntrinsicSize.Min),
    ) {
        Column(
            modifier = Modifier
                .width(24.dp)
                .fillMaxHeight(),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Box(
                modifier = Modifier
                    .size(14.dp)
                    .clip(CircleShape)
                    .background(movementActionColor(entry.action)),
            )
            if (!isLast) {
                Box(
                    modifier = Modifier
                        .width(2.dp)
                        .weight(1f)
                        .background(AppOutline),
                )
            }
        }
        Spacer(modifier = Modifier.width(8.dp))
        Column(modifier = Modifier.weight(1f)) {
            Card(
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = AppCardBackground),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onOpenDetails() },
            ) {
                Column(modifier = Modifier.padding(14.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            entry.companyName ?: "Sin asignar",
                            color = Color.White,
                            fontWeight = FontWeight.Bold,
                            fontSize = 15.sp,
                            modifier = Modifier.weight(1f),
                        )
                        ActionBadge(entry.action)
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(entry.code, color = AppTextSecondary, fontSize = 12.sp)
                    Text(formatDisplayDateTime(entry.occurredAt), color = AppTextMuted, fontSize = 12.sp)

                    Spacer(modifier = Modifier.height(8.dp))
                    HorizontalDivider(color = AppOutline)
                    Spacer(modifier = Modifier.height(6.dp))
                    Row(modifier = Modifier.fillMaxWidth()) {
                        CardActionButton("ℹ️", "Ver detalles", Modifier.weight(1f), onClick = onOpenDetails)
                        CardActionButton("📋", "Copiar código", Modifier.weight(1f), onClick = onCopyCode)
                    }
                }
            }
            Spacer(modifier = Modifier.height(12.dp))
        }
    }
}

@Composable
private fun ActionBadge(action: String) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(50))
            .background(movementActionColor(action).copy(alpha = 0.18f))
            .padding(horizontal = 10.dp, vertical = 4.dp),
    ) {
        Text(movementActionLabel(action), color = movementActionColor(action), fontSize = 11.sp, fontWeight = FontWeight.Bold)
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
private fun MovementDetailsDialog(entry: MovementLogEntry, onDismiss: () -> Unit, onCopyCode: () -> Unit) {
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
                    Text("🕓", fontSize = 20.sp)
                    Text(
                        "Detalle del movimiento",
                        color = Color.White,
                        fontWeight = FontWeight.Bold,
                        fontSize = 18.sp,
                        modifier = Modifier
                            .padding(start = 8.dp)
                            .weight(1f),
                    )
                    ActionBadge(entry.action)
                }
                Spacer(modifier = Modifier.height(16.dp))

                DetailRow("Empresa", entry.companyName ?: "Sin asignar")
                DetailRow("NIT", entry.companyNit ?: "—")
                DetailRow("Código de licencia", entry.code)
                DetailRow("Tipo de licencia", licenseTypeLabel(entry.licenseType))
                DetailRow("Acción", movementActionLabel(entry.action))
                DetailRow("Fecha y hora", formatDisplayDateTime(entry.occurredAt))
                DetailRow("Realizado por", entry.performedBy)
                DetailRow("Observaciones", entry.notes ?: "Sin observaciones.")

                Spacer(modifier = Modifier.height(16.dp))
                HorizontalDivider(color = AppOutline)
                Spacer(modifier = Modifier.height(12.dp))

                Row(modifier = Modifier.fillMaxWidth()) {
                    CardActionButton("📋", "Copiar código", Modifier.weight(1f), onClick = onCopyCode)
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
