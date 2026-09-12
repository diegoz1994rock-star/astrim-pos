package com.astrim.pos.core.dispatch

import com.astrim.pos.core.network.ApiException
import com.astrim.pos.core.network.FakeApiService
import com.astrim.pos.core.network.dto.DispatchOrderCardDto
import com.astrim.pos.core.network.dto.DispatchOrderItemDto
import com.astrim.pos.core.network.httpErrorException
import com.astrim.pos.core.session.FakeTokenStore
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

private fun sampleCard(orderId: Int = 12, status: String = "pending") = DispatchOrderCardDto(
    orderId = orderId,
    origin = "vendedor",
    customerName = "Juan Pérez",
    customerDocument = null,
    isPaid = false,
    cajaName = null,
    dispatchStatus = status,
    itemCount = 1,
    totalUnits = 2,
    items = listOf(
        DispatchOrderItemDto(
            id = 30, orderId = orderId, productId = 5, productName = "Coca-Cola 400ml",
            quantity = 2, notes = "Sin hielo", status = status, productImagePath = null,
        ),
    ),
    createdAt = "2026-07-24T17:03:34.889253Z",
    createdByUserName = "Diego Gutiérrez",
    dispatchedByUserName = null,
    saleId = null,
)

/**
 * Ninguna de estas pruebas toca la red real (ver [FakeApiService]) ni el
 * framework de Android (ver [FakeTokenStore]) — corren en JVM puro, mismo
 * patrón que `SalesRepositoryTest`/`CatalogRepositoryTest`.
 */
class DispatchRepositoryTest {

    @Test
    fun `listOrders sin servidor configurado devuelve error sin llamar a la API`() = runTest {
        val repository = DispatchRepository(
            FakeTokenStore(),
            apiServiceFactory = { error("no debería construirse un ApiService sin servidor") },
        )

        val result = repository.listOrders()

        assertTrue(result.isFailure)
    }

    @Test
    fun `listOrders exitoso devuelve la cola tal cual`() = runTest {
        val cards = listOf(sampleCard())
        val api = FakeApiService(listDispatchOrdersResult = Result.success(cards))
        val repository = DispatchRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.listOrders()

        assertTrue(result.isSuccess)
        assertEquals(cards, result.getOrNull())
    }

    @Test
    fun `listOrders sin permiso devuelve el 403 del backend`() = runTest {
        val api = FakeApiService(
            listDispatchOrdersResult = Result.failure(httpErrorException(403, "No tienes permiso para esta acción.")),
        )
        val repository = DispatchRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.listOrders()

        assertTrue(result.isFailure)
        assertEquals(403, (result.exceptionOrNull() as ApiException).statusCode)
    }

    @Test
    fun `advanceOrder envia el id correcto y devuelve la cola recargada`() = runTest {
        val cards = listOf(sampleCard(status = "preparing"))
        val api = FakeApiService(advanceDispatchOrderResult = Result.success(cards))
        val repository = DispatchRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.advanceOrder(12)

        assertTrue(result.isSuccess)
        assertEquals(cards, result.getOrNull())
        assertEquals(12, api.lastAdvanceDispatchOrderId)
    }

    @Test
    fun `advanceOrder sobre un pedido inexistente devuelve el 404 del backend`() = runTest {
        val api = FakeApiService(
            advanceDispatchOrderResult = Result.failure(httpErrorException(404, "No existe el pedido con id=999999.")),
        )
        val repository = DispatchRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.advanceOrder(999999)

        assertTrue(result.isFailure)
        assertEquals(404, (result.exceptionOrNull() as ApiException).statusCode)
    }

    @Test
    fun `deliverOrder envia el id correcto y devuelve la cola recargada`() = runTest {
        val cards = listOf(sampleCard(status = "delivered"))
        val api = FakeApiService(deliverDispatchOrderResult = Result.success(cards))
        val repository = DispatchRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.deliverOrder(12)

        assertTrue(result.isSuccess)
        assertEquals("delivered", result.getOrNull()?.get(0)?.dispatchStatus)
        assertEquals(12, api.lastDeliverDispatchOrderId)
    }
}
