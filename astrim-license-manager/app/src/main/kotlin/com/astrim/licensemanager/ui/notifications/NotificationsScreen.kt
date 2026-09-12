package com.astrim.licensemanager.ui.notifications

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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import com.astrim.licensemanager.data.MovementLogEntry
import com.astrim.licensemanager.data.daysRemaining
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
import com.astrim.licensemanager.ui.common.SectionCard
import com.astrim.licensemanager.ui.common.SectionTitle
import com.astrim.licensemanager.ui.common.showToast

private data class NotificationItem(
    val companyName: String,
    val nit: String,
    val licenseCode: String,
    val licenseType: String,
    val statusLabel: String,
    val detail: String,
    val hardwareId: String,
    val notes: String,
)

private data class NotificationSection(
    val title: String,
    val emoji: String,
    val accentColor: Color,
    val filterLabel: String,
    val items: List<NotificationItem>,
)

private fun LicensePoolEntry.toExpiryItem(detail: String, statusLabel: String): NotificationItem = NotificationItem(
    companyName = companyName ?: "Sin asignar",
    nit = companyNit ?: "—",
    licenseCode = code,
    licenseType = licenseTypeLabel(licenseType),
    statusLabel = statusLabel,
    detail = detail,
    hardwareId = hardwareFingerprint ?: "—",
    notes = notes ?: "Sin observaciones.",
)

private fun MovementLogEntry.toMovementItem(): NotificationItem = NotificationItem(
    companyName = companyName ?: "Sin asignar",
    nit = companyNit ?: "—",
    licenseCode = code,
    licenseType = licenseTypeLabel(licenseType),
    statusLabel = movementActionLabel(action),
    detail = "${movementActionLabel(action)} · ${formatDisplayDate(occurredAt)}",
    hardwareId = "—",
    notes = notes ?: "Sin observaciones.",
)

private val quickFilters = listOf(
    "Todos", "Vencen hoy", "Vencen en 7 días", "Bloqueadas", "Renovaciones", "Activaciones",
)

