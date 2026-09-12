package com.astrim.licensemanager.ui.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.ui.graphics.vector.ImageVector

/**
 * Los 6 módulos de la barra de navegación inferior — una única lista que
 * alimenta tanto [com.astrim.licensemanager.ui.LicenseManagerBottomBar]
 * como [LicenseManagerNavHost], para no repetir rutas/etiquetas en dos
 * lugares. `icon`/`emoji`: mismo criterio que
 * [com.astrim.licensemanager.ui.common.SectionTitle] — ícono de
 * `material-icons-core` cuando existe, emoji cuando no (para no sumar
 * `material-icons-extended` completa por un puñado de íconos sueltos).
 */
data class LicenseManagerDestination(
    val route: String,
    val label: String,
    val icon: ImageVector? = null,
    val emoji: String? = null,
)

val licenseManagerDestinations = listOf(
    LicenseManagerDestination(Routes.DASHBOARD, "Dashboard", icon = Icons.Default.Home),
    LicenseManagerDestination(Routes.LICENSES, "Licencias", emoji = "🔑"),
    LicenseManagerDestination(Routes.COMPANIES, "Empresas", emoji = "🏢"),
    LicenseManagerDestination(Routes.SEARCH, "Buscar", icon = Icons.Default.Search),
    LicenseManagerDestination(Routes.HISTORY, "Historial", emoji = "🕓"),
    LicenseManagerDestination(Routes.SETTINGS, "Configuración", icon = Icons.Default.Settings),
)
