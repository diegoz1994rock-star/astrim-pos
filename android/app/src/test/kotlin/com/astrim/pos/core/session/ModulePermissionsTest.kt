package com.astrim.pos.core.session

import com.astrim.pos.core.network.dto.SessionInfoDto
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

private fun session(isAdmin: Boolean = false, permissionCodes: List<String> = emptyList()) =
    SessionInfoDto(
        userId = 1,
        username = "cajero1",
        fullName = "Cajero de Prueba",
        isAdmin = isAdmin,
        permissionCodes = permissionCodes,
        loggedInAt = "2026-07-24T10:00:00Z",
    )

/** Mismos casos que `_panel_visible` del escritorio (`main.py`): un
 * Administrador General ve cualquier módulo sin importar sus permisos, y
 * cualquier otro cargo solo lo que su lista de permisos autoriza. */
class ModulePermissionsTest {

    @Test
    fun `administrador general tiene acceso a cualquier modulo sin importar sus permisos`() {
        assertTrue(hasModuleAccess(session(isAdmin = true), ModulePermissions.CASH_REGISTER))
        assertTrue(hasModuleAccess(session(isAdmin = true, permissionCodes = emptyList()), ModulePermissions.SALES))
    }

    @Test
    fun `un cargo sin el permiso no tiene acceso`() {
        assertFalse(hasModuleAccess(session(permissionCodes = listOf("sales.create")), ModulePermissions.CASH_REGISTER))
    }

    @Test
    fun `un cargo con el permiso exacto tiene acceso`() {
        assertTrue(hasModuleAccess(session(permissionCodes = listOf("cash_register.manage")), ModulePermissions.CASH_REGISTER))
    }

    @Test
    fun `sin ningun permiso no hay acceso a ningun modulo`() {
        assertFalse(hasModuleAccess(session(), ModulePermissions.SALES))
        assertFalse(hasModuleAccess(session(), ModulePermissions.CATALOG))
        assertFalse(hasModuleAccess(session(), ModulePermissions.DISPATCH))
        assertFalse(hasModuleAccess(session(), ModulePermissions.CUSTOMERS))
        assertFalse(hasModuleAccess(session(), ModulePermissions.CASH_REGISTER))
    }
}