/**
 * Pantalla de Notificaciones — no forma parte de la barra de navegación
 * inferior (se mantiene igual, ver `licenseManagerDestinations`); se
 * accede desde el ícono 🔔 del Dashboard, con su propia ruta y botón de
 * regresar (ver `Routes.NOTIFICATIONS`).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NotificationsScreen(viewModel: LicensePoolViewModel, onNavigateBack: () -> Unit = {}) {
    val context = LocalContext.current
    val assignedEntries by viewModel.assignedEntries.collectAsStateWithLifecycle()
    val movementLog by viewModel.movementLog.collectAsStateWithLifecycle()

    var searchQuery by remember { mutableStateOf("") }
    var selectedFilter by remember { mutableStateOf("Todos") }
    var selectedItem by remember { mutableStateOf<NotificationItem?>(null) }

    val expiresTodayItems = assignedEntries
        .filter { it.status == "ACTIVATED" && it.daysRemaining() == 0L }
        .map { it.toExpiryItem("Vence hoy · ${formatDisplayDate(it.expiresAt)}", "Vence hoy") }
    val expiresSoonItems = assignedEntries
        .filter { it.status == "ACTIVATED" && (it.daysRemaining() ?: -1) in 1..7 }
        .map { it.toExpiryItem("Vence en 7 días · ${formatDisplayDate(it.expiresAt)}", "Vence en 7 días") }
    val blockedItems = assignedEntries
        .filter { it.status == "BLOCKED" }
        .map { it.toExpiryItem("Bloqueada", "Bloqueada") }
    val renewedItems = movementLog.filter { it.action == "RENEWAL" }.take(5).map { it.toMovementItem() }
    val activatedItems = movementLog.filter { it.action == "ACTIVATION" }.take(5).map { it.toMovementItem() }

    val sections = listOf(
        NotificationSection("Licencias que vencen hoy", "🔴", Color(0xFFE57373), "Vencen hoy", expiresTodayItems),
        NotificationSection("Licencias que vencen en 7 días", "🟡", Color(0xFFFFC107), "Vencen en 7 días", expiresSoonItems),
        NotificationSection("Licencias bloqueadas", "⚪", Color(0xFFB0BEC5), "Bloqueadas", blockedItems),
        NotificationSection("Últimas renovaciones", "🔵", Color(0xFF64B5F6), "Renovaciones", renewedItems),
        NotificationSection("Últimas activaciones", "🟢", Color(0xFF66BB6A), "Activaciones", activatedItems),
    )

    val visibleSections = sections
        .filter { selectedFilter == "Todos" || it.filterLabel == selectedFilter }
        .map { section ->
            if (searchQuery.isBlank()) {
                section
            } else {
                section.copy(
                    items = section.items.filter {
                        it.companyName.contains(searchQuery, ignoreCase = true) ||
                            it.licenseCode.contains(searchQuery, ignoreCase = true)
                    },
                )
            }
        }

    Scaffold(
        containerColor = AppBackground,
        topBar = {
            TopAppBar(
                title = { Text("Notificaciones") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Regresar")
                    }
                },
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
                "Mantente al tanto de vencimientos, bloqueos y renovaciones.",
                color = AppTextSecondary,
                fontSize = 14.sp,
            )
            Spacer(modifier = Modifier.height(16.dp))

            SearchBarRow(searchQuery, onQueryChange = { searchQuery = it })
            Spacer(modifier = Modifier.height(16.dp))

            QuickFiltersRow(selectedFilter, onFilterSelected = { selectedFilter = it })
            Spacer(modifier = Modifier.height(20.dp))

            visibleSections.forEach { section ->
                SectionCard {
                    SectionTitle(icon = null, emoji = section.emoji, text = section.title)
                    Spacer(modifier = Modifier.height(10.dp))
                    if (section.items.isEmpty()) {
                        Text("Sin elementos en esta categoría.", color = AppTextMuted, fontSize = 12.sp)
                    }
                    section.items.forEachIndexed { index, item ->
                        NotificationRow(item, section.accentColor, onOpenDetails = { selectedItem = item })
                        if (index != section.items.lastIndex) {
                            HorizontalDivider(color = AppOutline)
                        }
                    }
                }
                Spacer(modifier = Modifier.height(16.dp))
            }
            Spacer(modifier = Modifier.height(8.dp))
        }
    }

    val detailsItem = selectedItem
    if (detailsItem != null) {
        NotificationDetailsDialog(
            item = detailsItem,
            onDismiss = { selectedItem = null },
            onViewLicense = { showToast(context, "Búscala por su código en la pantalla Licencias.") },
        )
    }
}

@Composable
private fun SearchBarRow(query: String, onQueryChange: (String) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        DarkOutlinedField(
            value = query,
            onValueChange = onQueryChange,
            label = "Buscar por empresa o código...",
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
private fun NotificationRow(item: NotificationItem, accentColor: Color, onOpenDetails: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(IntrinsicSize.Min)
            .clickable { onOpenDetails() }
            .padding(vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .width(4.dp)
                .fillMaxHeight()
                .clip(RoundedCornerShape(2.dp))
                .background(accentColor),
        )
        Column(modifier = Modifier.weight(1f).padding(start = 12.dp)) {
            Text(item.companyName, color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Bold)
            Text(item.licenseCode, color = AppTextSecondary, fontSize = 12.sp)
        }
        Text(item.detail, color = accentColor, fontSize = 12.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun NotificationDetailsDialog(item: NotificationItem, onDismiss: () -> Unit, onViewLicense: () -> Unit) {
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
                    Text("🔔", fontSize = 20.sp)
                    Text(
                        item.companyName,
                        color = Color.White,
                        fontWeight = FontWeight.Bold,
                        fontSize = 18.sp,
                        modifier = Modifier
                            .padding(start = 8.dp)
                            .weight(1f),
                    )
                }
                Spacer(modifier = Modifier.height(16.dp))

                DetailRow("NIT", item.nit)
                DetailRow("Código de licencia", item.licenseCode)
                DetailRow("Tipo de licencia", item.licenseType)
                DetailRow("Estado", item.statusLabel)
                DetailRow("Detalle", item.detail)
                DetailRow("Hardware ID", item.hardwareId)
                DetailRow("Observaciones", item.notes)

                Spacer(modifier = Modifier.height(16.dp))
                HorizontalDivider(color = AppOutline)
                Spacer(modifier = Modifier.height(12.dp))

                Row(modifier = Modifier.fillMaxWidth()) {
                    CardActionButton("🔑", "Ver licencia", Modifier.weight(1f), onClick = onViewLicense)
                    CardActionButton("✖️", "Cerrar", Modifier.weight(1f), onClick = onDismiss)
                }
            }
        }
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
