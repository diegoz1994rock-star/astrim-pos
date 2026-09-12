package com.astrim.pos.ui.sales

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.astrim.pos.core.catalog.CATALOG_POLL_INTERVAL_MS
import com.astrim.pos.core.catalog.CatalogRepository
import com.astrim.pos.core.customers.CustomerRepository
import com.astrim.pos.core.network.dto.BreBPaymentConfigDto
import com.astrim.pos.core.network.dto.CompletedSaleDto
import com.astrim.pos.core.network.dto.CustomerDto
import com.astrim.pos.core.network.dto.NequiPaymentConfigDto
import com.astrim.pos.core.network.dto.ProductSummaryDto
import com.astrim.pos.core.network.dto.QrPaymentConfigDto
import com.astrim.pos.core.network.dto.SaleDraftDto
import com.astrim.pos.core.network.dto.SalePaymentRequest
import com.astrim.pos.core.paymentmethods.PaymentMethodsRepository
import com.astrim.pos.core.sales.SalesRepository
import com.astrim.pos.ui.catalog.filterCatalog
import com.astrim.pos.ui.customers.filterCustomers
import java.math.BigDecimal
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Mismo subconjunto que `sale_view.py::_SELECTABLE_PAYMENT_METHODS` del
 * escritorio. `CUSTOMER_CREDIT` ("Agregar a la deuda") solo se puede usar
 * con un cliente registrado seleccionado (ver `SalesUiState.availablePaymentMethods`)
 * — mismo criterio que `_on_payment_method_changed` del escritorio. */
enum class PaymentMethodOption(val apiValue: String, val label: String) {
    CASH("cash", "Efectivo"),
    CARD("card", "Tarjeta"),
    QR("qr", "QR"),
    NEQUI("nequi", "Nequi"),
    BRE_B("bre_b", "Bre-B"),
    CUSTOMER_CREDIT("customer_credit", "Agregar a la deuda"),
}

fun paymentMethodLabel(apiValue: String): String =
    PaymentMethodOption.entries.firstOrNull { it.apiValue == apiValue }?.label ?: apiValue

/** QR/Nequi/Bre-B nunca piden un monto tipeado — mismo criterio que
 * `_on_qr_pay_clicked`/`_on_nequi_pay_clicked`/`_on_breb_pay_clicked` del
 * escritorio: siempre muestran la configuración registrada en
 * Administración → Pagos electrónicos y aplican exactamente el saldo
 * pendiente (ver [SalesViewModel.onOpenManualPayment]). */
fun requiresManualPaymentDialog(method: PaymentMethodOption): Boolean =
    method == PaymentMethodOption.QR || method == PaymentMethodOption.NEQUI || method == PaymentMethodOption.BRE_B

data class PendingPayment(
    val method: PaymentMethodOption,
    val amount: BigDecimal,
)

/** Suma pura de los pagos ya agregados — solo para mostrarle al cajero
 * cuánto lleva cargado antes de cobrar; la validación real de que la suma
 * coincida con el total de la venta la hace el backend al completar (ver
 * API.md §4, `422` "el total de pagos no coincide con el total de la venta"). */
fun totalPaid(payments: List<PendingPayment>): BigDecimal = payments.sumOf { it.amount }

/**
 * Réplica exacta de `sale_view.py::_on_add_payment_clicked` del
 * escritorio: nunca se envía al backend más de lo que falta por cobrar
 * (`remaining`) — eso es justo lo que causaba el bug real reportado ("si
 * valió 60000 y pago 100000 no sale devolver 40000... el total de pagos
 * no coincide con el total de la venta"). Devuelve
 * `(montoAplicado, vuelto)`:
 * - Efectivo con sobrepago (`enteredAmount > remaining`): se aplica solo
 *   `remaining` y el resto es vuelto — el cajero ve cuánto devolver, nunca
 *   se lo rechaza el backend.
 * - Cualquier otro medio de pago con sobrepago: se recorta a `remaining`
 *   sin vuelto — mismo criterio que el diálogo de pago manual del
 *   escritorio (QR/Nequi/Bre-B/crédito), que siempre aplica exactamente el
 *   remanente, nunca permite pagar de más.
 * - Sin sobrepago (`enteredAmount <= remaining`, o ya no falta nada por
 *   cobrar): se aplica el monto tal cual, sin vuelto.
 */
