package com.astrim.pos.ui.dispatch

import com.astrim.pos.core.network.dto.DispatchOrderCardDto
import com.astrim.pos.core.network.dto.DispatchOrderItemDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

private fun card(
    orderId: Int = 12,
    origin: String = "vendedor",
    customerName: String = "Juan Pérez",
    customerDocument: String? = null,
    isPaid: Boolean = false,
    cajaName: String? = null,
    dispatchStatus: String = "pending",
    createdByUserName: String? = "Diego Gutiérrez",
    dispatchedByUserName: String? = null,
) = DispatchOrderCardDto(
    orderId = orderId,
    origin = origin,
    customerName = customerName,
    customerDocument = customerDocument,
    isPaid = isPaid,
    cajaName = cajaName,
    dispatchStatus = dispatchStatus,
    itemCount = 1,
    totalUnits = 2,
    items = listOf(
        DispatchOrderItemDto(
            id = 30, orderId = orderId, productId = 5, productName = "Coca-Cola 400ml",
            quantity = 2, notes = null, status = dispatchStatus, productImagePath = null,
        ),
    ),
    createdAt = null,
    createdByUserName = createdByUserName,
    dispatchedByUserName = dispatchedByUserName,
    saleId = null,
)

/** Mismos casos que `kitchen_view.py::_matches_filter`/`_matches_search`
 * (escritorio), para que Android filtre exactamente igual. */
class DispatchFilterTest {

    @Test
    fun `Todos incluye cualquier estado`() {
        assertTrue(matchesDispatchFilter(card(dispatchStatus = "delivered"), DispatchFilter.ALL))
    }

    @Test
    fun `Pendientes solo coincide con pending`() {
        assertTrue(matchesDispatchFilter(card(dispatchStatus = "pending"), DispatchFilter.PENDING))
        assertFalse(matchesDispatchFilter(card(dispatchStatus = "preparing"), DispatchFilter.PENDING))
    }

    @Test
    fun `En preparacion incluye preparing y ready`() {
        assertTrue(matchesDispatchFilter(card(dispatchStatus = "preparing"), DispatchFilter.PREPARING))
        assertTrue(matchesDispatchFilter(card(dispatchStatus = "ready"), DispatchFilter.PREPARING))
        assertFalse(matchesDispatchFilter(card(dispatchStatus = "pending"), DispatchFilter.PREPARING))
    }

    @Test
    fun `Pagados y No pagados usan is_paid`() {
        assertTrue(matchesDispatchFilter(card(isPaid = true), DispatchFilter.PAID))
        assertFalse(matchesDispatchFilter(card(isPaid = false), DispatchFilter.PAID))
        assertTrue(matchesDispatchFilter(card(isPaid = false), DispatchFilter.UNPAID))
    }

    @Test
    fun `filtros por origen`() {
        assertTrue(matchesDispatchFilter(card(origin = "vendedor"), DispatchFilter.FROM_VENDEDOR))
        assertFalse(matchesDispatchFilter(card(origin = "ventas"), DispatchFilter.FROM_VENDEDOR))
        assertTrue(matchesDispatchFilter(card(origin = "ventas"), DispatchFilter.FROM_VENTAS))
    }

    @Test
    fun `busqueda por nombre de cliente es subcadena y no distingue mayusculas`() {
        assertTrue(matchesDispatchSearch(card(customerName = "Juan Pérez"), "juan"))
        assertFalse(matchesDispatchSearch(card(customerName = "Juan Pérez"), "María"))
    }

    @Test
    fun `busqueda por numero de pedido con formato de 6 digitos`() {
        assertTrue(matchesDispatchSearch(card(orderId = 12), "000012"))
    }

    @Test
    fun `busqueda vacia coincide con todo`() {
        assertTrue(matchesDispatchSearch(card(), ""))
    }

    @Test
    fun `busqueda por empleado que despacho`() {
        assertTrue(matchesDispatchSearch(card(dispatchedByUserName = "Ana Torres"), "ana torres"))
    }

    @Test
    fun `filterDispatchOrders combina filtro y busqueda`() {
        val pendingJuan = card(orderId = 1, dispatchStatus = "pending", customerName = "Juan")
        val pendingMaria = card(orderId = 2, dispatchStatus = "pending", customerName = "María")
        val deliveredJuan = card(orderId = 3, dispatchStatus = "delivered", customerName = "Juan")

        val result = filterDispatchOrders(
            listOf(pendingJuan, pendingMaria, deliveredJuan),
            DispatchFilter.PENDING,
            "juan",
        )

        assertEquals(listOf(pendingJuan), result)
    }

    @Test
    fun `dispatchStatusLabel traduce los estados al espanol`() {
        assertEquals("Pendiente", dispatchStatusLabel("pending"))
        assertEquals("En preparación", dispatchStatusLabel("preparing"))
        assertEquals("En preparación", dispatchStatusLabel("ready"))
        assertEquals("Entregado", dispatchStatusLabel("delivered"))
    }

    @Test
    fun `dispatchOriginLabel traduce el origen al espanol`() {
        assertEquals("Vendedor", dispatchOriginLabel("vendedor"))
        assertEquals("Ventas", dispatchOriginLabel("ventas"))
    }
}
