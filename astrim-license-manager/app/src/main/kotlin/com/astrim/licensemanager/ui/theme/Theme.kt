package com.astrim.licensemanager.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

// Misma identidad visual que el POS (android/app/.../ui/theme/Theme.kt) —
// los colores base de MaterialTheme son los mismos; la mayoría de las
// pantallas de esta app usan además la paleta oscura "Cristal" de
// ui/common/AppColors.kt directamente (mismo criterio que el POS: Despacho,
// Venta, Vendedor), MaterialTheme queda para lo que sí resuelve Material3
// por su cuenta (indicadores de progreso, etc.).
private val LightColors = lightColorScheme(
    primary = AstrimPrimary,
    secondary = AstrimSecondary,
    error = AstrimError,
)

private val DarkColors = darkColorScheme(
    primary = AstrimPrimaryDark,
    secondary = AstrimSecondary,
    error = AstrimError,
)

@Composable
fun AstrimTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}
