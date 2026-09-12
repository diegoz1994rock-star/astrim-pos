package com.astrim.pos.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.astrim.pos.core.network.dto.SessionInfoDto
import com.astrim.pos.core.session.ModulePermissions
import com.astrim.pos.ui.cashregister.CashRegisterScreen
import com.astrim.pos.ui.catalog.CatalogScreen
import com.astrim.pos.ui.customers.CustomersScreen
import com.astrim.pos.ui.dispatch.DispatchScreen
import com.astrim.pos.ui.home.HomeScreen
import com.astrim.pos.ui.sales.SalesScreen
import com.astrim.pos.ui.saleshistory.SalesHistoryScreen
import com.astrim.pos.ui.vendor.VendorScreen

/**
 * Grafo de navegación de la app ya autenticada. Cada fase futura (Ventas,
 * Despacho) agrega sus rutas acá, sin tocar el mecanismo de login/logout
 * (ver `ui/AstrimApp.kt`, que decide si este grafo se muestra en absoluto
 * según [com.astrim.pos.core.session.SessionState]).
 *
 * Cada ruta de módulo (todas menos [Routes.HOME]) pasa por [ModuleGate]
 * con el mismo `permission_code` que [HomeScreen] usa para decidir si
 * dibuja su botón — la ruta vuelve a exigir el permiso aunque se llegue a
 * ella sin pasar por ese botón (ver `ModuleGate`).
 */
@Composable
fun AstrimNavHost(session: SessionInfoDto, onLogout: () -> Unit) {
    val navController: NavHostController = rememberNavController()
    val onBack: () -> Unit = { navController.popBackStack() }
    NavHost(navController = navController, startDestination = Routes.HOME) {
        composable(Routes.HOME) {
            HomeScreen(
                session = session,
                onLogout = onLogout,
                onOpenCatalog = { navController.navigate(Routes.CATALOG) },
                onOpenSales = { navController.navigate(Routes.SALES) },
                onOpenDispatch = { navController.navigate(Routes.DISPATCH) },
                onOpenCustomers = { navController.navigate(Routes.CUSTOMERS) },
                onOpenCashRegister = { navController.navigate(Routes.CASH_REGISTER) },
                onOpenVendor = { navController.navigate(Routes.VENDOR) },
            )
        }
        composable(Routes.CATALOG) {
            ModuleGate(session, ModulePermissions.CATALOG, onBack) {
                CatalogScreen(onBack = onBack)
            }
        }
        composable(Routes.SALES) {
            ModuleGate(session, ModulePermissions.SALES, onBack) {
                SalesScreen(onBack = onBack, onOpenHistory = { navController.navigate(Routes.SALES_HISTORY) })
            }
        }
        composable(Routes.SALES_HISTORY) {
            ModuleGate(session, ModulePermissions.SALES, onBack) {
                SalesHistoryScreen(onBack = onBack)
            }
        }
        composable(Routes.DISPATCH) {
            ModuleGate(session, ModulePermissions.DISPATCH, onBack) {
                DispatchScreen(onBack = onBack)
            }
        }
        composable(Routes.CUSTOMERS) {
            ModuleGate(session, ModulePermissions.CUSTOMERS, onBack) {
                CustomersScreen(onBack = onBack)
            }
        }
        composable(Routes.CASH_REGISTER) {
            ModuleGate(session, ModulePermissions.CASH_REGISTER, onBack) {
                CashRegisterScreen(onBack = onBack)
            }
        }
        composable(Routes.VENDOR) {
            ModuleGate(session, ModulePermissions.VENDOR, onBack) {
                VendorScreen(onBack = onBack)
            }
        }
    }
}
