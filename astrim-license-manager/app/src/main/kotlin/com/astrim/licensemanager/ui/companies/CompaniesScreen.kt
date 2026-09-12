package com.astrim.licensemanager.ui.companies

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import com.astrim.licensemanager.data.LicenseDisplayStatus
import com.astrim.licensemanager.data.LicensePoolEntry
import com.astrim.licensemanager.data.LicensePoolViewModel
import com.astrim.licensemanager.data.daysRemainingLabel
import com.astrim.licensemanager.data.displayStatus
import com.astrim.licensemanager.data.formatDisplayDate
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CompaniesScreen(viewModel: LicensePoolViewModel) {
    val context = LocalContext.current
    val summary by viewModel.summary.collectAsStateWithLifecycle()
    val assignedEntries by viewModel.assignedEntries.collectAsStateWithLifecycle()

    var searchQuery by remember { mutableStateOf("") }
    var selectedCompany by remember { mutableStateOf<LicensePoolEntry?>(null) }

    val filteredCompanies = remember(assignedEntries, searchQuery) {
        if (searchQuery.isBlank()) {
            assignedEntries
        } else {
            assignedEntries.filter { entry ->
                entry.companyName.orEmpty().contains(searchQuery, ignoreCase = true) ||
                    entry.companyNit.orEmpty().contains(searchQuery, ignoreCase = true) ||
                    entry.ownerName.orEmpty().contains(searchQuery, ignoreCase = true)
            }
        }
    }

    val activeCount = assignedEntries.count { it.displayStatus() == LicenseDisplayStatus.ACTIVE }
    val upcomingCount = assignedEntries.count { it.displayStatus() == LicenseDisplayStatus.UPCOMING_EXPIRATION }
    val expiredCount = assignedEntries.count { it.displayStatus() == LicenseDisplayStatus.EXPIRED }

    fun renew(entry: LicensePoolEntry) {
        if (entry.status == "BLOCKED") {
            showToast(context, "Desbloquéala antes de renovarla.")
        } else {
            val updated = viewModel.renewLicense(entry)
            if (selectedCompany?.id == entry.id) selectedCompany = updated
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

    Scaffold(
        containerColor = AppBackground,
        topBar = {
            TopAppBar(
                title = { Text("Empresas") },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = AppBackground),
            )
        },
        floatingActionButton = {
            FloatingActionButton(
                onClick = { showToast(context, "Registro manual de empresas próximamente.") },
                containerColor = GradientButtonStart,
                contentColor = Color.White,
            ) {
                Icon(Icons.Default.Add, contentDescription = "Registrar empresa")
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
                "Administra todas las empresas registradas en ASTRIM.",
                color = AppTextSecondary,
                fontSize = 14.sp,
            )
            Spacer(modifier = Modifier.height(16.dp))

            SearchBarRow(searchQuery, onQueryChange = { searchQuery = it })
            Spacer(modifier = Modifier.height(16.dp))

            SummaryCountsRow(
                totalCompanies = summary.totalCompanies,
                active = activeCount,
                upcoming = upcomingCount,
                expired = expiredCount,
            )
            Spacer(modifier = Modifier.height(20.dp))

            if (filteredCompanies.isEmpty()) {
                Text(
                    "Aún no hay empresas registradas. Entrega una licencia desde \"Nueva licencia\" para verla aquí.",
                    color = AppTextMuted,
                    fontSize = 13.sp,
                )
            }
            filteredCompanies.forEach { company ->
                CompanyCard(
                    company = company,
                    onOpenDetails = { selectedCompany = company },
                    onRenew = { renew(company) },
                    onShare = { share(company) },
                )
                Spacer(modifier = Modifier.height(12.dp))
            }
            Spacer(modifier = Modifier.height(72.dp))
        }
    }

    val detailsCompany = selectedCompany
    if (detailsCompany != null) {
        CompanyDetailsDialog(
            company = detailsCompany,
            onDismiss = { selectedCompany = null },
            onCopyCode = {
                copyToClipboard(context, "Código de licencia", detailsCompany.code)
                showToast(context, "Código copiado: ${detailsCompany.code}")
            },
            onShare = { share(detailsCompany) },
            onRenew = { renew(detailsCompany) },
        )
    }
}

@Composable
private fun SearchBarRow(query: String, onQueryChange: (String) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        DarkOutlinedField(
            value = query,
            onValueChange = onQueryChange,
            label = "Buscar por empresa, NIT o propietario...",
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
private fun SummaryCountsRow(totalCompanies: Int, active: Int, upcoming: Int, expired: Int) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            KpiCard("Total empresas", totalCompanies.toString(), accentColor = GradientButtonStart, modifier = Modifier.weight(1f))
            KpiCard("Licencias activas", active.toString(), accentColor = LicenseDisplayStatus.ACTIVE.color, modifier = Modifier.weight(1f))
        }
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            KpiCard("Próximas a vencer", upcoming.toString(), accentColor = LicenseDisplayStatus.UPCOMING_EXPIRATION.color, modifier = Modifier.weight(1f))
            KpiCard("Licencias vencidas", expired.toString(), accentColor = LicenseDisplayStatus.EXPIRED.color, modifier = Modifier.weight(1f))
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
private fun CompanyCard(
    company: LicensePoolEntry,
    onOpenDetails: () -> Unit,
    onRenew: () -> Unit,
    onShare: () -> Unit,
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
                    company.companyName ?: "Sin asignar",
                    color = Color.White,
                    fontWeight = FontWeight.Bold,
                    fontSize = 16.sp,
                    modifier = Modifier.weight(1f),
                )
                StatusBadge(company.displayStatus())
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text("NIT: ${company.companyNit ?: "—"}", color = AppTextSecondary, fontSize = 13.sp)
            Text("Propietario: ${company.ownerName ?: "—"}", color = AppTextSecondary, fontSize = 13.sp)
            Spacer(modifier = Modifier.height(8.dp))

            Row(modifier = Modifier.fillMaxWidth()) {
                CompanyField("Teléfono", "—", Modifier.weight(1f))
                CompanyField("Correo", "—", Modifier.weight(1f))
            }
            Spacer(modifier = Modifier.height(8.dp))
            Row(modifier = Modifier.fillMaxWidth()) {
                CompanyField("Tipo de licencia", licenseTypeLabel(company.licenseType), Modifier.weight(1f))
                CompanyField("Días restantes", company.daysRemainingLabel(), Modifier.weight(1f))
            }
            Spacer(modifier = Modifier.height(8.dp))
            Row(modifier = Modifier.fillMaxWidth()) {
                CompanyField("Activación", formatDisplayDate(company.activatedAt), Modifier.weight(1f))
                CompanyField("Vencimiento", formatDisplayDate(company.expiresAt), Modifier.weight(1f))
            }
            Spacer(modifier = Modifier.height(8.dp))
            Text("Hardware ID: ${company.hardwareFingerprint ?: "—"}", color = AppTextMuted, fontSize = 12.sp)

            Spacer(modifier = Modifier.height(12.dp))
            HorizontalDivider(color = AppOutline)
            Spacer(modifier = Modifier.height(8.dp))

            Row(modifier = Modifier.fillMaxWidth()) {
                CardActionButton("🔄", "Renovar", Modifier.weight(1f), onClick = onRenew)
                CardActionButton("🔑", "Ver licencia", Modifier.weight(1f), onClick = onOpenDetails)
                CardActionButton("💬", "WhatsApp", Modifier.weight(1f), onClick = onShare)
                CardActionButton("ℹ️", "Detalles", Modifier.weight(1f), onClick = onOpenDetails)
            }
        }
    }
}

