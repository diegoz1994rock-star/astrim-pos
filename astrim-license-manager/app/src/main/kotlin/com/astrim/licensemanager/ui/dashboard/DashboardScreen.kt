package com.astrim.licensemanager.ui.dashboard

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
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
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.astrim.licensemanager.R
import com.astrim.licensemanager.data.LicensePoolViewModel
import com.astrim.licensemanager.data.MovementLogEntry
import com.astrim.licensemanager.data.daysRemaining
import com.astrim.licensemanager.data.displayStatus
import com.astrim.licensemanager.data.LicenseDisplayStatus
import com.astrim.licensemanager.data.licenseTypeLabel
import com.astrim.licensemanager.data.movementActionLabel
import com.astrim.licensemanager.data.relativeTimeLabel
import com.astrim.licensemanager.ui.common.AppBackground
import com.astrim.licensemanager.ui.common.AppOutline
import com.astrim.licensemanager.ui.common.AppTextMuted
import com.astrim.licensemanager.ui.common.AppTextSecondary
import com.astrim.licensemanager.ui.common.GradientButton
import com.astrim.licensemanager.ui.common.GradientButtonEnd
import com.astrim.licensemanager.ui.common.GradientButtonStart
import com.astrim.licensemanager.ui.common.SectionCard
import com.astrim.licensemanager.ui.common.SectionTitle
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

private data class SummaryMetric(val label: String, val value: String)

private data class LicenseTypeSummary(
    val title: String,
    val available: Int,
    val used: Int,
    val expired: Int,
    val accent: Color,
)

private fun movementEmoji(action: String): String = when (action) {
    "ACTIVATION" -> "✅"
    "RENEWAL" -> "🔄"
    "BLOCK" -> "🔒"
    "UNBLOCK" -> "🔓"
    "EXPIRATION" -> "⌛"
    else -> "•"
}

private val dateTimeFormatter: DateTimeFormatter =
    DateTimeFormatter.ofPattern("EEEE d 'de' MMMM 'de' yyyy · h:mm a", Locale("es", "ES"))

private fun greetingForHour(hour: Int): String = when (hour) {
    in 0..11 -> "Buenos días"
    in 12..17 -> "Buenas tardes"
    else -> "Buenas noches"
}

@Composable
fun DashboardScreen(
    viewModel: LicensePoolViewModel,
    onNewLicenseClick: () -> Unit,
    onSearchCompanyClick: () -> Unit,
    onHistoryClick: () -> Unit,
    onSettingsClick: () -> Unit,
    onNotificationsClick: () -> Unit,
) {
    val summary by viewModel.summary.collectAsStateWithLifecycle()
    val typeBreakdown by viewModel.typeBreakdown.collectAsStateWithLifecycle()
    val assignedEntries by viewModel.assignedEntries.collectAsStateWithLifecycle()
    val movementLog by viewModel.movementLog.collectAsStateWithLifecycle()

    val summaryMetrics = listOf(
        SummaryMetric("Licencias disponibles", summary.available.toString()),
        SummaryMetric("Licencias activas", summary.active.toString()),
        SummaryMetric("Licencias vencidas", summary.expired.toString()),
        SummaryMetric("Licencias bloqueadas", summary.blocked.toString()),
        SummaryMetric("Total de empresas", summary.totalCompanies.toString()),
        SummaryMetric("Total de equipos registrados", summary.totalDevices.toString()),
    )

    val licenseTypeSummaries = listOf(
        LicenseTypeSummary(
            title = "30 días",
            available = typeBreakdown["TRIAL"]?.get("AVAILABLE") ?: 0,
            used = typeBreakdown["TRIAL"]?.get("ACTIVATED") ?: 0,
            expired = typeBreakdown["TRIAL"]?.get("EXPIRED") ?: 0,
            accent = Color(0xFF4A6FA5),
        ),
        LicenseTypeSummary(
            title = "6 meses",
            available = typeBreakdown["SEMIANNUAL"]?.get("AVAILABLE") ?: 0,
            used = typeBreakdown["SEMIANNUAL"]?.get("ACTIVATED") ?: 0,
            expired = typeBreakdown["SEMIANNUAL"]?.get("EXPIRED") ?: 0,
            accent = Color(0xFF6E8FC2),
        ),
        LicenseTypeSummary(
            title = "1 año",
            available = typeBreakdown["ANNUAL"]?.get("AVAILABLE") ?: 0,
            used = typeBreakdown["ANNUAL"]?.get("ACTIVATED") ?: 0,
            expired = typeBreakdown["ANNUAL"]?.get("EXPIRED") ?: 0,
            accent = Color(0xFF64B5F6),
        ),
    )

    val recentActivities = movementLog.take(3)

    val upcomingExpirations = assignedEntries
        .filter { it.displayStatus() == LicenseDisplayStatus.ACTIVE || it.displayStatus() == LicenseDisplayStatus.UPCOMING_EXPIRATION }
        .mapNotNull { entry -> entry.daysRemaining()?.let { entry to it } }
        .sortedBy { it.second }
        .take(3)

    Scaffold(containerColor = AppBackground) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 20.dp),
            verticalArrangement = Arrangement.spacedBy(28.dp),
        ) {
            DashboardHeader(onNotificationsClick = onNotificationsClick)
            SummaryCard(summaryMetrics)
            LicenseTypesSection(licenseTypeSummaries)
            RecentActivitySection(recentActivities)
            UpcomingExpirationsSection(upcomingExpirations.map { (entry, days) ->
                UpcomingExpirationRow(entry.companyName ?: "Sin asignar", licenseTypeLabel(entry.licenseType), days)
            })
            QuickActionsSection(
                onNewLicenseClick = onNewLicenseClick,
                onSearchCompanyClick = onSearchCompanyClick,
                onHistoryClick = onHistoryClick,
                onSettingsClick = onSettingsClick,
            )
        }
    }
}

