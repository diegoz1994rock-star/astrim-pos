package com.astrim.pos.ui.vendor

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.astrim.pos.core.catalog.CATALOG_POLL_INTERVAL_MS
import com.astrim.pos.core.catalog.CatalogRepository
import com.astrim.pos.core.network.dto.OrderDto
import com.astrim.pos.core.network.dto.OrderItemLineRequest
import com.astrim.pos.core.network.dto.OrderPreviewDto
import com.astrim.pos.core.network.dto.ProductSummaryDto
import com.astrim.pos.core.restaurant.RestaurantRepository
import com.astrim.pos.ui.catalog.filterCatalog
import java.math.BigDecimal
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class VendorUiState(
    val isLoadingCatalog: Boolean = true,
    val catalogError: String? = null,
    val products: List<ProductSummaryDto> = emptyList(),
    val searchText: String = "",
    val items: List<OrderItemLineRequest> = emptyList(),
    val preview: OrderPreviewDto? = null,
    val isCartLoading: Boolean = false,
    val cartError: String? = null,
    val editingLineIndex: Int? = null,
    val customerName: String = "",
    val customerDocument: String = "",
    val isSending: Boolean = false,
    val sendError: String? = null,
    val confirmedOrder: OrderDto? = null,
) {
    val filteredProducts: List<ProductSummaryDto>
        get() = if (searchText.isBlank()) emptyList() else filterCatalog(products, categoryId = null, query = searchText)
}

/**
 * Sin lógica de negocio propia: cada acción del vendedor es una llamada
 * directa a [RestaurantRepository] (que refleja `/api/v1/restaurant`, ver
 * API.md §3.11) — subtotal/impuestos/total siempre vienen ya calculados
 * en la respuesta (`OrderPreviewDto`, la misma `SalesService.preview_sale`
 * que ya usa Ventas), nunca se recalculan acá. El buscador de productos
 * reutiliza [filterCatalog], el mismo criterio que ya usan Catálogo y
 * Ventas — mismo catálogo, ningún buscador nuevo.
 *
 * A diferencia de Ventas (que arma su carrito contra un `draft_id`
 * persistido en el servidor), acá el pedido en construcción
 * (`_uiState.items`) vive en memoria de este `ViewModel` — igual que
 * `RestaurantViewModel._items` vive en memoria del proceso Qt del
 * escritorio hasta confirmarlo (`restaurant_router.py` no tiene concepto
 * de carrito persistido para Vendedor). Cada vez que el carrito cambia,
 * se llama a `previewOrder` con la lista completa para recalcular el
 * total y validar stock — si esa llamada falla (ej. stock insuficiente),
 * el carrito NO se actualiza y se muestra el error, igual que
 * `RestaurantViewModel.add_item`/`update_item` no agregan la línea si
 * `_check_stock` la rechaza.
 */
