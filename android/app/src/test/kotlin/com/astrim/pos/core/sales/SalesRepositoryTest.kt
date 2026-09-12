package com.astrim.pos.core.sales

import com.astrim.pos.core.network.ApiException
import com.astrim.pos.core.network.FakeApiService
import com.astrim.pos.core.network.dto.CompletedSaleDto
import com.astrim.pos.core.network.dto.SaleDraftDto
import com.astrim.pos.core.network.dto.SaleDraftLineDto
import com.astrim.pos.core.network.dto.SaleItemDto
import com.astrim.pos.core.network.dto.SalePaymentDto
import com.astrim.pos.core.network.dto.SalePaymentRequest
import com.astrim.pos.core.network.httpErrorException
import com.astrim.pos.core.session.FakeTokenStore
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

private fun emptyDraft(draftId: String = "draft-1") = SaleDraftDto(
    draftId = draftId,
    subtotal = "0",
    discountTotal = "0",
    taxTotal = "0",
    total = "0",
    items = emptyList(),
)

private fun draftWithLine(draftId: String = "draft-1") = SaleDraftDto(
    draftId = draftId,
    subtotal = "3500.00",
    discountTotal = "0",
    taxTotal = "0",
    total = "3500.00",
    items = listOf(
        SaleDraftLineDto(
            productId = 12,
            productName = "Coca-Cola 400ml",
            quantity = "1",
            unitPrice = "3500.00",
            discountAmount = "0",
            taxAmount = "0",
            lineTotal = "3500.00",
            note = null,
        ),
    ),
)

private fun completedSale() = CompletedSaleDto(
    id = 45,
    status = "completed",
    saleType = "counter",
    customerId = null,
    subtotal = "3500.00",
    discountTotal = "0",
    taxTotal = "0",
    total = "3500.00",
    createdAt = "2026-07-24T17:10:00.000000Z",
    createdByUserId = 7,
    cashSessionId = 3,
    customerName = null,
    customerDocument = null,
    items = listOf(
        SaleItemDto(
            id = 91, productId = 12, productName = "Coca-Cola 400ml", quantity = "1.000",
            unitPrice = "3500.00", discountAmount = "0", taxAmount = "0", lineTotal = "3500.00",
            note = null, saleUnit = "unit", unitOfMeasure = "unidad",
        ),
    ),
    payments = listOf(SalePaymentDto(id = 33, paymentMethod = "cash", amount = "3500.00", reference = null)),
)

/**
 * Ninguna de estas pruebas toca la red real (ver [FakeApiService]) ni el
 * framework de Android (ver [FakeTokenStore]) — corren en JVM puro, mismo
 * patrón que `CatalogRepositoryTest`. Ningún total se recalcula acá: cada
 * prueba solo verifica que el repositorio devuelve/reenvía tal cual lo que
 * responde la API.
 */
class SalesRepositoryTest {

    @Test
    fun `createDraft sin servidor configurado devuelve error sin llamar a la API`() = runTest {
        val repository = SalesRepository(
            FakeTokenStore(),
            apiServiceFactory = { error("no debería construirse un ApiService sin servidor") },
        )

        val result = repository.createDraft()

        assertTrue(result.isFailure)
    }

    @Test
    fun `createDraft exitoso devuelve el carrito vacio`() = runTest {
        val draft = emptyDraft()
        val api = FakeApiService(createDraftResult = Result.success(draft))
        val repository = SalesRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.createDraft()

        assertTrue(result.isSuccess)
        assertEquals(draft, result.getOrNull())
    }

    @Test
    fun `addItem envia product_id y cantidad y devuelve el carrito actualizado`() = runTest {
        val updatedDraft = draftWithLine()
        val api = FakeApiService(addItemResult = Result.success(updatedDraft))
        val repository = SalesRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.addItem("draft-1", productId = 12, quantity = "1")

        assertTrue(result.isSuccess)
        assertEquals(updatedDraft, result.getOrNull())
        assertEquals("draft-1", api.lastAddItemDraftId)
        assertEquals(12, api.lastAddItemRequest?.productId)
        assertEquals("1", api.lastAddItemRequest?.quantity)
    }

    @Test
    fun `addItem con stock insuficiente devuelve el 409 del backend`() = runTest {
        val api = FakeApiService(
            addItemResult = Result.failure(httpErrorException(409, "Stock insuficiente para 'Coca-Cola 400ml'.")),
        )
        val repository = SalesRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.addItem("draft-1", productId = 12, quantity = "100")

        assertTrue(result.isFailure)
        val error = result.exceptionOrNull()
        assertTrue(error is ApiException)
        assertEquals(409, (error as ApiException).statusCode)
    }

