package com.astrim.pos.ui.catalog

import com.astrim.pos.core.network.dto.ProductSummaryDto
import org.junit.Assert.assertEquals
import org.junit.Test

private fun product(
    id: Int = 1,
    sku: String = "SKU-1",
    name: String = "Coca-Cola 400ml",
    categoryId: Int? = 3,
    categoryName: String? = "Bebidas",
    barcodes: List<String> = listOf("7701234567890"),
) = ProductSummaryDto(
    id = id,
    sku = sku,
    name = name,
    categoryId = categoryId,
    categoryName = categoryName,
    productType = "simple",
    unitPrice = "3500.00",
    unitOfMeasure = "unidad",
    saleUnit = "unit",
    isActive = true,
    trackInventory = true,
    imagePath = null,
    barcodes = barcodes,
)

/** Mismo criterio que `_matches_search` del backend (ver
 * `tests/unit/sync/test_products_router_search.py`): subcadena, sin
 * distinguir mayúsculas/minúsculas, sobre SKU + códigos de barras + nombre
 * + categoría. */
class FilterCatalogTest {

    @Test
    fun `sin categoria ni busqueda devuelve todos los productos`() {
        val products = listOf(product(id = 1), product(id = 2, name = "Papa criolla"))

        assertEquals(products, filterCatalog(products, categoryId = null, query = ""))
    }

    @Test
    fun `filtra por categoria seleccionada`() {
        val bebida = product(id = 1, categoryId = 3, categoryName = "Bebidas")
        val snack = product(id = 2, categoryId = 5, categoryName = "Snacks")

        val result = filterCatalog(listOf(bebida, snack), categoryId = 5, query = "")

        assertEquals(listOf(snack), result)
    }

    @Test
    fun `busqueda por nombre es subcadena y no distingue mayusculas`() {
        val products = listOf(product(name = "Coca-Cola 400ml"))

        assertEquals(products, filterCatalog(products, categoryId = null, query = "COCA"))
    }

    @Test
    fun `busqueda por sku`() {
        val products = listOf(product(sku = "ABC-123"))

        assertEquals(products, filterCatalog(products, categoryId = null, query = "abc-123"))
    }

    @Test
    fun `busqueda por codigo de barras`() {
        val products = listOf(product(barcodes = listOf("7701234567890")))

        assertEquals(products, filterCatalog(products, categoryId = null, query = "7701234567890"))
    }

    @Test
    fun `busqueda por nombre de categoria`() {
        val products = listOf(product(categoryName = "Bebidas"))

        assertEquals(products, filterCatalog(products, categoryId = null, query = "bebidas"))
    }

    @Test
    fun `busqueda sin coincidencias devuelve lista vacia`() {
        val products = listOf(product(name = "Coca-Cola 400ml"))

        assertEquals(emptyList<ProductSummaryDto>(), filterCatalog(products, categoryId = null, query = "papa"))
    }

    @Test
    fun `producto sin categoria no revienta la busqueda`() {
        val products = listOf(product(categoryId = null, categoryName = null, name = "Papa"))

        assertEquals(products, filterCatalog(products, categoryId = null, query = "papa"))
    }

    @Test
    fun `categoria y busqueda combinadas se aplican ambas`() {
        val bebidaCoca = product(id = 1, categoryId = 3, categoryName = "Bebidas", name = "Coca-Cola 400ml")
        val bebidaAgua = product(id = 2, categoryId = 3, categoryName = "Bebidas", name = "Agua")
        val snackCoca = product(id = 3, categoryId = 5, categoryName = "Snacks", name = "Coca de sal")

        val result = filterCatalog(listOf(bebidaCoca, bebidaAgua, snackCoca), categoryId = 3, query = "coca")

        assertEquals(listOf(bebidaCoca), result)
    }
}