fun applyPayment(
    method: PaymentMethodOption,
    enteredAmount: BigDecimal,
    remaining: BigDecimal,
): Pair<BigDecimal, BigDecimal> {
    if (remaining <= BigDecimal.ZERO || enteredAmount <= remaining) {
        return enteredAmount to BigDecimal.ZERO
    }
    return if (method == PaymentMethodOption.CASH) {
        remaining to (enteredAmount - remaining)
    } else {
        remaining to BigDecimal.ZERO
    }
}

data class SalesUiState(
    val isLoadingCatalog: Boolean = true,
    val catalogError: String? = null,
    val products: List<ProductSummaryDto> = emptyList(),
    val searchText: String = "",
    val barcodeText: String = "",
    val barcodeError: String? = null,
    val isSearchingBarcode: Boolean = false,
    val draft: SaleDraftDto? = null,
    val isCartLoading: Boolean = false,
    val cartError: String? = null,
    val editingLineIndex: Int? = null,
    val customerName: String = "",
    val customerDocument: String = "",
    val customers: List<CustomerDto> = emptyList(),
    val customerSearchText: String = "",
    val selectedCustomer: CustomerDto? = null,
    val selectedPaymentMethod: PaymentMethodOption = PaymentMethodOption.CASH,
    val paymentAmountText: String = "",
    val paymentError: String? = null,
    val payments: List<PendingPayment> = emptyList(),
    val changeDue: BigDecimal = BigDecimal.ZERO,
    val manualPaymentMethod: PaymentMethodOption? = null,
    val isLoadingManualPaymentConfig: Boolean = false,
    val manualPaymentQrConfig: QrPaymentConfigDto? = null,
    val manualPaymentNequiConfig: NequiPaymentConfigDto? = null,
    val manualPaymentBreBConfig: BreBPaymentConfigDto? = null,
    val manualPaymentError: String? = null,
    val isCompleting: Boolean = false,
    val completeError: String? = null,
    val completedSale: CompletedSaleDto? = null,
) {
    val filteredProducts: List<ProductSummaryDto>
        get() = if (searchText.isBlank()) emptyList() else filterCatalog(products, categoryId = null, query = searchText)

    val filteredCustomers: List<CustomerDto>
        get() = if (customerSearchText.isBlank()) emptyList() else filterCustomers(customers, customerSearchText)

    /** `CUSTOMER_CREDIT` ("Agregar a la deuda") solo se ofrece con un
     * cliente registrado ya seleccionado — mismo requisito que valida
     * `SalesService.complete_sale` ("Un pago a crédito requiere
     * seleccionar un cliente."), acá solo evita una solicitud condenada a
     * fallar, la validación real sigue siendo del backend. */
    val availablePaymentMethods: List<PaymentMethodOption>
        get() = if (selectedCustomer != null) {
            PaymentMethodOption.entries.toList()
        } else {
            PaymentMethodOption.entries.filter { it != PaymentMethodOption.CUSTOMER_CREDIT }
        }
}

/**
 * Sin lógica de negocio propia: cada acción del cajero es una llamada
 * directa a [SalesRepository] (que a su vez refleja `/api/v1/sales/`, ver
 * API.md §3.5/§3.6) — subtotal/descuentos/impuestos/total/validación de
 * stock siempre vienen ya calculados en la respuesta (`SaleDraftDto`),
 * nunca se recalculan acá. El buscador de productos reutiliza
 * [filterCatalog], el mismo criterio que ya usa el Catálogo (Fase 2).
 */
