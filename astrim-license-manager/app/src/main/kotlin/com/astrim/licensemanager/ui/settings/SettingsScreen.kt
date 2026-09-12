package com.astrim.licensemanager.ui.settings

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import android.net.Uri
import com.astrim.licensemanager.data.BackupInfo
import com.astrim.licensemanager.data.BackupManager
import com.astrim.licensemanager.data.InvalidBackupException
import com.astrim.licensemanager.data.LicensePoolRepository
import com.astrim.licensemanager.data.LicensePoolViewModel
import com.astrim.licensemanager.ui.common.AppBackground
import com.astrim.licensemanager.ui.common.AppCardBackground
import com.astrim.licensemanager.ui.common.AppOutline
import com.astrim.licensemanager.ui.common.AppTextMuted
import com.astrim.licensemanager.ui.common.AppTextSecondary
import com.astrim.licensemanager.ui.common.GradientButton
import com.astrim.licensemanager.ui.common.GradientButtonStart
import com.astrim.licensemanager.ui.common.SectionCard
import com.astrim.licensemanager.ui.common.SectionTitle
import com.astrim.licensemanager.ui.common.showToast
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** Cada fila todavía sin ninguna acción real (ver PROGRESS.md del
 * módulo) — organizadas en las 4 secciones pedidas (General, Licencias,
 * Apariencia, Soporte). El interruptor de "Animaciones" es puramente
 * visual, con estado local propio (no se conecta a ninguna preferencia
 * real todavía). La sección "Respaldo y restauración" sí es real (ver
 * `BackupManager`) — es la única con `onClick` por fila. */
private data class SettingsRowSpec(
    val emoji: String,
    val label: String,
    val subtitle: String,
    val isToggle: Boolean = false,
    val onClick: (() -> Unit)? = null,
)

private val generalRows = listOf(
    SettingsRowSpec("ℹ️", "Información de la aplicación", "ASTRIM License Manager"),
    SettingsRowSpec("🔢", "Versión", "1.0.0 (build 100)"),
    SettingsRowSpec("🔄", "Actualizaciones", "Buscar actualizaciones"),
)

private val licensingRows = listOf(
    SettingsRowSpec("⚙️", "Configuración del sistema", "Parámetros generales del pool"),
    SettingsRowSpec("🗂️", "Información del pool", "30,000 códigos totales"),
    SettingsRowSpec("📊", "Estadísticas", "Resumen de uso y consumo"),
)

private val appearanceRows = listOf(
    SettingsRowSpec("🌙", "Tema", "Oscuro"),
    SettingsRowSpec("🌐", "Idioma", "Español"),
    SettingsRowSpec("✨", "Animaciones", "Activadas", isToggle = true),
)

