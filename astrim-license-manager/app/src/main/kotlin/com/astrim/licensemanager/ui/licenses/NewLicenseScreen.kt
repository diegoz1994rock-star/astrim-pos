package com.astrim.licensemanager.ui.licenses

import androidx.compose.foundation.BorderStroke
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
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
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.astrim.licensemanager.data.LicensePoolViewModel
import com.astrim.licensemanager.ui.common.AppBackground
import com.astrim.licensemanager.ui.common.AppCardBackground
import com.astrim.licensemanager.ui.common.AppOutline
import com.astrim.licensemanager.ui.common.AppTextMuted
import com.astrim.licensemanager.ui.common.AppTextSecondary
import com.astrim.licensemanager.ui.common.DarkOutlinedField
import com.astrim.licensemanager.ui.common.GradientButton
import com.astrim.licensemanager.ui.common.GradientButtonStart
import com.astrim.licensemanager.ui.common.SectionCard
import com.astrim.licensemanager.ui.common.SectionTitle
import com.astrim.licensemanager.ui.common.copyToClipboard
import com.astrim.licensemanager.ui.common.shareLicenseText
import com.astrim.licensemanager.ui.common.showToast

/** Las 3 duraciones que ofrece el pool de licencias — solo una puede estar
 * seleccionada a la vez (ver `NewLicenseScreen`). Sin ninguna lógica
 * todavía (ver PROGRESS.md del módulo): esta pantalla solo diseña la
 * interfaz de entrega. */
private data class LicenseTypeOption(val label: String, val emoji: String, val hint: String)

private val licenseTypeOptions = listOf(
    LicenseTypeOption("30 días", "⏳", "Ideal para pruebas cortas"),
    LicenseTypeOption("6 meses", "📆", "Buena opción semestral"),
    LicenseTypeOption("1 año", "🗓️", "Mejor precio a largo plazo"),
)

private data class AvailabilityRow(val label: String, val rawType: String)

private val availabilityRows = listOf(
    AvailabilityRow("30 días", "TRIAL"),
    AvailabilityRow("6 meses", "SEMIANNUAL"),
    AvailabilityRow("1 año", "ANNUAL"),
)

/** Primeros 8 caracteres alfanuméricos del Hardware ID que envía el
 * cliente, en mayúsculas y agrupados `XXXX-XXXX` — mismo cálculo que
 * `hardware.format_hardware_prefix` en el POS (Python), para que el
 * prefijo que antepone esta pantalla siempre coincida con el que el POS
 * recalcula al validar la licencia. */