@Composable
private fun DashboardHeader(onNotificationsClick: () -> Unit) {
    val now = remember { LocalDateTime.now() }
    Column {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Image(
                painter = painterResource(R.drawable.brand_logo),
                contentDescription = "ASTRIM",
                modifier = Modifier.size(44.dp),
            )
            Spacer(modifier = Modifier.width(12.dp))
            Text(
                "ASTRIM License Manager",
                color = Color.White,
                fontWeight = FontWeight.Bold,
                fontSize = 20.sp,
                modifier = Modifier.weight(1f),
            )
            IconButton(onClick = onNotificationsClick) {
                Text("🔔", fontSize = 20.sp)
            }
        }
        Spacer(modifier = Modifier.height(14.dp))
        Text(
            text = now.format(dateTimeFormatter).replaceFirstChar { it.uppercase() },
            color = AppTextSecondary,
            fontSize = 13.sp,
        )
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = "${greetingForHour(now.hour)}.",
            color = Color.White,
            fontWeight = FontWeight.SemiBold,
            fontSize = 17.sp,
        )
    }
}

@Composable
private fun SummaryCard(summaryMetrics: List<SummaryMetric>) {
    SectionCard {
        SectionTitle(icon = null, emoji = "📊", text = "Resumen general")
        Spacer(modifier = Modifier.height(18.dp))
        summaryMetrics.chunked(2).forEach { rowMetrics ->
            Row(modifier = Modifier.fillMaxWidth()) {
                rowMetrics.forEach { metric ->
                    Column(modifier = Modifier.weight(1f)) {
                        Text(metric.value, color = Color.White, fontWeight = FontWeight.Bold, fontSize = 24.sp)
                        Text(metric.label, color = AppTextSecondary, fontSize = 12.sp)
                    }
                }
            }
            Spacer(modifier = Modifier.height(16.dp))
        }
    }
}

@Composable
private fun LicenseTypesSection(licenseTypeSummaries: List<LicenseTypeSummary>) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SectionTitle(icon = null, emoji = "🗂️", text = "Licencias por tipo")
        licenseTypeSummaries.forEach { summary -> LicenseTypeCard(summary) }
    }
}

@Composable
private fun LicenseTypeCard(summary: LicenseTypeSummary) {
    val total = (summary.available + summary.used + summary.expired).coerceAtLeast(1)
    val targetFraction = (summary.used + summary.expired).toFloat() / total
    val animatedFraction by animateFloatAsState(
        targetValue = targetFraction,
        animationSpec = tween(durationMillis = 900),
        label = "licenseTypeProgress",
    )

    SectionCard {
        Text(summary.title, color = Color.White, fontWeight = FontWeight.Bold, fontSize = 17.sp)
        Spacer(modifier = Modifier.height(14.dp))
        Row(modifier = Modifier.fillMaxWidth()) {
            LicenseTypeStat("Disponible", summary.available.toString(), Modifier.weight(1f))
            LicenseTypeStat("Usada", summary.used.toString(), Modifier.weight(1f))
            LicenseTypeStat("Vencida", summary.expired.toString(), Modifier.weight(1f))
        }
        Spacer(modifier = Modifier.height(14.dp))
        LinearProgressIndicator(
            progress = { animatedFraction },
            modifier = Modifier
                .fillMaxWidth()
                .height(8.dp)
                .clip(RoundedCornerShape(4.dp)),
            color = summary.accent,
            trackColor = AppOutline,
        )
    }
}