@Composable
private fun CompanyField(label: String, value: String, modifier: Modifier = Modifier) {
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
private fun CompanyDetailsDialog(
    company: LicensePoolEntry,
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
                    Text("🏢", fontSize = 20.sp)
                    Text(
                        "Información general",
                        color = Color.White,
                        fontWeight = FontWeight.Bold,
                        fontSize = 18.sp,
                        modifier = Modifier
                            .padding(start = 8.dp)
                            .weight(1f),
                    )
                    StatusBadge(company.displayStatus())
                }
                Spacer(modifier = Modifier.height(16.dp))

                DetailRow("Nombre de la empresa", company.companyName ?: "Sin asignar")
                DetailRow("NIT", company.companyNit ?: "—")
                DetailRow("Propietario", company.ownerName ?: "—")
                DetailRow("Teléfono", "—")
                DetailRow("Correo electrónico", "—")
                DetailRow("Dirección", "—")
                DetailRow("Ciudad", "—")
                DetailRow("Tipo de licencia", licenseTypeLabel(company.licenseType))
                DetailRow("Código de licencia", company.code)
                DetailRow("Hardware ID", company.hardwareFingerprint ?: "—")
                DetailRow("Fecha de activación", formatDisplayDate(company.activatedAt))
                DetailRow("Fecha de vencimiento", formatDisplayDate(company.expiresAt))
                DetailRow("Días restantes", company.daysRemainingLabel())
                DetailRow("Estado", company.displayStatus().label)
                DetailRow("Observaciones", company.notes ?: "Sin observaciones.")

                Spacer(modifier = Modifier.height(16.dp))
                HorizontalDivider(color = AppOutline)
                Spacer(modifier = Modifier.height(12.dp))

                Row(modifier = Modifier.fillMaxWidth()) {
                    CardActionButton("🔄", "Renovar licencia", Modifier.weight(1f), onClick = onRenew)
                    CardActionButton("📋", "Copiar código", Modifier.weight(1f), onClick = onCopyCode)
                    CardActionButton("💬", "Enviar WhatsApp", Modifier.weight(1f), onClick = onShare)
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
