package com.astrim.pos.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

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
