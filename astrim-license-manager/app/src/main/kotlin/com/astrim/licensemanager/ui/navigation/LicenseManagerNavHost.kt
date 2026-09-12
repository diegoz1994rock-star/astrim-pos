package com.astrim.licensemanager.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import com.astrim.licensemanager.data.LicensePoolViewModel
import com.astrim.licensemanager.ui.companies.CompaniesScreen
import com.astrim.licensemanager.ui.dashboard.DashboardScreen
import com.astrim.licensemanager.ui.history.HistoryScreen
import com.astrim.licensemanager.ui.licenses.LicensesScreen
import com.astrim.licensemanager.ui.licenses.NewLicenseScreen
import com.astrim.licensemanager.ui.notifications.NotificationsScreen
import com.astrim.licensemanager.ui.search.SearchScreen
import com.astrim.licensemanager.ui.settings.SettingsScreen

/**
 * Grafo de navegación de los 6 módulos — sin ningún gate de sesión/permiso
 * (esta primera fase no tiene login, ver PROGRESS.md del módulo). Cada
 * pantalla es hoy una cáscara estática; la lógica real se agrega adentro
 * de cada una sin tener que tocar este archivo.
 */
@Composable
fun LicenseManagerNavHost(navController: NavHostController, viewModel: LicensePoolViewModel) {
    NavHost(navController = navController, startDestination = Routes.DASHBOARD) {
        composable(Routes.DASHBOARD) {
            DashboardScreen(
                viewModel = viewModel,
                onNewLicenseClick = { navController.navigate(Routes.NEW_LICENSE) },
                onSearchCompanyClick = { navController.navigate(Routes.SEARCH) },
                onHistoryClick = { navController.navigate(Routes.HISTORY) },
                onSettingsClick = { navController.navigate(Routes.SETTINGS) },
                onNotificationsClick = { navController.navigate(Routes.NOTIFICATIONS) },
            )
        }
        composable(Routes.LICENSES) {
            LicensesScreen(viewModel = viewModel, onNewLicenseClick = { navController.navigate(Routes.NEW_LICENSE) })
        }
        composable(Routes.NEW_LICENSE) {
            NewLicenseScreen(viewModel = viewModel, onNavigateBack = { navController.popBackStack() })
        }
        composable(Routes.COMPANIES) { CompaniesScreen(viewModel = viewModel) }
        composable(Routes.SEARCH) { SearchScreen(viewModel = viewModel) }
        composable(Routes.HISTORY) { HistoryScreen(viewModel = viewModel) }
        composable(Routes.SETTINGS) { SettingsScreen(viewModel = viewModel) }
        composable(Routes.NOTIFICATIONS) {
            NotificationsScreen(viewModel = viewModel, onNavigateBack = { navController.popBackStack() })
        }
    }
}
