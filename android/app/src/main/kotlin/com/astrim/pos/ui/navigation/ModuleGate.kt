package com.astrim.pos.ui.navigation

import androidx.compose.runtime.Composable
import com.astrim.pos.core.network.dto.SessionInfoDto
import com.astrim.pos.core.session.hasModuleAccess
import com.astrim.pos.ui.common.AccessDeniedScreen

/**
 * Segunda capa de la misma validación que ya decide qué botones dibuja
 * [com.astrim.pos.ui.home.HomeScreen]: cada ruta de módulo en
 * [AstrimNavHost] pasa por acá antes de mostrar su pantalla real, así que
 * llegar a la ruta sin pasar por el botón del menú (navegación directa,
 * un deep link futuro, un bug) queda igual de bloqueado — nunca alcanza a
 * pedir nada a la API, que de todos modos volvería a rechazarlo
 * (`require_permission`, ver API.md).
 */
@Composable
fun ModuleGate(
    session: SessionInfoDto,
    requiredPermission: String,
    onBack: () -> Unit,
    content: @Composable () -> Unit,
) {
    if (hasModuleAccess(session, requiredPermission)) {
        content()
    } else {
        AccessDeniedScreen(onBack = onBack)
    }
}
