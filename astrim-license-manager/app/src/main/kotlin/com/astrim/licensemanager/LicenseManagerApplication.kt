package com.astrim.licensemanager

import android.app.Application

/**
 * Sin contenedor de dependencias todavía (a diferencia de la app del POS,
 * `AstrimApplication`) — esta primera fase no tiene ningún servicio real
 * que inyectar (sin red, sin base de datos, sin sesión). Se agrega cuando
 * exista algo real que construir acá.
 */
class LicenseManagerApplication : Application()
