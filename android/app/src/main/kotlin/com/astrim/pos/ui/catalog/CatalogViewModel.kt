package com.astrim.pos.ui.catalog

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.astrim.pos.core.catalog.CATALOG_POLL_INTERVAL_MS
import com.astrim.pos.core.catalog.CatalogRepository
import com.astrim.pos.core.network.dto.CategoryDto
import com.astrim.pos.core.network.dto.ProductSummaryDto
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class CatalogUiState(
    val isLoading: Boolean = true,
    val errorMessage: String? = null,
    val categories: List<CategoryDto> = emptyList(),
    val products: List<ProductSummaryDto> = emptyList(),
    val selectedCategoryId: Int? = null,
    val searchText: String = "",
    val barcodeText: String = "",
    val barcodeError: String? = null,
    val isSearchingBarcode: Boolean = false,
    val selectedProduct: ProductSummaryDto? = null,
) {
    val filteredProducts: List<ProductSummaryDto>
        get() = filterCatalog(products, selectedCategoryId, searchText)
}

/**
 * Mismo criterio que la búsqueda en vivo del escritorio y que
 * `_matches_search` del backend (ver API.md §3.4 y
 * `sync/server/api/products_router.py`): subcadena, sin distinguir
 * mayúsculas/minúsculas, sobre SKU + códigos de barras + nombre + categoría.
 * Función pura (sin dependencias de Android) para poder probarla en JVM
 * puro sin instrumentación.
 */
fun filterCatalog(
    products: List<ProductSummaryDto>,
    categoryId: Int?,
    query: String,
): List<ProductSummaryDto> {
    val byCategory = if (categoryId == null) products else products.filter { it.categoryId == categoryId }
    val needle = query.trim().lowercase()
    if (needle.isEmpty()) return byCategory
    return byCategory.filter { product ->
        val haystack = buildString {
            append(product.sku)
            append(' ')
            product.barcodes.forEach { append(it); append(' ') }
            append(product.name)
            append(' ')
            append(product.categoryName.orEmpty())
        }.lowercase()
        needle in haystack
    }
}

/**
 * Sin lógica de negocio propia: carga el catálogo una sola vez y filtra en
 * memoria (ver [filterCatalog]) para que la búsqueda por nombre y el filtro
 * por categoría sean instantáneos, igual que el buscador del escritorio
 * filtra sobre la tabla ya cargada. Solo la búsqueda por código de barras
 * va al servidor en cada intento (ver [CatalogRepository.findProductByBarcode]).
 */
class CatalogViewModel(private val repository: CatalogRepository) : ViewModel() {

    private val _uiState = MutableStateFlow(CatalogUiState())
    val uiState: StateFlow<CatalogUiState> = _uiState.asStateFlow()

    init {
        load()
        startCatalogPolling()
    }

    fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            repository.loadCatalog()
                .onSuccess { data ->
                    _uiState.update {
                        it.copy(isLoading = false, categories = data.categories, products = data.products)
                    }
                }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(isLoading = false, errorMessage = error.message ?: "Error desconocido.")
                    }
                }
        }
    }

    /** Sondeo periódico (Sincronización en tiempo real): refleja en esta
     * pantalla altas/ediciones/bajas de productos hechas en el escritorio
     * sin que el usuario tenga que salir y volver a entrar — ver
     * [CATALOG_POLL_INTERVAL_MS]. Se cancela solo al cerrarse la pantalla
     * (vive en `viewModelScope`, igual que cualquier otra corrutina de
     * este ViewModel). Un fallo de sondeo se ignora en silencio: no tiene
     * sentido reemplazar una lista que ya funciona por una pantalla de
     * error solo porque una consulta de fondo tuvo un hipo de red pasajero.
     *
     * `Dispatchers.IO` explícito a propósito: esta corrutina nunca
     * termina mientras la pantalla esté abierta, y `viewModelScope` usa
     * `Dispatchers.Main.immediate` por defecto — en las pruebas, eso
     * comparte el mismo `TestCoroutineScheduler` que instala
     * `Dispatchers.setMain(...)`, y `runTest` intenta agotarlo por
     * completo al terminar, lo que colgaría cualquier prueba que
     * construya este ViewModel (un bucle que jamás se agota nunca deja
     * "agotar" al scheduler). Al despachar en `Dispatchers.IO` — que las
     * pruebas no reemplazan — el sondeo queda fuera del reloj virtual de
     * las pruebas, igual que corre en un hilo real en producción. */
    private fun startCatalogPolling() {
        viewModelScope.launch(Dispatchers.IO) {
            while (true) {
                delay(CATALOG_POLL_INTERVAL_MS)
                repository.loadCatalog().onSuccess { data ->
                    _uiState.update { it.copy(categories = data.categories, products = data.products) }
                }
            }
        }
    }

    fun onSearchTextChange(text: String) {
        _uiState.update { it.copy(searchText = text) }
    }

    fun onCategorySelected(categoryId: Int?) {
        _uiState.update { it.copy(selectedCategoryId = categoryId) }
    }

    fun onBarcodeTextChange(text: String) {
        _uiState.update { it.copy(barcodeText = text, barcodeError = null) }
    }

    /** Refleja el mismo flujo que `_on_scan_entered` del escritorio: escanear
     * (o tipear) un código y Enter busca ese producto puntual contra el
     * servidor, sin importar si ya está entre los productos cargados. */
    fun onBarcodeSubmit() {
        val code = _uiState.value.barcodeText.trim()
        if (code.isBlank()) return
        viewModelScope.launch {
            _uiState.update { it.copy(isSearchingBarcode = true, barcodeError = null) }
            repository.findProductByBarcode(code)
                .onSuccess { product ->
                    _uiState.update {
                        it.copy(
                            isSearchingBarcode = false,
                            barcodeText = "",
                            searchText = "",
                            selectedCategoryId = null,
                            selectedProduct = product,
                        )
                    }
                }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(
                            isSearchingBarcode = false,
                            barcodeError = error.message ?: "No se encontró ningún producto con ese código.",
                        )
                    }
                }
        }
    }

    fun onProductSelected(product: ProductSummaryDto?) {
        _uiState.update { it.copy(selectedProduct = product) }
    }
}
