package com.astrim.pos.core.session

import com.astrim.pos.core.network.dto.SessionInfoDto

/**
 * Código de permiso que gobierna cada módulo — mismos códigos que
 * `_build_nav_panels` del escritorio (`main.py`), para que el menú de
 * Android y la protección de cada pantalla repliquen exactamente qué ve
 * cada cargo en el sidebar del escritorio. Un módulo nuevo agrega una
 * línea acá con el mismo `permission_code` que su `NavPanel` en el
 * escritorio — nunca uno inventado.
 */
object ModulePermissions {
    const val SALES = "sales.create"
    const val CATALOG = "products.manage"
    const val DISPATCH = "kitchen.manage"
    const val CUSTOMERS = "customers.manage"
    const val CASH_REGISTER = "cash_register.manage"
    const val VENDOR = "restaurant.manage"
}

/**
 * Réplica exacta de `_panel_visible` del escritorio (`main.py`), sin el
 * filtro de `business_types` porque ningún módulo de Android lo usa
 * todavía: Administrador General ve todo sin restricción de permiso,
 * cualquier otro cargo solo lo que su lista de permisos autoriza.
 *
 * Se usa en dos capas independientes (ver `HomeScreen`/`AstrimNavHost`):
 * primero para no dibujar el botón de un módulo sin permiso, y de nuevo al
 * entrar a la ruta del módulo — así un acceso directo a la ruta (código
 * futuro con un deep link, o un bug que la muestre igual) queda bloqueado
 * aunque el botón nunca haya existido.
 */
fun hasModuleAccess(session: SessionInfoDto, permissionCode: String): Boolean =
    session.isAdmin || permissionCode in session.permissionCodes
