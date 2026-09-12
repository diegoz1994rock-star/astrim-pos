package com.astrim.licensemanager.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.astrim.licensemanager.data.LicensePoolViewModel
import com.astrim.licensemanager.ui.common.AppBackground
import com.astrim.licensemanager.ui.common.AppCardBackground
import com.astrim.licensemanager.ui.common.AppTextSecondary
import com.astrim.licensemanager.ui.common.GradientButtonStart
import com.astrim.licensemanager.ui.navigation.LicenseManagerNavHost
import com.astrim.licensemanager.ui.navigation.licenseManagerDestinations

/**
 * Raíz de la UI: barra de navegación inferior con los 6 módulos +
 * [LicenseManagerNavHost]. Sin pantalla de login (esta primera fase no
 * tiene sesión/seguridad, ver PROGRESS.md del módulo) — arranca
 * directamente en el Dashboard.
 */
@Composable
fun LicenseManagerApp() {
    val navController = rememberNavController()
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route
    val licensePoolViewModel: LicensePoolViewModel = viewModel()

    Scaffold(
        containerColor = AppBackground,
        bottomBar = {
            NavigationBar(containerColor = AppCardBackground) {
                licenseManagerDestinations.forEach { destination ->
                    NavigationBarItem(
                        selected = currentRoute == destination.route,
                        onClick = {
                            navController.navigate(destination.route) {
                                popUpTo(navController.graph.startDestinationId) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = {
                            if (destination.icon != null) {
                                Icon(destination.icon, contentDescription = destination.label)
                            } else {
                                Text(destination.emoji.orEmpty())
                            }
                        },
                        label = {
                            Text(
                                destination.label,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                                style = TextStyle(fontSize = 11.sp),
                            )
                        },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = GradientButtonStart,
                            selectedTextColor = GradientButtonStart,
                            unselectedIconColor = AppTextSecondary,
                            unselectedTextColor = AppTextSecondary,
                            indicatorColor = AppBackground,
                        ),
                    )
                }
            }
        },
    ) { paddingValues ->
        Box(modifier = Modifier.padding(paddingValues)) {
            LicenseManagerNavHost(navController, licensePoolViewModel)
        }
    }
}
