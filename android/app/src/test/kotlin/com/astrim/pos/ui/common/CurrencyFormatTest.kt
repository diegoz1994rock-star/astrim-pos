package com.astrim.pos.ui.common

import org.junit.Assert.assertEquals
import org.junit.Test

/** Mismos casos que `tests/unit/.../formatting.py::format_currency` del
 * escritorio, para que un precio se vea idéntico en ambos clientes.
 * Compartida entre Catálogo y Ventas. */
class CurrencyFormatTest {

    @Test
    fun `numero redondo no muestra decimales`() {
        assertEquals("3.500", formatCurrency("3500.00"))
    }

    @Test
    fun `centavos reales se muestran con coma`() {
        assertEquals("3.500,50", formatCurrency("3500.50"))
    }

    @Test
    fun `miles se separan con punto`() {
        assertEquals("1.250.000", formatCurrency("1250000.00"))
    }

    @Test
    fun `valores negativos conservan el signo`() {
        assertEquals("-3.500", formatCurrency("-3500.00"))
    }

    @Test
    fun `valor no numerico se devuelve tal cual`() {
        assertEquals("no-es-un-numero", formatCurrency("no-es-un-numero"))
    }
}
