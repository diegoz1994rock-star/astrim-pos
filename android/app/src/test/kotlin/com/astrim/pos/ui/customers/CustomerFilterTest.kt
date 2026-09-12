package com.astrim.pos.ui.customers

import com.astrim.pos.core.network.dto.CustomerDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

private fun customer(
    id: Int = 7,
    fullName: String = "Juan Pérez",
    documentId: String? = "123456",
    phone: String? = null,
    email: String? = null,
) = CustomerDto(
    id = id,
    fullName = fullName,
    documentId = documentId,
    email = email,
    phone = phone,
    address = null,
    creditLimit = "100000",
    currentDebt = "0",
    loyaltyPointsBalance = 0,
)

/** Mismo criterio de búsqueda que ya usan Catálogo/Despacho: subcadena, sin
 * distinguir mayúsculas/minúsculas — ver [matchesCustomerSearch]. */
class CustomerFilterTest {

    @Test
    fun `busqueda vacia coincide con todo`() {
        assertTrue(matchesCustomerSearch(customer(), ""))
        assertTrue(matchesCustomerSearch(customer(), "   "))
    }

    @Test
    fun `busqueda por nombre es subcadena y no distingue mayusculas`() {
        assertTrue(matchesCustomerSearch(customer(fullName = "Juan Pérez"), "juan"))
        assertTrue(matchesCustomerSearch(customer(fullName = "Juan Pérez"), "PÉREZ"))
        assertFalse(matchesCustomerSearch(customer(fullName = "Juan Pérez"), "María"))
    }

    @Test
    fun `busqueda por documento`() {
        assertTrue(matchesCustomerSearch(customer(documentId = "123456"), "1234"))
        assertFalse(matchesCustomerSearch(customer(documentId = "123456"), "999"))
    }

    @Test
    fun `busqueda por documento nulo no rompe`() {
        assertFalse(matchesCustomerSearch(customer(documentId = null), "1234"))
    }

    @Test
    fun `busqueda por telefono y correo`() {
        assertTrue(matchesCustomerSearch(customer(phone = "3001234567"), "3001234567"))
        assertTrue(matchesCustomerSearch(customer(email = "juan@example.com"), "juan@example"))
    }

    @Test
    fun `filterCustomers devuelve solo los que coinciden`() {
        val juan = customer(id = 1, fullName = "Juan Pérez")
        val maria = customer(id = 2, fullName = "María Gómez")

        val result = filterCustomers(listOf(juan, maria), "juan")

        assertEquals(listOf(juan), result)
    }
}
