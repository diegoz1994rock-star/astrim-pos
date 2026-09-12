package com.astrim.pos.ui.saleshistory

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.astrim.pos.core.network.dto.CompletedSaleDto
import com.astrim.pos.core.sales.SalesRepository
import com.astrim.pos.ui.sales.paymentMethodLabel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SalesHistoryUiState(
    val isLoading: Boolean = true,
    val errorMessage: String? = null,
    val sales: List<CompletedSaleDto> = emptyList(),
)

/** Réplica exacta de `paymentMethodSummary` de `sales_history_view_model.py`
 * del escritorio: los métodos de pago de una venta, unidos con " + " (pago
 * mixto), o "No registrado" si por alguna razón no tiene ninguno. */
fun paymentMethodSummary(sale: CompletedSaleDto): String {
    if (sale.payments.isEmpty()) return "No registrado"
    return sale.payments.joinToString(" + ") { paymentMethodLabel(it.paymentMethod) }
}

/**
 * Historial de ventas (botón "Historial" de Ventas) — réplica de solo
 * lectura de `SalesHistoryView` del escritorio: lista de ventas recientes
 * (`GET /sales`, API.md §3.6), sin filtros de fecha/cliente ni paginación
 * real, igual que el escritorio. Anular venta y generar factura siguen
 * siendo exclusivos del escritorio, no expuestos acá.
 */
class SalesHistoryViewModel(private val salesRepository: SalesRepository) : ViewModel() {

    private val _uiState = MutableStateFlow(SalesHistoryUiState())
    val uiState: StateFlow<SalesHistoryUiState> = _uiState.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            salesRepository.listSales()
                .onSuccess { sales -> _uiState.update { it.copy(isLoading = false, sales = sales) } }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(isLoading = false, errorMessage = error.message ?: "Error desconocido.")
                    }
                }
        }
    }
}