class SalesViewModel(
    private val catalogRepository: CatalogRepository,
    private val salesRepository: SalesRepository,
    private val customerRepository: CustomerRepository,
    private val paymentMethodsRepository: PaymentMethodsRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(SalesUiState())
    val uiState: StateFlow<SalesUiState> = _uiState.asStateFlow()

    init {
        loadCatalog()
        loadCustomers()
        createDraft()
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
     * sin que el cajero tenga que salir y volver a entrar a Ventas — ver
     * [CATALOG_POLL_INTERVAL_MS]. Un fallo de sondeo se ignora en silencio
     * (mismo criterio que [com.astrim.pos.ui.catalog.CatalogViewModel]):
     * no tiene sentido interrumpir una venta en curso por un hipo de red
     * pasajero en una consulta de fondo.
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

    /** Se carga una vez, igual que el catálogo — la búsqueda de cliente
     * registrado filtra en memoria sobre esta lista (mismo criterio que
     * usa [com.astrim.pos.ui.customers.CustomersScreen]), sin ir al
     * servidor por cada tecla. Si falla, no bloquea el resto de la
     * pantalla: el cajero sigue pudiendo vender sin cliente registrado. */
    private fun loadCustomers() {
        viewModelScope.launch {
            customerRepository.listCustomers()
                .onSuccess { customers -> _uiState.update { it.copy(customers = customers) } }
        }
    }

    private fun createDraft() {
        viewModelScope.launch {
            _uiState.update { it.copy(isCartLoading = true, cartError = null) }
            salesRepository.createDraft()
                .onSuccess { draft -> _uiState.update { it.copy(isCartLoading = false, draft = draft) } }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(isCartLoading = false, cartError = error.message ?: "Error desconocido.")
                    }
                }
        }
    }

    fun onSearchTextChange(text: String) {
        _uiState.update { it.copy(searchText = text) }
    }

    fun onBarcodeTextChange(text: String) {
        _uiState.update { it.copy(barcodeText = text, barcodeError = null) }
    }

    /** Mismo flujo que `_on_scan_entered` del escritorio: escanear (o
     * tipear) un código y Enter agrega directamente ese producto al
     * carrito, sin pasar por el buscador. */
    fun onBarcodeSubmit() {
        val code = _uiState.value.barcodeText.trim()
        if (code.isBlank()) return
        viewModelScope.launch {
            _uiState.update { it.copy(isSearchingBarcode = true, barcodeError = null) }
            catalogRepository.findProductByBarcode(code)
                .onSuccess { product ->
                    _uiState.update { it.copy(isSearchingBarcode = false, barcodeText = "") }
                    addProductToCart(product.id)
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

    fun onAddProduct(product: ProductSummaryDto) {
        _uiState.update { it.copy(searchText = "") }
        addProductToCart(product.id)
    }

    private fun addProductToCart(productId: Int) {
        val draftId = _uiState.value.draft?.draftId ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(isCartLoading = true, cartError = null) }
            salesRepository.addItem(draftId, productId, quantity = "1")
                .onSuccess { draft -> _uiState.update { it.copy(isCartLoading = false, draft = draft) } }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(isCartLoading = false, cartError = error.message ?: "Error desconocido.")
                    }
                }
        }
    }

    fun onEditLine(index: Int) {
        _uiState.update { it.copy(editingLineIndex = index) }
    }

    fun onDismissEditLine() {
        _uiState.update { it.copy(editingLineIndex = null) }
    }

    fun onConfirmEditLine(quantity: String, note: String?) {
        val draftId = _uiState.value.draft?.draftId ?: return
        val index = _uiState.value.editingLineIndex ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(isCartLoading = true, cartError = null) }
            salesRepository.updateItem(draftId, index, quantity, note)
                .onSuccess { draft ->
                    _uiState.update { it.copy(isCartLoading = false, draft = draft, editingLineIndex = null) }
                }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(
                            isCartLoading = false,
                            cartError = error.message ?: "Error desconocido.",
                            editingLineIndex = null,
                        )
                    }
                }
        }
    }

    fun onRemoveLine(index: Int) {
        val draftId = _uiState.value.draft?.draftId ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(isCartLoading = true, cartError = null) }
            salesRepository.removeItem(draftId, index)
                .onSuccess { draft -> _uiState.update { it.copy(isCartLoading = false, draft = draft) } }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(isCartLoading = false, cartError = error.message ?: "Error desconocido.")
                    }
                }
        }
    }

    /** Botones "−"/"+" inline de la tabla de detalle — mismo atajo de un
     * toque que ya usa Vendedor ([com.astrim.pos.ui.vendor.VendorViewModel
     * .onIncrementLine]), acá sobre el carrito persistido en el servidor
     * (`draft_id`) en vez de uno en memoria. Bajar a 0 elimina la línea,
     * igual que `remove_item` del escritorio. */
    fun onIncrementLine(index: Int) {
        val line = _uiState.value.draft?.items?.getOrNull(index) ?: return
        val current = line.quantity.toBigDecimalOrNull() ?: return
        updateLineQuantity(index, (current + BigDecimal.ONE).toPlainString(), note = line.note)
    }

    fun onDecrementLine(index: Int) {
        val line = _uiState.value.draft?.items?.getOrNull(index) ?: return
        val current = line.quantity.toBigDecimalOrNull() ?: return
        val next = current - BigDecimal.ONE
        if (next <= BigDecimal.ZERO) {
            onRemoveLine(index)
        } else {
            updateLineQuantity(index, next.toPlainString(), note = line.note)
        }
    }

    private fun updateLineQuantity(index: Int, quantity: String, note: String?) {
        val draftId = _uiState.value.draft?.draftId ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(isCartLoading = true, cartError = null) }
            salesRepository.updateItem(draftId, index, quantity, note)
                .onSuccess { draft -> _uiState.update { it.copy(isCartLoading = false, draft = draft) } }
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

    fun onCustomerSearchTextChange(text: String) {
        _uiState.update { it.copy(customerSearchText = text) }
    }

    /** Igual que `_apply_registered_customer` del escritorio: elegir un
     * cliente de la búsqueda completa Nombre/Documento (sin pisarlos si el
     * cajero ya los había tipeado a mano) y vacía el buscador. */
    fun onSelectRegisteredCustomer(customer: CustomerDto) {
        _uiState.update {
            it.copy(
                selectedCustomer = customer,
                customerName = customer.fullName,
                customerDocument = customer.documentId ?: it.customerDocument,
                customerSearchText = "",
            )
        }
    }

    fun onClearRegisteredCustomer() {
        _uiState.update {
            val method = if (it.selectedPaymentMethod == PaymentMethodOption.CUSTOMER_CREDIT) {
                PaymentMethodOption.CASH
            } else {
                it.selectedPaymentMethod
            }
            it.copy(selectedCustomer = null, selectedPaymentMethod = method)
        }
    }

    fun onPaymentMethodSelected(method: PaymentMethodOption) {
        _uiState.update { it.copy(selectedPaymentMethod = method, paymentError = null) }
    }

    fun onPaymentAmountChange(text: String) {
        _uiState.update { it.copy(paymentAmountText = text, paymentError = null) }
    }

    fun onAddPayment() {
        val amount = _uiState.value.paymentAmountText.trim().toBigDecimalOrNull()
        if (amount == null || amount <= BigDecimal.ZERO) {
            _uiState.update { it.copy(paymentError = "El monto del pago debe ser un número mayor que cero.") }
            return
        }
        val state = _uiState.value
        val total = state.draft?.total?.toBigDecimalOrNull() ?: BigDecimal.ZERO
        val remaining = total - totalPaid(state.payments)
        val (appliedAmount, change) = applyPayment(state.selectedPaymentMethod, amount, remaining)
        _uiState.update {
            it.copy(
                payments = it.payments + PendingPayment(it.selectedPaymentMethod, appliedAmount),
                paymentAmountText = "",
                paymentError = null,
                changeDue = change,
            )
        }
    }

    fun onRemovePayment(index: Int) {
        _uiState.update { state -> state.copy(payments = state.payments.filterIndexed { i, _ -> i != index }) }
    }

    /** Réplica de `SaleView._open_manual_payment_dialog` del escritorio:
     * antes de abrir el diálogo de QR/Nequi/Bre-B calcula cuánto falta por
     * cobrar y, si ya está todo cobrado, ni siquiera lo abre. Después
     * carga en vivo la configuración registrada en Administración → Pagos
     * electrónicos — nunca un valor fijo en la app (ver API.md §3.12). */
    fun onOpenManualPayment(method: PaymentMethodOption) {
        val state = _uiState.value
        val total = state.draft?.total?.toBigDecimalOrNull() ?: BigDecimal.ZERO
        val remaining = total - totalPaid(state.payments)
        if (remaining <= BigDecimal.ZERO) {
            _uiState.update { it.copy(paymentError = "No hay ningún monto pendiente por cobrar.") }
            return
        }
        _uiState.update {
            it.copy(
                manualPaymentMethod = method,
                isLoadingManualPaymentConfig = true,
                manualPaymentError = null,
                manualPaymentQrConfig = null,
                manualPaymentNequiConfig = null,
                manualPaymentBreBConfig = null,
            )
        }
        viewModelScope.launch {
            when (method) {
                PaymentMethodOption.QR -> paymentMethodsRepository.getQrConfig()
                    .onSuccess { config ->
                        _uiState.update {
                            it.copy(isLoadingManualPaymentConfig = false, manualPaymentQrConfig = config)
                        }
                    }
                    .onFailure { error -> onManualPaymentConfigError(error) }
                PaymentMethodOption.NEQUI -> paymentMethodsRepository.getNequiConfig()
                    .onSuccess { config ->
                        _uiState.update {
                            it.copy(isLoadingManualPaymentConfig = false, manualPaymentNequiConfig = config)
                        }
                    }
                    .onFailure { error -> onManualPaymentConfigError(error) }
                PaymentMethodOption.BRE_B -> paymentMethodsRepository.getBreBConfig()
                    .onSuccess { config ->
                        _uiState.update {
                            it.copy(isLoadingManualPaymentConfig = false, manualPaymentBreBConfig = config)
                        }
                    }
                    .onFailure { error -> onManualPaymentConfigError(error) }
                else -> Unit
            }
        }
    }

    private fun onManualPaymentConfigError(error: Throwable) {
        _uiState.update {
            it.copy(isLoadingManualPaymentConfig = false, manualPaymentError = error.message ?: "Error desconocido.")
        }
    }

    fun onDismissManualPayment() {
        _uiState.update {
            it.copy(
                manualPaymentMethod = null,
                isLoadingManualPaymentConfig = false,
                manualPaymentQrConfig = null,
                manualPaymentNequiConfig = null,
                manualPaymentBreBConfig = null,
                manualPaymentError = null,
            )
        }
    }

    /** Réplica de `SaleView._open_manual_payment_dialog` del escritorio:
     * aplica exactamente el saldo pendiente (nunca un monto tipeado) y, si
     * eso cubre el total, completa la venta de inmediato — mismo
     * comportamiento que tenía `_on_qr_pay_clicked` y equivalentes. */
    fun onConfirmManualPayment() {
        val method = _uiState.value.manualPaymentMethod ?: return
        val state = _uiState.value
        val total = state.draft?.total?.toBigDecimalOrNull() ?: BigDecimal.ZERO
        val remaining = total - totalPaid(state.payments)
        if (remaining <= BigDecimal.ZERO) {
            onDismissManualPayment()
            return
        }
        _uiState.update {
            it.copy(
                payments = it.payments + PendingPayment(method, remaining),
                manualPaymentMethod = null,
                isLoadingManualPaymentConfig = false,
                manualPaymentQrConfig = null,
                manualPaymentNequiConfig = null,
                manualPaymentBreBConfig = null,
                manualPaymentError = null,
                changeDue = BigDecimal.ZERO,
            )
        }
        if (totalPaid(_uiState.value.payments) >= total) {
            onCompleteSale()
        }
    }

    fun onCompleteSale() {
        val draftId = _uiState.value.draft?.draftId ?: return
        val payments = _uiState.value.payments
        viewModelScope.launch {
            _uiState.update { it.copy(isCompleting = true, completeError = null) }
            salesRepository.completeSale(
                draftId = draftId,
                payments = payments.map { SalePaymentRequest(it.method.apiValue, it.amount.toPlainString()) },
                customerId = _uiState.value.selectedCustomer?.id,
                customerName = _uiState.value.customerName.trim().ifEmpty { null },
                customerDocument = _uiState.value.customerDocument.trim().ifEmpty { null },
            ).onSuccess { sale ->
                _uiState.update { it.copy(isCompleting = false, completedSale = sale) }
            }.onFailure { error ->
                _uiState.update {
                    it.copy(isCompleting = false, completeError = error.message ?: "Error desconocido.")
                }
            }
        }
    }

    fun onStartNewSale() {
        _uiState.update {
            SalesUiState(isLoadingCatalog = false, products = it.products, customers = it.customers)
        }
        createDraft()
    }
}
