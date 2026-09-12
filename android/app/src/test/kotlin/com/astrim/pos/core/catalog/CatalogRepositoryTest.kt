package com.astrim.pos.core.catalog

import com.astrim.pos.core.network.ApiException
import com.astrim.pos.core.network.FakeApiService
import com.astrim.pos.core.network.dto.CategoryDto
import com.astrim.pos.core.network.dto.ProductSummaryDto
import com.astrim.pos.core.network.httpErrorException
import com.astrim.pos.core.session.FakeTokenStore
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

private fun sampleProduct(id: Int = 1, name: String = "Coca-Cola 400ml") = ProductSummaryDto(
    id = id,
    sku = "SKU-$id",
    name = name,
    categoryId = 3,
    categoryName = "Bebidas",
    productType = "simple",
    unitPrice = "3500.00",
    unitOfMeasure = "unidad",
    saleUnit = "unit",
    isActive = true,
    trackInventory = true,
    imagePath = null,
    barcodes = listOf("7701234567890"),
)

/**
 * Ninguna de estas pruebas toca la red real (ver [FakeApiService]) ni el
 * framework de Android (ver [FakeTokenStore]) — corren en JVM puro, mismo
 * patrón que `SessionRepositoryTest`.
 */
class CatalogRepositoryTest {

    @Test
    fun `loadCatalog sin servidor configurado devuelve error sin llamar a la API`() = runTest {
        val repository = CatalogRepository(
            FakeTokenStore(),
            apiServiceFactory = { error("no debería construirse un ApiService sin servidor") },
        )

        val result = repository.loadCatalog()

        assertTrue(result.isFailure)
    }

    @Test
    fun `loadCatalog exitoso devuelve categorias y productos`() = runTest {
        val categories = listOf(CategoryDto(id = 3, name = "Bebidas", isActive = true))
        val products = listOf(sampleProduct())
        val api = FakeApiService(
            categoriesResult = Result.success(categories),
            productsResult = Result.success(products),
        )
        val repository = CatalogRepository(
            FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"),
            apiServiceFactory = { api },
        )

        val result = repository.loadCatalog()

        assertTrue(result.isSuccess)
        assertEquals(CatalogData(categories, products), result.getOrNull())
    }

    @Test
    fun `loadCatalog con error del servidor devuelve el mensaje real`() = runTest {
        val api = FakeApiService(categoriesResult = Result.failure(httpErrorException(401, "Token inválido o expirado.")))
        val repository = CatalogRepository(
            FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"),
            apiServiceFactory = { api },
        )

        val result = repository.loadCatalog()

        assertTrue(result.isFailure)
        val error = result.exceptionOrNull()
        assertTrue(error is ApiException)
        assertEquals("Token inválido o expirado.", error?.message)
    }

    @Test
    fun `findProductByBarcode exitoso devuelve el producto y registra el codigo consultado`() = runTest {
        val product = sampleProduct()
        val api = FakeApiService(barcodeResult = Result.success(product))
        val repository = CatalogRepository(
            FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"),
            apiServiceFactory = { api },
        )

        val result = repository.findProductByBarcode("7701234567890")

        assertTrue(result.isSuccess)
        assertEquals(product, result.getOrNull())
        assertEquals("7701234567890", api.lastBarcodeQueried)
    }

    @Test
    fun `findProductByBarcode sin coincidencia devuelve el 404 del backend`() = runTest {
        val api = FakeApiService(
            barcodeResult = Result.failure(
                httpErrorException(404, "No existe ningún producto con ese código de barras."),
            ),
        )
        val repository = CatalogRepository(
            FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"),
            apiServiceFactory = { api },
        )

        val result = repository.findProductByBarcode("no-existe")

        assertTrue(result.isFailure)
        val error = result.exceptionOrNull()
        assertTrue(error is ApiException)
        assertEquals(404, (error as ApiException).statusCode)
    }

    @Test
    fun `imageUrl arma la url completa a partir del servidor guardado`() {
        val repository = CatalogRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"))

        assertEquals("http://192.168.1.50:8765/api/v1/products/12/image", repository.imageUrl(12, null))
    }

    @Test
    fun `imageUrl sin servidor configurado devuelve null`() {
        val repository = CatalogRepository(FakeTokenStore())

        assertNull(repository.imageUrl(12, null))
    }

    @Test
    fun `imageUrl agrega un parametro de cache basado en imagePath`() {
        val repository = CatalogRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"))

        val url = repository.imageUrl(12, "/data/product_images/abc123.jpg")

        assertEquals(
            "http://192.168.1.50:8765/api/v1/products/12/image?v=${"/data/product_images/abc123.jpg".hashCode()}",
            url,
        )
    }

    @Test
    fun `imageUrl con distinto imagePath produce distinta url para invalidar la cache de Coil`() {
        val repository = CatalogRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"))

        val before = repository.imageUrl(12, "/data/product_images/old.jpg")
        val after = repository.imageUrl(12, "/data/product_images/new.jpg")

        assertTrue(before != after)
    }
}
