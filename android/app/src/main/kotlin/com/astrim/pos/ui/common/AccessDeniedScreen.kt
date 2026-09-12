package com.astrim.pos.ui.common

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

/**
 * Segunda capa de protección de permisos (ver
 * `core/session/ModulePermissions.kt::hasModuleAccess`): se muestra en vez
 * del contenido real de un módulo cuando la ruta se alcanza sin el permiso
 * que le corresponde — nunca debería ocurrir a través del menú de Inicio
 * (que ya no dibuja el botón), pero sí protege contra un acceso directo a
 * la ruta. El backend vuelve a validar lo mismo con `require_permission`
 * (ver API.md) — esta pantalla es una capa de defensa adicional, no la
 * única.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AccessDeniedScreen(onBack: () -> Unit) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Acceso denegado") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Volver")
                    }
                },
            )
        },
    ) { paddingValues ->
        Box(
            modifier = Modifier.fillMaxSize().padding(paddingValues).padding(24.dp),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = "No tienes permiso para acceder a este módulo.",
                style = MaterialTheme.typography.bodyLarge,
            )
        }
    }
}
