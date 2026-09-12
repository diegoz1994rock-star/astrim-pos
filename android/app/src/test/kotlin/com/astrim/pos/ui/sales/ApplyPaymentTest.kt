package com.astrim.pos.ui.sales

import java.math.BigDecimal
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Réplica de `sale_view.py::_on_add_payment_clicked` del escritorio —
 * corrección de un bug real: antes, Android enviaba el monto tal cual lo
 * escribía el cajero, así que pagar 100000 en efectivo sobre una venta de
 * 60000 hacía que el backend rechazara la venta ("el total de pagos no
 * coincide con el total de la venta") en vez de aplicar 60000 y mostrar
 * 40000 de vuelto.
 */
class ApplyPaymentTest {

    @Test
    fun `efectivo con sobrepago aplica solo el remanente y calcula el vuelto`() {
        val (applied, change) = applyPayment(
            method = PaymentMethodOption.CASH,
            enteredAmount = BigDecimal("100000"),
            remaining = BigDecimal("60000"),
        )

        assertEquals(0, BigDecimal("60000").compareTo(applied))
        assertEquals(0, BigDecimal("40000").compareTo(change))
    }

    @Test
    fun `efectivo sin sobrepago aplica el monto tal cual sin vuelto`() {
        val (applied, change) = applyPayment(
            method = PaymentMethodOption.CASH,
            enteredAmount = BigDecimal("60000"),
            remaining = BigDecimal("60000"),
        )

        assertEquals(0, BigDecimal("60000").compareTo(applied))
        assertEquals(0, BigDecimal.ZERO.compareTo(change))
    }

    @Test
    fun `efectivo con pago parcial menor al remanente aplica el monto tal cual`() {
        val (applied, change) = applyPayment(
            method = PaymentMethodOption.CASH,
            enteredAmount = BigDecimal("20000"),
            remaining = BigDecimal("60000"),
        )

        assertEquals(0, BigDecimal("20000").compareTo(applied))
        assertEquals(0, BigDecimal.ZERO.compareTo(change))
    }

    @Test
    fun `metodo distinto de efectivo con sobrepago se recorta al remanente sin vuelto`() {
        val (applied, change) = applyPayment(
            method = PaymentMethodOption.QR,
            enteredAmount = BigDecimal("100000"),
            remaining = BigDecimal("60000"),
        )

        assertEquals(0, BigDecimal("60000").compareTo(applied))
        assertEquals(0, BigDecimal.ZERO.compareTo(change))
    }

    @Test
    fun `sin nada pendiente por cobrar el monto se aplica tal cual`() {
        val (applied, change) = applyPayment(
            method = PaymentMethodOption.CASH,
            enteredAmount = BigDecimal("5000"),
            remaining = BigDecimal.ZERO,
        )

        assertEquals(0, BigDecimal("5000").compareTo(applied))
        assertEquals(0, BigDecimal.ZERO.compareTo(change))
    }

    @Test
    fun `un segundo pago en efectivo calcula el vuelto contra lo que falta, no contra el total completo`() {
        // Ya se pagaron 30000 de un total de 60000 — falta 30000. Si el
        // cajero paga 50000 en efectivo, el vuelto es sobre esos 30000
        // que faltaban, no sobre el total de la venta.
        val (applied, change) = applyPayment(
            method = PaymentMethodOption.CASH,
            enteredAmount = BigDecimal("50000"),
            remaining = BigDecimal("30000"),
        )

        assertEquals(0, BigDecimal("30000").compareTo(applied))
        assertEquals(0, BigDecimal("20000").compareTo(change))
    }
}
