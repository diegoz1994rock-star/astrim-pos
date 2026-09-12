package com.astrim.pos.core.restaurant

import com.astrim.pos.core.network.ApiException
import com.astrim.pos.core.network.FakeApiService
import com.astrim.pos.core.network.dto.OrderDto
import com.astrim.pos.core.network.dto.OrderItemDto
import com.astrim.pos.core.network.dto.OrderItemLineRequest
import com.astrim.pos.core.network.dto.OrderPreviewDto
import com.astrim.pos.core.network.dto.SaleDraftLineDto
import com.astrim.pos.core.network.httpErrorException
import com.astrim.pos.core.session.FakeTokenStore
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

private fun samplePreview() = OrderPreviewDto(
    subtotal = "30000",
    discountTotal = "0",
    taxTotal = "5700",
    total = "35700",
    items = listOf(
        SaleDraftLineDto(
            productId = 12,
            productName = "Hamburguesa",
            quantity = "2",
            unitPrice = "15000",
            discountAmount = "0",
            taxAmount = "5700",
            lineTotal = "35700",
            note = "Sin cebolla",
        ),
    ),
)

private fun sampleOrder(id: Int = 45, status: String = "pending") = OrderDto(
    id = id,
    tableSessionId = null,
    orderType = "quick",
    status = status,
    items = listOf(
        OrderItemDto(
            id = 90, productId = 12, productName = "Hamburguesa", quantity = 2,
            notes = "Sin cebolla", status = "pending", productImagePath = null,
        ),
    ),
    createdAt = "2026-07-26T10:00:00.000000Z",
    createdByUserId = 7,
    saleId = null,
    customerName = "Juan Pérez",
    customerDocument = "123456",
    origin = "vendedor",
    dispatchedByUserId = null,
)

/**
 * Ninguna de estas pruebas toca la red real (ver [FakeApiService]) ni el
 * framework de Android (ver [FakeTokenStore]) — corren en JVM puro, mismo
 * patrón que `SalesRepositoryTest`/`CashRegisterRepositoryTest`.
 */
class RestaurantRepositoryTest {

    @Test
    fun `previewOrder sin servidor configurado devuelve error sin llamar a la API`() = runTest {
        val repository = RestaurantRepository(
            FakeTokenStore(),
            apiServiceFactory = { error("no debería construirse un ApiService sin servidor") },
        )

        val result = repository.previewOrder(listOf(OrderItemLineRequest(productId = 12, quantity = "2")))

        assertTrue(result.isFailure)
    }

    @Test
    fun `previewOrder exitoso devuelve el total tal cual`() = runTest {
        val preview = samplePreview()
        val api = FakeApiService(previewOrderResult = Result.success(preview))
        val repository = RestaurantRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.previewOrder(
            listOf(OrderItemLineRequest(productId = 12, quantity = "2", note = "Sin cebolla")),
        )

        assertTrue(result.isSuccess)
        assertEquals(preview, result.getOrNull())
        assertEquals(1, api.lastPreviewOrderRequest?.items?.size)
        assertEquals(12, api.lastPreviewOrderRequest?.items?.get(0)?.productId)
    }

    @Test
    fun `previewOrder con stock insuficiente devuelve el 409 del backend`() = runTest {
        val api = FakeApiService(
            previewOrderResult = Result.failure(
                httpErrorException(409, "Stock insuficiente para 'Hamburguesa'. Disponible: 5 unidad."),
            ),
        )
        val repository = RestaurantRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.previewOrder(listOf(OrderItemLineRequest(productId = 12, quantity = "100")))

        assertTrue(result.isFailure)
        assertEquals(409, (result.exceptionOrNull() as ApiException).statusCode)
    }

    @Test
    fun `createOrder envia los items y el cliente y devuelve el pedido confirmado`() = runTest {
        val order = sampleOrder()
        val api = FakeApiService(createOrderResult = Result.success(order))
        val repository = RestaurantRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.createOrder(
            items = listOf(OrderItemLineRequest(productId = 12, quantity = "2", note = "Sin cebolla")),
            customerName = "Juan Pérez",
            customerDocument = "123456",
        )

        assertTrue(result.isSuccess)
        assertEquals(order, result.getOrNull())
        assertEquals("pending", result.getOrNull()?.status)
        assertEquals("vendedor", result.getOrNull()?.origin)
        assertEquals("Juan Pérez", api.lastCreateOrderRequest?.customerName)
        assertEquals(1, api.lastCreateOrderRequest?.items?.size)
    }

    @Test
    fun `createOrder con carrito vacio devuelve el 422 del backend`() = runTest {
        val api = FakeApiService(
            createOrderResult = Result.failure(
                httpErrorException(422, "El pedido debe tener al menos un producto."),
            ),
        )
        val repository = RestaurantRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.createOrder(items = emptyList(), customerName = null, customerDocument = null)

        assertTrue(result.isFailure)
        assertEquals(422, (result.exceptionOrNull() as ApiException).statusCode)
    }
}
