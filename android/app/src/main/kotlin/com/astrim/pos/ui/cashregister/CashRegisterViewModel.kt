package com.astrim.pos.ui.cashregister

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.astrim.pos.core.cashregister.CashRegisterRepository
import com.astrim.pos.core.network.dto.CashSessionDto
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class CashRegisterUiState(
    val isLoading: Boolean = true,
    val errorMessage: String? = null,
    val cashRegisterName: String? = null,
    val session: CashSessionDto? = null,
    val openingAmountText: String = "",
    val openError: String? = null,
    val isOpening: Boolean = false,
    val countedAmountText: String = "",
    val closeError: String? = null,
    val isClosing: Boolean = false,
    val lastClosedSession: CashSessionDto? = null,
)

/**
 * Sin lógica de negocio propia: cada acción es una llamada directa a
 * [CashRegisterRepository] (que refleja `/api/v1/cash-register`, ver
 * API.md §3.10). Ni el monto esperado ni la diferencia del arqueo se
 * calculan acá — la sesión que devuelve cada respuesta ya viene resuelta
 * por el backend, igual que `cash_register_view_model.py` del escritorio:
 * ese ViewModel tampoco valida montos negativos por su cuenta, deja que
 * el service lance el error y lo muestra tal cual (`error_occurred`).
 */
class CashRegisterViewModel(private val repository: CashRegisterRepository) : ViewModel() {

    private val _uiState = MutableStateFlow(CashRegisterUiState())
    val uiState: StateFlow<CashRegisterUiState> = _uiState.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            repository.getStatus()
                .onSuccess { status ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            cashRegisterName = status.cashRegister.name,
                            session = status.session,
                        )
                    }
                }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(isLoading = false, errorMessage = error.message ?: "Error desconocido.")
                    }
                }
        }
    }

    fun onOpeningAmountChange(text: String) {
        _uiState.update { it.copy(openingAmountText = text, openError = null) }
    }

    /** Igual que `_ask_amount` del escritorio: el formato del número es
     * lo único que se valida acá — que sea negativo, o que el turno ya
     * esté abierto, lo valida el backend (`CashRegisterService.
     * open_session`) y su mensaje se muestra tal cual. */
    fun onOpenSession() {
        val amount = _uiState.value.openingAmountText.trim()
        if (amount.toBigDecimalOrNull() == null) {
            _uiState.update { it.copy(openError = "El monto debe ser un número válido.") }
            return
        }
        viewModelScope.launch {
            _uiState.update { it.copy(isOpening = true, openError = null) }
            repository.openSession(amount)
                .onSuccess { opened ->
                    _uiState.update {
                        it.copy(
                            isOpening = false,
                            session = opened,
                            openingAmountText = "",
                            lastClosedSession = null,
                        )
                    }
                }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(isOpening = false, openError = error.message ?: "Error desconocido.")
                    }
                }
        }
    }

    fun onCountedAmountChange(text: String) {
        _uiState.update { it.copy(countedAmountText = text, closeError = null) }
    }

    fun onCloseSession() {
        val amount = _uiState.value.countedAmountText.trim()
        if (amount.toBigDecimalOrNull() == null) {
            _uiState.update { it.copy(closeError = "El monto debe ser un número válido.") }
            return
        }
        viewModelScope.launch {
            _uiState.update { it.copy(isClosing = true, closeError = null) }
            repository.closeSession(amount)
                .onSuccess { closed ->
                    _uiState.update {
                        it.copy(
                            isClosing = false,
                            session = null,
                            countedAmountText = "",
                            lastClosedSession = closed,
                        )
                    }
                }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(isClosing = false, closeError = error.message ?: "Error desconocido.")
                    }
                }
        }
    }
}
