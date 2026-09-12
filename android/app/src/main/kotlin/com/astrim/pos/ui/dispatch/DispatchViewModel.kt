package com.astrim.pos.ui.dispatch

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.astrim.pos.core.dispatch.DispatchRepository
import com.astrim.pos.core.network.dto.CompletedSaleDto
import com.astrim.pos.core.network.dto.DispatchOrderCardDto
import com.astrim.pos.core.sales.SalesRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Mismos filtros que `kitchen_view.py::_FILTERS` del escritorio, en el
 * mismo orden. */
enum class DispatchFilter(val label: String) {
    ALL("Todos"),
    PENDING("Pendientes"),
    PREPARING("En preparación"),
    DELIVERED("Entregados"),
    PAID("Pagados"),
    UNPAID("No pagados"),
    FROM_VENDEDOR("Pedidos del Vendedor"),
    FROM_VENTAS("Pedidos de Ventas"),
}

/** Mismo criterio que `kitchen_view.py::_matches_filter`. */
fun matchesDispatchFilter(card: DispatchOrderCardDto, filter: DispatchFilter): Boolean = when (filter) {
    DispatchFilter.ALL -> true
    DispatchFilter.PENDING -> card.dispatchStatus == "pending"
    DispatchFilter.PREPARING -> card.dispatchStatus == "preparing" || card.dispatchStatus == "ready"
    DispatchFilter.DELIVERED -> card.dispatchStatus == "delivered"
    DispatchFilter.PAID -> card.isPaid
    DispatchFilter.UNPAID -> !card.isPaid
    DispatchFilter.FROM_VENDEDOR -> card.origin == "vendedor"
    DispatchFilter.FROM_VENTAS -> card.origin == "ventas"
}

/** Mismo criterio que `kitchen_view.py::_matches_search`: subcadena, sin
 * distinguir mayúsculas/minúsculas, sobre cliente/documento/pedido/caja/
 * empleados. */
fun matchesDispatchSearch(card: DispatchOrderCardDto, query: String): Boolean {
    val needle = query.trim().lowercase()
    if (needle.isEmpty()) return true
    val haystack = listOfNotNull(
        card.customerName,
        card.customerDocument,
        card.orderId.toString().padStart(6, '0'),
        card.cajaName,
        card.createdByUserName,
        card.dispatchedByUserName,
    ).joinToString(" ").lowercase()
    return needle in haystack
}

fun filterDispatchOrders(
    orders: List<DispatchOrderCardDto>,
    filter: DispatchFilter,
    query: String,
): List<DispatchOrderCardDto> =
    orders.filter { matchesDispatchFilter(it, filter) && matchesDispatchSearch(it, query) }

/** Mismas etiquetas que `kitchen_view.py::_DISPATCH_STATUS_LABELS`/
 * `_ORIGIN_LABELS`. */
fun dispatchStatusLabel(status: String): String = when (status) {
    "pending" -> "Pendiente"
    "preparing", "ready" -> "En preparación"
    "delivered" -> "Entregado"
    "cancelled" -> "Anulado"
    "archived" -> "Archivado"
    else -> status
}

fun dispatchOriginLabel(origin: String): String = when (origin) {
    "vendedor" -> "Vendedor"
    "ventas" -> "Ventas"
    else -> origin
}

data class DispatchUiState(
    val isLoading: Boolean = true,
    val errorMessage: String? = null,
    val orders: List<DispatchOrderCardDto> = emptyList(),
    val activeFilter: DispatchFilter = DispatchFilter.ALL,
    val searchText: String = "",
    val selectedOrderId: Int? = null,
    val detailOrderId: Int? = null,
    val isActing: Boolean = false,
    val actionError: String? = null,
    val isLoadingSaleDetail: Boolean = false,
    val saleDetail: CompletedSaleDto? = null,
    val saleDetailError: String? = null,
) {
    val filteredOrders: List<DispatchOrderCardDto>
        get() = filterDispatchOrders(orders, activeFilter, searchText)
}

