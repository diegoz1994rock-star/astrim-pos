package com.astrim.pos.core

import androidx.compose.runtime.staticCompositionLocalOf

/** Punto de acceso a [AppContainer] desde cualquier composable — provisto
 * una única vez en `MainActivity`, ver `ui/AstrimApp.kt`. */
val LocalAppContainer = staticCompositionLocalOf<AppContainer> {
    error(
        "AppContainer no fue provisto — envolvé el árbol de composables con " +
            "CompositionLocalProvider(LocalAppContainer provides ...).",
    )
}