private val supportRows = listOf(
    SettingsRowSpec("💬", "Contactar soporte", "soporte@astrim.com"),
    SettingsRowSpec("📖", "Manual", "Guía de uso de la aplicación"),
    SettingsRowSpec("ℹ️", "Acerca de", "Versión 1.0.0 · ASTRIM License Manager"),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(viewModel: LicensePoolViewModel) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val backupManager = remember { BackupManager(context) }
    val repository = remember { LicensePoolRepository(context) }

    var isBusy by remember { mutableStateOf(false) }
    var restoreCandidate by remember { mutableStateOf<Uri?>(null) }
    var backupInfoToShow by remember { mutableStateOf<BackupInfo?>(null) }

    fun runBackupTask(startMessage: String, task: () -> BackupInfo, onSuccess: (BackupInfo) -> Unit) {
        isBusy = true
        showToast(context, startMessage)
        scope.launch(Dispatchers.IO) {
            try {
                val info = task()
                withContext(Dispatchers.Main) {
                    isBusy = false
                    onSuccess(info)
                }
            } catch (error: InvalidBackupException) {
                withContext(Dispatchers.Main) {
                    isBusy = false
                    showToast(context, error.message ?: "El respaldo no es válido.")
                }
            } catch (error: Exception) {
                withContext(Dispatchers.Main) {
                    isBusy = false
                    showToast(context, "Error al procesar el respaldo.")
                }
            }
        }
    }

    val exportLauncher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/zip")) { uri ->
        if (uri != null) {
            runBackupTask(
                startMessage = "Creando respaldo...",
                task = { backupManager.exportBackupTo(uri, repository) },
                onSuccess = { showToast(context, "Respaldo creado correctamente.") },
            )
        }
    }

    val restoreLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) restoreCandidate = uri
    }

    val infoLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            runBackupTask(
                startMessage = "Leyendo información del respaldo...",
                task = { backupManager.readBackupInfo(uri) },
                onSuccess = { backupInfoToShow = it },
            )
        }
    }

    val backupRows = listOf(
        SettingsRowSpec("💾", "Crear respaldo", "Guardar en Descargas/ASTRIM Backup") {
            runBackupTask(
                startMessage = "Creando respaldo...",
                task = { backupManager.createBackupToDownloads(repository) },
                onSuccess = { showToast(context, "Respaldo creado correctamente.") },
            )
        },
        SettingsRowSpec("♻️", "Restaurar respaldo", "Seleccionar un archivo de respaldo") {
            restoreLauncher.launch(arrayOf("application/zip", "application/octet-stream", "*/*"))
        },
        SettingsRowSpec("📤", "Exportar base de datos", "Elegir carpeta de destino") {
            exportLauncher.launch("ASTRIM_Backup.zip")
        },
        SettingsRowSpec("📥", "Importar base de datos", "Seleccionar un archivo para importar") {
            restoreLauncher.launch(arrayOf("application/zip", "application/octet-stream", "*/*"))
        },
        SettingsRowSpec("🧾", "Ver información del respaldo", "Fecha, empresas, licencias y movimientos") {
            infoLauncher.launch(arrayOf("application/zip", "application/octet-stream", "*/*"))
        },
    )

    Scaffold(
        containerColor = AppBackground,
        topBar = {
            TopAppBar(
                title = { Text("Configuración") },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = AppBackground),
            )
        },
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
        ) {
            SettingsSection(emoji = "🧩", title = "General", rows = generalRows)
            Spacer(modifier = Modifier.height(20.dp))
            SettingsSection(emoji = "🔑", title = "Licencias", rows = licensingRows)
            Spacer(modifier = Modifier.height(20.dp))
            SettingsSection(emoji = "🎨", title = "Apariencia", rows = appearanceRows)
            Spacer(modifier = Modifier.height(20.dp))
            SettingsSection(emoji = "🗄️", title = "Respaldo y restauración", rows = backupRows)
            Spacer(modifier = Modifier.height(20.dp))
            SettingsSection(emoji = "🛟", title = "Soporte", rows = supportRows)
            Spacer(modifier = Modifier.height(24.dp))
        }
    }

    if (isBusy) {
        BusyOverlay()
    }

    val pendingRestoreUri = restoreCandidate
    if (pendingRestoreUri != null) {
        ConfirmRestoreDialog(
            onDismiss = { restoreCandidate = null },
            onConfirm = {
                restoreCandidate = null
                runBackupTask(
                    startMessage = "Restaurando respaldo...",
                    task = { backupManager.restoreBackup(pendingRestoreUri) },
                    onSuccess = {
                        viewModel.reload()
                        showToast(context, "Restauración completada.")
                    },
                )
            },
        )
    }

    val info = backupInfoToShow
    if (info != null) {
        BackupInfoDialog(info = info, onDismiss = { backupInfoToShow = null })
    }
}

@Composable
private fun SettingsSection(emoji: String, title: String, rows: List<SettingsRowSpec>) {
    SectionCard {
        SectionTitle(icon = null, emoji = emoji, text = title)
        Spacer(modifier = Modifier.height(12.dp))
        rows.forEachIndexed { index, row ->
            SettingsRow(row)
            if (index != rows.lastIndex) {
                Spacer(modifier = Modifier.height(4.dp))
                HorizontalDivider(color = AppOutline)
                Spacer(modifier = Modifier.height(4.dp))
            }
        }
    }
}

@Composable
private fun SettingsRow(row: SettingsRowSpec) {
    var toggled by remember { mutableStateOf(true) }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .let { base -> if (row.onClick != null) base.clickable { row.onClick.invoke() } else base }
            .padding(vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(row.emoji, fontSize = 20.sp)
        Column(modifier = Modifier.weight(1f).padding(start = 12.dp)) {
            Text(row.label, color = Color.White, fontSize = 15.sp)
            Text(row.subtitle, color = AppTextMuted, fontSize = 12.sp)
        }
        if (row.isToggle) {
            Switch(
                checked = toggled,
                onCheckedChange = { toggled = it },
                colors = SwitchDefaults.colors(
                    checkedThumbColor = Color.White,
                    checkedTrackColor = GradientButtonStart,
                    uncheckedThumbColor = AppTextSecondary,
                    uncheckedTrackColor = AppOutline,
                ),
            )
        } else {
            Icon(
                Icons.AutoMirrored.Filled.KeyboardArrowRight,
                contentDescription = null,
                tint = AppTextSecondary,
            )
        }
    }
}