class VendorViewModel(
    private val catalogRepository: CatalogRepository,
    private val restaurantRepository: RestaurantRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(VendorUiState())
    val uiState: StateFlow<VendorUiState> = _uiState.asStateFlow()

    init {
        loadCatalog()
        startCatalogPolling()
    }

    private fun loadCatalog() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoadingCatalog = true, catalogError = null) }
            catalogRepository.loadCatalog()
                .onSuccess { data -> _uiState.update { it.copy(isLoadingCatalog = false, products = data.products) } }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(isLoadingCatalog = false, catalogError = error.message ?: "Error desconocido.")
                    }
                }
        }
    }

    /** Sondeo periódico (Sincronización en tiempo real): refleja en el
     * buscador de productos altas/ediciones/bajas hechas en el escritorio
     * sin que el vendedor tenga que salir y volver a entrar — ver
     * [CATALOG_POLL_INTERVAL_MS]. Un fallo de sondeo se ignora en silencio
     * (mismo criterio que en Catálogo/Ventas): no tiene sentido
     * interrumpir un pedido en curso por un hipo de red pasajero en una
     * consulta de fondo.
     *
     * `Dispatchers.IO` explícito (ver el mismo razonamiento en
     * `CatalogViewModel.startCatalogPolling`): este bucle nunca termina
     * mientras la pantalla esté abierta, y despacharlo en
     * `Dispatchers.Main.immediate` (lo que usa `viewModelScope` por
     * defecto) colgaría cualquier prueba que construya este ViewModel con
     * `Dispatchers.setMain(...)`, porque `runTest` intenta agotar por
     * completo ese mismo reloj virtual al terminar. */
    private fun startCatalogPolling() {
        viewModelScope.launch(Dispatchers.IO) {
            while (true) {
                delay(CATALOG_POLL_INTERVAL_MS)
                catalogRepository.loadCatalog().onSuccess { data ->
                    _uiState.update { it.copy(products = data.products) }
                }
            }
        }
    }

    fun onSearchTextChange(text: String) {
        _uiState.update { it.copy(searchText = text) }
    }

    /** Igual que `RestaurantViewModel.add_item`: si el producto ya está en
     * el pedido, suma la cantidad a la línea existente en vez de crear una
     * línea duplicada. */
    fun onAddProduct(product: ProductSummaryDto) {
        _uiState.update { it.copy(searchText = "") }
        val current = _uiState.value.items
        val existingIndex = current.indexOfFirst { it.productId == product.id }
        val newItems = if (existingIndex >= 0) {
            val existing = current[existingIndex]
            val newQuantity = (existing.quantity.toBigDecimalOrNull() ?: BigDecimal.ONE) + BigDecimal.ONE
            current.toMutableList().apply {
                this[existingIndex] = existing.copy(quantity = newQuantity.toPlainString())
            }
        } else {
            current + OrderItemLineRequest(productId = product.id, quantity = "1")
        }
        refreshPreview(newItems)
    }

    /** Botones "+"/"-" de la línea del carrito — mismo efecto que editar
     * la cantidad desde el diálogo, solo un atajo de un toque. Bajar a 0
     * elimina la línea, igual que `remove_item` del escritorio. */
    fun onIncrementLine(index: Int) {
        val items = _uiState.value.items
        if (index !in items.indices) return
        val current = items[index].quantity.toBigDecimalOrNull() ?: return
        setLineQuantity(index, (current + BigDecimal.ONE).toPlainString())
    }

    fun onDecrementLine(index: Int) {
        val items = _uiState.value.items
        if (index !in items.indices) return
        val current = items[index].quantity.toBigDecimalOrNull() ?: return
        val next = current - BigDecimal.ONE
        if (next <= BigDecimal.ZERO) {
            onRemoveLine(index)
        } else {
            setLineQuantity(index, next.toPlainString())
        }
    }

    private fun setLineQuantity(index: Int, quantity: String) {
        val items = _uiState.value.items
        if (index !in items.indices) return
        val newItems = items.toMutableList().apply { this[index] = this[index].copy(quantity = quantity) }
        refreshPreview(newItems)
    }

    fun onEditLine(index: Int) {
        _uiState.update { it.copy(editingLineIndex = index) }
    }

    fun onDismissEditLine() {
        _uiState.update { it.copy(editingLineIndex = null) }
    }

    fun onConfirmEditLine(quantity: String, note: String?) {
        val index = _uiState.value.editingLineIndex ?: return
        val items = _uiState.value.items
        if (index !in items.indices) return
        val newItems = items.toMutableList().apply { this[index] = this[index].copy(quantity = quantity, note = note) }
        _uiState.update { it.copy(editingLineIndex = null) }
        refreshPreview(newItems)
    }

    fun onRemoveLine(index: Int) {
        val items = _uiState.value.items
        if (index !in items.indices) return
        val newItems = items.toMutableList().apply { removeAt(index) }
        if (newItems.isEmpty()) {
            _uiState.update { it.copy(items = emptyList(), preview = null, cartError = null) }
            return
        }
        refreshPreview(newItems)
    }

    private fun refreshPreview(items: List<OrderItemLineRequest>) {
        viewModelScope.launch {
            _uiState.update { it.copy(isCartLoading = true, cartError = null) }
            restaurantRepository.previewOrder(items)
                .onSuccess { preview ->
                    _uiState.update { it.copy(isCartLoading = false, items = items, preview = preview) }
                }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(isCartLoading = false, cartError = error.message ?: "Error desconocido.")
                    }
                }
        }
    }

    fun onCustomerNameChange(text: String) {
        _uiState.update { it.copy(customerName = text) }
    }

    fun onCustomerDocumentChange(text: String) {
        _uiState.update { it.copy(customerDocument = text) }
    }

    /** Botón "Enviar pedido" — réplica de `RestaurantViewModel.
     * confirm_order`: el pedido nace sin cobrar y aparece automáticamente
     * en Despacho, no hace falta ninguna llamada adicional para "enviarlo". */
    fun onSendOrder() {
        val items = _uiState.value.items
        if (items.isEmpty()) {
            _uiState.update { it.copy(sendError = "Agrega al menos un producto al pedido.") }
            return
        }
        viewModelScope.launch {
            _uiState.update { it.copy(isSending = true, sendError = null) }
            restaurantRepository.createOrder(
                items = items,
                customerName = _uiState.value.customerName.trim().ifEmpty { null },
                customerDocument = _uiState.value.customerDocument.trim().ifEmpty { null },
            ).onSuccess { order ->
                _uiState.update { it.copy(isSending = false, confirmedOrder = order) }
            }.onFailure { error ->
                _uiState.update {
                    it.copy(isSending = false, sendError = error.message ?: "Error desconocido.")
                }
            }
        }
    }

    fun onStartNewOrder() {
        _uiState.update { VendorUiState(isLoadingCatalog = false, products = it.products) }
    }
}
