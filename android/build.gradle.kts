// Build raíz: solo declara los plugins (sin aplicarlos) para que el módulo
// :app los use con una versión consistente, resuelta una única vez acá.
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
}
