package com.astrim.pos.ui.sales

import java.math.BigDecimal
import org.junit.Assert.assertEquals
import org.junit.Test

/** Suma pura y local de los pagos ya agregados en pantalla — solo para
 * mostrarle al cajero cuánto lleva cargado; la validación real de que
 * coincida con el total de la venta la hace el backend al completar. */
class TotalPaidTest {

    @Test
    fun `sin pagos el total es cero`() {
        assertEquals(BigDecimal.ZERO, totalPaid(emptyList()))
    }

    @Test
    fun `suma varios pagos mixtos`() {
        val payments = listOf(
            PendingPayment(PaymentMethodOption.CASH, BigDecimal("2000.00")),
            PendingPayment(PaymentMethodOption.CARD, BigDecimal("1500.00")),
        )

        assertEquals(0, BigDecimal("3500.00").compareTo(totalPaid(payments)))
    }

    @Test
    fun `paymentMethodLabel traduce el valor de la API al español`() {
        assertEquals("Efectivo", paymentMethodLabel("cash"))
        assertEquals("Bre-B", paymentMethodLabel("bre_b"))
    }

    @Test
    fun `paymentMethodLabel desconocido devuelve el valor tal cual`() {
        assertEquals("transfer", paymentMethodLabel("transfer"))
    }
}
