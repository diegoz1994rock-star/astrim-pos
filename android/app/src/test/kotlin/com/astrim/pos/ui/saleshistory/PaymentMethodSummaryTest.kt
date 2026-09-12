package com.astrim.pos.ui.saleshistory

import com.astrim.pos.core.network.dto.CompletedSaleDto
import com.astrim.pos.core.network.dto.SaleItemDto
import com.astrim.pos.core.network.dto.SalePaymentDto
import org.junit.Assert.assertEquals
import org.junit.Test

private fun sale(payments: List<SalePaymentDto>) = CompletedSaleDto(
    id = 1,
    status = "completed",
    saleType = "counter",
    customerId = null,
    subtotal = "1000",
    discountTotal = "0",
    taxTotal = "0",
    total = "1000",
    createdAt = "2026-07-30T10:00:00Z",
    createdByUserId = 1,
    cashSessionId = 1,
    customerName = null,
    customerDocument = null,
    items = listOf(
        SaleItemDto(
            id = 1, productId = 1, productName = "Producto", quantity = "1",
            unitPrice = "1000", discountAmount = "0", taxAmount = "0", lineTotal = "1000",
            note = null, saleUnit = "unit", unitOfMeasure = "unidad",
        ),
    ),
    payments = payments,
)

/** Réplica de `paymentMethodSummary` de `sales_history_view_model.py` del
 * escritorio — mismo criterio de unión/valor por defecto. */
class PaymentMethodSummaryTest {

    @Test
    fun `una venta sin pagos registrados muestra No registrado`() {
        assertEquals("No registrado", paymentMethodSummary(sale(emptyList())))
    }

    @Test
    fun `un solo pago muestra la etiqueta de ese metodo`() {
        val payments = listOf(SalePaymentDto(id = 1, paymentMethod = "cash", amount = "1000", reference = null))
        assertEquals("Efectivo", paymentMethodSummary(sale(payments)))
    }

    @Test
    fun `pago mixto une los metodos con un signo mas`() {
        val payments = listOf(
            SalePaymentDto(id = 1, paymentMethod = "cash", amount = "500", reference = null),
            SalePaymentDto(id = 2, paymentMethod = "card", amount = "500", reference = null),
        )
        assertEquals("Efectivo + Tarjeta", paymentMethodSummary(sale(payments)))
    }
}