@Composable
private fun LicenseTypeStat(label: String, value: String, modifier: Modifier = Modifier) {
    Column(modifier = modifier) {
        Text(value, color = Color.White, fontWeight = FontWeight.Bold, fontSize = 19.sp)
        Text(label, color = AppTextMuted, fontSize = 11.sp)
    }
}

@Composable
private fun RecentActivitySection(recentActivities: List<MovementLogEntry>) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SectionTitle(icon = null, emoji = "🕓", text = "Actividad reciente")
        SectionCard {
            if (recentActivities.isEmpty()) {
                Text("Aún no hay actividad registrada.", color = AppTextMuted, fontSize = 13.sp)
            }
            recentActivities.forEachIndexed { index, activity ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(movementEmoji(activity.action), fontSize = 18.sp)
                    Column(modifier = Modifier.weight(1f).padding(start = 12.dp)) {
                        Text(
                            activity.companyName ?: "Sin asignar",
                            color = Color.White,
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 14.sp,
                        )
                        Text(movementActionLabel(activity.action), color = AppTextSecondary, fontSize = 12.sp)
                    }
                    Text(relativeTimeLabel(activity.occurredAt), color = AppTextMuted, fontSize = 11.sp)
                }
                if (index != recentActivities.lastIndex) {
                    HorizontalDivider(color = AppOutline, modifier = Modifier.padding(vertical = 10.dp))
                }
            }
        }
    }
}

private data class UpcomingExpirationRow(val companyName: String, val licenseType: String, val daysRemaining: Long)

private fun expirationColor(daysRemaining: Long): Color = when {
    daysRemaining < 7 -> Color(0xFFE57373)
    daysRemaining < 30 -> Color(0xFFFFD54F)
    else -> Color(0xFF81C784)
}

@Composable
private fun UpcomingExpirationsSection(upcomingExpirations: List<UpcomingExpirationRow>) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SectionTitle(icon = null, emoji = "⏳", text = "Próximos vencimientos")
        SectionCard {
            if (upcomingExpirations.isEmpty()) {
                Text("No hay licencias por vencer todavía.", color = AppTextMuted, fontSize = 13.sp)
            }
            upcomingExpirations.forEachIndexed { index, item ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(item.companyName, color = Color.White, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                        Text(item.licenseType, color = AppTextSecondary, fontSize = 12.sp)
                    }
                    val color = expirationColor(item.daysRemaining)
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(12.dp))
                            .background(color.copy(alpha = 0.18f))
                            .padding(horizontal = 10.dp, vertical = 4.dp),
                    ) {
                        Text(
                            "${item.daysRemaining} días",
                            color = color,
                            fontWeight = FontWeight.Bold,
                            fontSize = 12.sp,
                        )
                    }
                }
                if (index != upcomingExpirations.lastIndex) {
                    HorizontalDivider(color = AppOutline, modifier = Modifier.padding(vertical = 10.dp))
                }
            }
        }
    }
}

@Composable
private fun QuickActionsSection(
    onNewLicenseClick: () -> Unit,
    onSearchCompanyClick: () -> Unit,
    onHistoryClick: () -> Unit,
    onSettingsClick: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SectionTitle(icon = null, emoji = "⚡", text = "Acciones rápidas")
        Row(modifier = Modifier.fillMaxWidth()) {
            GradientButton(
                text = "Nueva licencia",
                onClick = onNewLicenseClick,
                enabled = true,
                modifier = Modifier.weight(1f).padding(end = 6.dp),
            )
            GradientButton(
                text = "Buscar empresa",
                onClick = onSearchCompanyClick,
                enabled = true,
                modifier = Modifier.weight(1f).padding(start = 6.dp),
                gradientStart = GradientButtonEnd,
                gradientEnd = GradientButtonStart,
            )
        }
        Row(modifier = Modifier.fillMaxWidth()) {
            GradientButton(
                text = "Historial",
                onClick = onHistoryClick,
                enabled = true,
                modifier = Modifier.weight(1f).padding(end = 6.dp),
                gradientStart = GradientButtonEnd,
                gradientEnd = GradientButtonStart,
            )
            GradientButton(
                text = "Configuración",
                onClick = onSettingsClick,
                enabled = true,
                modifier = Modifier.weight(1f).padding(start = 6.dp),
            )
        }
    }
}
