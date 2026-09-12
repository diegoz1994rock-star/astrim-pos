package com.astrim.pos.core.network

import org.junit.Assert.assertEquals
import org.junit.Test

class NormalizeServerUrlTest {

    @Test
    fun `agrega esquema http y barra final cuando faltan`() {
        assertEquals("http://192.168.1.50:8765/", normalizeServerUrl("192.168.1.50:8765"))
    }

    @Test
    fun `no duplica el esquema si ya viene con http`() {
        assertEquals("http://192.168.1.50:8765/", normalizeServerUrl("http://192.168.1.50:8765"))
    }

    @Test
    fun `respeta https si el usuario lo escribe explicito`() {
        assertEquals("https://192.168.1.50:8765/", normalizeServerUrl("https://192.168.1.50:8765"))
    }

    @Test
    fun `no duplica la barra final si ya viene incluida`() {
        assertEquals("http://192.168.1.50:8765/", normalizeServerUrl("http://192.168.1.50:8765/"))
    }

    @Test
    fun `recorta espacios en blanco`() {
        assertEquals("http://192.168.1.50:8765/", normalizeServerUrl("  192.168.1.50:8765  "))
    }
}
