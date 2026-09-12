package com.astrim.pos.ui.customers

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.astrim.pos.core.customers.CustomerRepository
import com.astrim.pos.core.network.dto.CustomerDto
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Subcadena, sin distinguir mayúsculas/minúsculas, sobre nombre/documento/
 * teléfono/correo — sin equivalente exacto en el escritorio (la pantalla
 * "Clientes" no tiene buscador propio, ver `customers_view.py`), pero mismo
 * criterio que ya usan Catálogo/Despacho para no inventar uno nuevo. */
fun matchesCustomerSearch(customer: CustomerDto, query: String): Boolean {
    val needle = query.trim().lowercase()
    if (needle.isEmpty()) return true
    val haystack = listOfNotNull(customer.fullName, customer.documentId, customer.phone, customer.email)
        .joinToString(" ")
        .lowercase()
    return needle in haystack
}

fun filterCustomers(customers: List<CustomerDto>, query: String): List<CustomerDto> =
    customers.filter { matchesCustomerSearch(it, query) }

data class CustomersUiState(
    val isLoading: Boolean = true,
    val errorMessage: String? = null,
    val customers: List<CustomerDto> = emptyList(),
    val searchText: String = "",
    val selectedCustomerId: Int? = null,
    val showCreateDialog: Boolean = false,
    val newFullName: String = "",
    val newDocumentId: String = "",
    val newEmail: String = "",
    val newPhone: String = "",
    val newAddress: String = "",
    val newCreditLimit: String = "0",
    val createError: String? = null,
    val isCreating: Boolean = false,
    val paymentAmount: String = "",
    val paymentError: String? = null,
    val isRegisteringPayment: Boolean = false,
) {
    val filteredCustomers: List<CustomerDto>
        get() = filterCustomers(customers, searchText)

    val selectedCustomer: CustomerDto?
        get() = customers.firstOrNull { it.id == selectedCustomerId }
}

/**
 * Sin lógica de negocio propia: cada acción es una llamada directa a
 * [CustomerRepository] (que refleja `/api/v1/customers`, ver API.md §3.9).
 * Ni la deuda ni el cupo disponible se calculan acá — el cliente que
 * devuelve cada respuesta ya viene resuelto por el backend.
 */
class CustomersViewModel(private val repository: CustomerRepository) : ViewModel() {

    private val _uiState = MutableStateFlow(CustomersUiState())
    val uiState: StateFlow<CustomersUiState> = _uiState.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            repository.listCustomers()
                .onSuccess { customers -> _uiState.update { it.copy(isLoading = false, customers = customers) } }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(isLoading = false, errorMessage = error.message ?: "Error desconocido.")
                    }
                }
        }
    }

    fun onSearchTextChange(text: String) {
        _uiState.update { it.copy(searchText = text) }
    }

    fun onSelectCustomer(customerId: Int?) {
        _uiState.update { it.copy(selectedCustomerId = customerId, paymentAmount = "", paymentError = null) }
    }

    fun onOpenCreateDialog() {
        _uiState.update {
            it.copy(
                showCreateDialog = true,
                newFullName = "",
                newDocumentId = "",
                newEmail = "",
                newPhone = "",
                newAddress = "",
                newCreditLimit = "0",
                createError = null,
            )
        }
    }

    fun onDismissCreateDialog() {
        _uiState.update { it.copy(showCreateDialog = false) }
    }

    fun onNewFullNameChange(value: String) = _uiState.update { it.copy(newFullName = value, createError = null) }
    fun onNewDocumentIdChange(value: String) = _uiState.update { it.copy(newDocumentId = value) }
    fun onNewEmailChange(value: String) = _uiState.update { it.copy(newEmail = value) }
    fun onNewPhoneChange(value: String) = _uiState.update { it.copy(newPhone = value) }
    fun onNewAddressChange(value: String) = _uiState.update { it.copy(newAddress = value) }
    fun onNewCreditLimitChange(value: String) = _uiState.update { it.copy(newCreditLimit = value, createError = null) }

    fun onCreateCustomer() {
        val current = _uiState.value
        if (current.newFullName.isBlank()) {
            _uiState.update { it.copy(createError = "El nombre completo es obligatorio.") }
            return
        }
        viewModelScope.launch {
            _uiState.update { it.copy(isCreating = true, createError = null) }
            repository.createCustomer(
                fullName = current.newFullName.trim(),
                documentId = current.newDocumentId.trim().ifEmpty { null },
                email = current.newEmail.trim().ifEmpty { null },
                phone = current.newPhone.trim().ifEmpty { null },
                address = current.newAddress.trim().ifEmpty { null },
                creditLimit = current.newCreditLimit.trim().ifEmpty { "0" },
            ).onSuccess { customer ->
                _uiState.update {
                    it.copy(isCreating = false, showCreateDialog = false, customers = it.customers + customer)
                }
            }.onFailure { error ->
                _uiState.update {
                    it.copy(isCreating = false, createError = error.message ?: "Error desconocido.")
                }
            }
        }
    }

    fun onPaymentAmountChange(value: String) {
        _uiState.update { it.copy(paymentAmount = value, paymentError = null) }
    }

    fun onRegisterPayment() {
        val customerId = _uiState.value.selectedCustomerId ?: return
        val amount = _uiState.value.paymentAmount.trim()
        if (amount.toBigDecimalOrNull() == null || amount.toBigDecimal().signum() <= 0) {
            _uiState.update { it.copy(paymentError = "El monto debe ser un número mayor que cero.") }
            return
        }
        viewModelScope.launch {
            _uiState.update { it.copy(isRegisteringPayment = true, paymentError = null) }
            repository.registerPayment(customerId, amount, reference = null)
                .onSuccess { updated ->
                    _uiState.update { state ->
                        state.copy(
                            isRegisteringPayment = false,
                            paymentAmount = "",
                            customers = state.customers.map { if (it.id == updated.id) updated else it },
                        )
                    }
                }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(isRegisteringPayment = false, paymentError = error.message ?: "Error desconocido.")
                    }
                }
        }
    }
}