/**
 * Sin lógica de negocio propia: cada acción es una llamada directa a
 * [DispatchRepository] (que refleja `/api/v1/dispatch`, ver API.md §3.7).
 * Ningún estado de despacho se calcula acá — cada respuesta ya trae la cola
 * recargada por el backend. El filtrado/búsqueda reutiliza el mismo
 * criterio que `kitchen_view.py`, aplicado en memoria sobre la cola ya
 * cargada, igual que el escritorio.
 *
 * El detalle de un pedido ya cobrado (`card.saleId != null`) reutiliza
 * [SalesRepository.getSale] para mostrar precio/impuestos/total/método de
 * pago reales — ni ese cálculo ni el de la venta se duplican acá. Un
 * pedido sin cobrar (`saleId == null`, el caso normal de Vendedor antes de
 * pasar por Caja) no tiene ese precio todavía en ningún lado, ni en el
 * backend ni en el escritorio — el detalle simplemente no lo pide.
 */
class DispatchViewModel(
    private val repository: DispatchRepository,
    private val salesRepository: SalesRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(DispatchUiState())
    val uiState: StateFlow<DispatchUiState> = _uiState.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            repository.listOrders()
                .onSuccess { orders -> _uiState.update { it.copy(isLoading = false, orders = orders) } }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(isLoading = false, errorMessage = error.message ?: "Error desconocido.")
                    }
                }
        }
    }

    fun onFilterSelected(filter: DispatchFilter) {
        _uiState.update { it.copy(activeFilter = filter) }
    }

    fun onSearchTextChange(text: String) {
        _uiState.update { it.copy(searchText = text) }
    }

    /** Un tap selecciona/deselecciona la tarjeta (para "Siguiente proceso") —
     * equivalente táctil del clic simple del escritorio. */
    fun onSelectOrder(orderId: Int) {
        _uiState.update {
            it.copy(selectedOrderId = if (it.selectedOrderId == orderId) null else orderId)
        }
    }

    /** Abre el detalle — equivalente táctil del doble clic del escritorio.
     * Si el pedido ya tiene una venta asociada (`saleId != null`), pide
     * su precio/pago real; si no la tiene, no hay nada que pedir (ver
     * docstring de la clase). */
    fun onOpenDetail(orderId: Int) {
        _uiState.update {
            it.copy(detailOrderId = orderId, saleDetail = null, saleDetailError = null)
        }
        val saleId = _uiState.value.orders.firstOrNull { it.orderId == orderId }?.saleId ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(isLoadingSaleDetail = true) }
            salesRepository.getSale(saleId)
                .onSuccess { sale -> _uiState.update { it.copy(isLoadingSaleDetail = false, saleDetail = sale) } }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(
                            isLoadingSaleDetail = false,
                            saleDetailError = error.message ?: "Error desconocido.",
                        )
                    }
                }
        }
    }

    fun onDismissDetail() {
        _uiState.update {
            it.copy(
                detailOrderId = null,
                saleDetail = null,
                saleDetailError = null,
                isLoadingSaleDetail = false,
            )
        }
    }

    /** Botón "Siguiente proceso" sobre la tarjeta seleccionada. */
    fun onAdvanceSelected() {
        val orderId = _uiState.value.selectedOrderId ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(isActing = true, actionError = null) }
            repository.advanceOrder(orderId)
                .onSuccess { orders ->
                    _uiState.update { it.copy(isActing = false, orders = orders, selectedOrderId = null) }
                }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(isActing = false, actionError = error.message ?: "Error desconocido.")
                    }
                }
        }
    }

    /** Botón "Marcar como entregado" del detalle. */
    fun onDeliverOrder(orderId: Int) {
        viewModelScope.launch {
            _uiState.update { it.copy(isActing = true, actionError = null, detailOrderId = null) }
            repository.deliverOrder(orderId)
                .onSuccess { orders -> _uiState.update { it.copy(isActing = false, orders = orders) } }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(isActing = false, actionError = error.message ?: "Error desconocido.")
                    }
                }
        }
    }
}