    @Test
    fun `updateItem envia cantidad y nota a la linea correcta`() = runTest {
        val updatedDraft = draftWithLine()
        val api = FakeApiService(updateItemResult = Result.success(updatedDraft))
        val repository = SalesRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.updateItem("draft-1", itemIndex = 0, quantity = "3", note = "Sin hielo")

        assertTrue(result.isSuccess)
        assertEquals("draft-1", api.lastUpdateItemDraftId)
        assertEquals(0, api.lastUpdateItemIndex)
        assertEquals("3", api.lastUpdateItemRequest?.quantity)
        assertEquals("Sin hielo", api.lastUpdateItemRequest?.note)
    }

    @Test
    fun `removeItem elimina la linea indicada`() = runTest {
        val api = FakeApiService(removeItemResult = Result.success(emptyDraft()))
        val repository = SalesRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.removeItem("draft-1", itemIndex = 0)

        assertTrue(result.isSuccess)
        assertEquals("draft-1", api.lastRemoveItemDraftId)
        assertEquals(0, api.lastRemoveItemIndex)
    }

    @Test
    fun `completeSale envia los pagos y el cliente y devuelve la venta persistida`() = runTest {
        val sale = completedSale()
        val api = FakeApiService(completeSaleResult = Result.success(sale))
        val repository = SalesRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.completeSale(
            draftId = "draft-1",
            payments = listOf(SalePaymentRequest(paymentMethod = "cash", amount = "3500.00")),
            customerId = 42,
            customerName = "Juan Pérez",
            customerDocument = "123456",
        )

        assertTrue(result.isSuccess)
        assertEquals(sale, result.getOrNull())
        assertEquals("draft-1", api.lastCompleteSaleDraftId)
        assertEquals(1, api.lastCompleteSaleRequest?.payments?.size)
        assertEquals("cash", api.lastCompleteSaleRequest?.payments?.get(0)?.paymentMethod)
        assertEquals("Juan Pérez", api.lastCompleteSaleRequest?.customerName)
        assertEquals(42, api.lastCompleteSaleRequest?.customerId)
    }

    @Test
    fun `completeSale con carrito vacio devuelve el 422 del backend`() = runTest {
        val api = FakeApiService(
            completeSaleResult = Result.failure(
                httpErrorException(422, "La venta debe tener al menos un producto."),
            ),
        )
        val repository = SalesRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.completeSale(
            draftId = "draft-1",
            payments = emptyList(),
            customerId = null,
            customerName = null,
            customerDocument = null,
        )

        assertTrue(result.isFailure)
        assertEquals(422, (result.exceptionOrNull() as ApiException).statusCode)
    }

    @Test
    fun `getSale devuelve la venta ya persistida`() = runTest {
        val sale = completedSale()
        val api = FakeApiService(getSaleResult = Result.success(sale))
        val repository = SalesRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.getSale(45)

        assertTrue(result.isSuccess)
        assertEquals(sale, result.getOrNull())
        assertEquals(45, api.lastGetSaleId)
    }

    @Test
    fun `getSale sin permiso sales-create devuelve el 403 del backend`() = runTest {
        val api = FakeApiService(
            getSaleResult = Result.failure(httpErrorException(403, "No tienes permiso para esta acción.")),
        )
        val repository = SalesRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.getSale(45)

        assertTrue(result.isFailure)
        assertEquals(403, (result.exceptionOrNull() as ApiException).statusCode)
    }

    @Test
    fun `listSales devuelve el historial de ventas recientes`() = runTest {
        val sale = completedSale()
        val api = FakeApiService(listSalesResult = Result.success(listOf(sale)))
        val repository = SalesRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.listSales()

        assertTrue(result.isSuccess)
        assertEquals(listOf(sale), result.getOrNull())
    }

    @Test
    fun `listSales sin permiso sales-create devuelve el 403 del backend`() = runTest {
        val api = FakeApiService(
            listSalesResult = Result.failure(httpErrorException(403, "No tienes permiso para esta acción.")),
        )
        val repository = SalesRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.listSales()

        assertTrue(result.isFailure)
        assertEquals(403, (result.exceptionOrNull() as ApiException).statusCode)
    }
}