private fun hardwarePrefixFrom(hardwareId: String): String {
    val prefix = hardwareId.filter { it.isLetterOrDigit() }.uppercase().take(8)
    return "${prefix.take(4)}-${prefix.drop(4)}"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NewLicenseScreen(viewModel: LicensePoolViewModel, onNavigateBack: () -> Unit = {}) {
    val context = LocalContext.current
    val typeBreakdown by viewModel.typeBreakdown.collectAsStateWithLifecycle()

    var hardwareId by remember { mutableStateOf("") }
    var companyName by remember { mutableStateOf("") }
    var nit by remember { mutableStateOf("") }
    var ownerName by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var notes by remember { mutableStateOf("") }
    var selectedType by remember { mutableStateOf("6 meses") }
    var generatedCode by remember { mutableStateOf<String?>(null) }

    Scaffold(
        containerColor = AppBackground,
        topBar = {
            TopAppBar(
                title = { Text("Nueva licencia") },
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
                "Asigna una licencia disponible a un nuevo cliente.",
                color = AppTextSecondary,
                fontSize = 14.sp,
            )
            Spacer(modifier = Modifier.height(20.dp))

            SectionCard {
                SectionTitle(icon = null, emoji = "🔒", text = "Hardware ID del cliente")
                Spacer(modifier = Modifier.height(12.dp))
                DarkOutlinedField(
                    value = hardwareId,
                    onValueChange = { hardwareId = it },
                    label = "Hardware ID (te lo manda el cliente por WhatsApp)",
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    "Prefijo para la licencia: ${hardwarePrefixFrom(hardwareId)}",
                    color = AppTextMuted,
                    fontSize = 12.sp,
                )
            }

            Spacer(modifier = Modifier.height(20.dp))

            SectionCard {
                SectionTitle(icon = null, emoji = "🏢", text = "Datos del cliente")
                Spacer(modifier = Modifier.height(12.dp))
                DarkOutlinedField(companyName, { companyName = it }, "Nombre de la empresa", Modifier.fillMaxWidth())
                Spacer(modifier = Modifier.height(12.dp))
                DarkOutlinedField(nit, { nit = it }, "NIT", Modifier.fillMaxWidth())
                Spacer(modifier = Modifier.height(12.dp))
                DarkOutlinedField(ownerName, { ownerName = it }, "Propietario", Modifier.fillMaxWidth())
                Spacer(modifier = Modifier.height(12.dp))
                DarkOutlinedField(
                    value = email,
                    onValueChange = { email = it },
                    label = "Correo electrónico",
                    modifier = Modifier.fillMaxWidth(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                )
                Spacer(modifier = Modifier.height(12.dp))
                DarkOutlinedField(
                    value = phone,
                    onValueChange = { phone = it },
                    label = "Teléfono",
                    modifier = Modifier.fillMaxWidth(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                )
                Spacer(modifier = Modifier.height(12.dp))
                DarkOutlinedField(notes, { notes = it }, "Observaciones", Modifier.fillMaxWidth())
            }

            Spacer(modifier = Modifier.height(20.dp))
            SectionTitle(icon = null, emoji = "🔑", text = "Tipo de licencia")
            Spacer(modifier = Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                licenseTypeOptions.forEach { option ->
                    LicenseTypeSelectableCard(
                        option = option,
                        selected = selectedType == option.label,
                        onClick = { selectedType = option.label },
                        modifier = Modifier.weight(1f),
                    )
                }
            }

            Spacer(modifier = Modifier.height(20.dp))
            SectionCard {
                SectionTitle(icon = null, emoji = "📊", text = "Licencias disponibles")
                Spacer(modifier = Modifier.height(12.dp))
                availabilityRows.forEach { row ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp),
                    ) {
                        Text(row.label, color = AppTextSecondary, fontSize = 14.sp, modifier = Modifier.weight(1f))
                        Text(
                            (typeBreakdown[row.rawType]?.get("AVAILABLE") ?: 0).toString(),
                            color = Color.White,
                            fontWeight = FontWeight.Bold,
                            fontSize = 14.sp,
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))
            GradientButton(
                text = "Generar licencia",
                onClick = {
                    val hardwarePrefix = hardwarePrefixFrom(hardwareId)
                    if (hardwareId.filter { it.isLetterOrDigit() }.length < 8) {
                        showToast(context, "Pega el Hardware ID completo que te mandó el cliente.")
                    } else if (companyName.isBlank() || nit.isBlank() || ownerName.isBlank()) {
                        showToast(context, "Completa empresa, NIT y propietario antes de generar la licencia.")
                    } else {
                        val result = viewModel.activateLicense(
                            licenseTypeLabel = selectedType,
                            companyName = companyName,
                            companyNit = nit,
                            ownerName = ownerName,
                        )
                        if (result == null) {
                            showToast(context, "No quedan códigos disponibles de ese tipo en el pool.")
                        } else {
                            generatedCode = "$hardwarePrefix-${result.code}"
                            showToast(context, "Licencia generada correctamente.")
                        }
                    }
                },
                enabled = true,
                modifier = Modifier.fillMaxWidth(),
            )

            Spacer(modifier = Modifier.height(20.dp))
            SectionCard {
                SectionTitle(icon = null, emoji = "🧾", text = "Código generado")
                Spacer(modifier = Modifier.height(12.dp))
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(12.dp))
                        .background(AppOutline)
                        .padding(vertical = 16.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        generatedCode ?: "XXXX-XXXX-ASTR-XXXX-XXXX-XXXX-XXXX",
                        color = Color.White,
                        fontWeight = FontWeight.Bold,
                        fontSize = 18.sp,
                    )
                }
                Spacer(modifier = Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                    GradientButton(
                        text = "Copiar código",
                        onClick = {
                            generatedCode?.let {
                                copyToClipboard(context, "Código de licencia", it)
                                showToast(context, "Código copiado: $it")
                            }
                        },
                        enabled = generatedCode != null,
                        modifier = Modifier.weight(1f),
                    )
                    GradientButton(
                        text = "Compartir por WhatsApp",
                        onClick = {
                            generatedCode?.let {
                                shareLicenseText(
                                    context,
                                    "Licencia ASTRIM\nCódigo: $it\nEmpresa: $companyName\nTipo: $selectedType",
                                )
                            }
                        },
                        enabled = generatedCode != null,
                        modifier = Modifier.weight(1f),
                    )
                }
            }

            Spacer(modifier = Modifier.height(20.dp))
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(AppCardBackground)
                    .padding(14.dp),
            ) {
                Text("⚠️", fontSize = 16.sp)
                Text(
                    "Una vez entregada, la licencia quedará asociada a esta empresa y no podrá " +
                        "reutilizarse.",
                    color = AppTextMuted,
                    fontSize = 12.sp,
                    modifier = Modifier.padding(start = 8.dp),
                )
            }
            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}

@Composable
private fun LicenseTypeSelectableCard(
    option: LicenseTypeOption,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (selected) GradientButtonStart.copy(alpha = 0.18f) else AppCardBackground,
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        border = BorderStroke(
            width = if (selected) 2.dp else 1.dp,
            color = if (selected) GradientButtonStart else AppOutline,
        ),
        modifier = modifier.clickable { onClick() },
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 18.dp, horizontal = 8.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(option.emoji, fontSize = 22.sp)
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                option.label,
                color = Color.White,
                fontWeight = FontWeight.Bold,
                fontSize = 14.sp,
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                option.hint,
                color = AppTextMuted,
                fontSize = 10.sp,
                textAlign = TextAlign.Center,
            )
        }
    }
}