@Composable
private fun BusyOverlay() {
    Dialog(onDismissRequest = {}) {
        Card(
            shape = RoundedCornerShape(20.dp),
            colors = CardDefaults.cardColors(containerColor = AppCardBackground),
            elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
        ) {
            Row(
                modifier = Modifier.padding(24.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                CircularProgressIndicator(color = GradientButtonStart, strokeWidth = 3.dp)
                Text(
                    "Procesando...",
                    color = Color.White,
                    fontSize = 15.sp,
                    modifier = Modifier.padding(start = 16.dp),
                )
            }
        }
    }
}

@Composable
private fun ConfirmRestoreDialog(onDismiss: () -> Unit, onConfirm: () -> Unit) {
    Dialog(onDismissRequest = onDismiss) {
        Card(
            shape = RoundedCornerShape(20.dp),
            colors = CardDefaults.cardColors(containerColor = AppCardBackground),
            elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
        ) {
            Column(modifier = Modifier.padding(20.dp)) {
                Text(
                    "Restaurar respaldo",
                    color = Color.White,
                    fontWeight = FontWeight.Bold,
                    fontSize = 18.sp,
                )
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    "Esta acción reemplazará toda la información actual (licencias, empresas e " +
                        "historial) con la del respaldo seleccionado. Esta acción no se puede deshacer.",
                    color = AppTextSecondary,
                    fontSize = 14.sp,
                )
                Spacer(modifier = Modifier.height(20.dp))
                Row(modifier = Modifier.fillMaxWidth()) {
                    GradientButton(
                        text = "Cancelar",
                        onClick = onDismiss,
                        enabled = true,
                        modifier = Modifier.weight(1f).padding(end = 6.dp),
                        gradientStart = AppOutline,
                        gradientEnd = AppOutline,
                    )
                    GradientButton(
                        text = "Restaurar",
                        onClick = onConfirm,
                        enabled = true,
                        modifier = Modifier.weight(1f).padding(start = 6.dp),
                    )
                }
            }
        }
    }
}

@Composable
private fun BackupInfoDialog(info: BackupInfo, onDismiss: () -> Unit) {
    Dialog(onDismissRequest = onDismiss) {
        Card(
            shape = RoundedCornerShape(20.dp),
            colors = CardDefaults.cardColors(containerColor = AppCardBackground),
            elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
        ) {
            Column(modifier = Modifier.padding(20.dp)) {
                Text(
                    "Información del respaldo",
                    color = Color.White,
                    fontWeight = FontWeight.Bold,
                    fontSize = 18.sp,
                )
                Spacer(modifier = Modifier.height(16.dp))

                val (date, time) = splitBackupTimestamp(info.createdAt)
                BackupInfoRow("Fecha del respaldo", date)
                BackupInfoRow("Hora", time)
                BackupInfoRow("Cantidad de empresas", info.companiesCount.toString())
                BackupInfoRow("Cantidad de licencias", info.licensesTotal.toString())
                BackupInfoRow("Licencias activas", info.licensesActive.toString())
                BackupInfoRow("Licencias disponibles", info.licensesAvailable.toString())
                BackupInfoRow("Licencias vencidas", info.licensesExpired.toString())
                BackupInfoRow("Movimientos registrados", info.movementsCount.toString())
                BackupInfoRow("Versión de la aplicación", info.appVersionName)

                Spacer(modifier = Modifier.height(16.dp))
                GradientButton(
                    text = "Cerrar",
                    onClick = onDismiss,
                    enabled = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }
    }
}

@Composable
private fun BackupInfoRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp),
    ) {
        Text(label, color = AppTextMuted, fontSize = 13.sp, modifier = Modifier.weight(1f))
        Text(value, color = Color.White, fontSize = 13.sp, modifier = Modifier.weight(1f))
    }
}

private fun splitBackupTimestamp(isoDateTime: String): Pair<String, String> {
    val parts = isoDateTime.split("T")
    val date = parts.getOrNull(0)?.let { raw ->
        val (year, month, day) = raw.split("-")
        "$day/$month/$year"
    } ?: "—"
    val time = parts.getOrNull(1)?.take(8) ?: "—"
    return date to time
}
