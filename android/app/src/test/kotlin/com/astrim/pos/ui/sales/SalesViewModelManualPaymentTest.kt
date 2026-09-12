package com.astrim.pos.ui.sales

import com.astrim.pos.core.catalog.CatalogRepository
import com.astrim.pos.core.customers.CustomerRepository
import com.astrim.pos.core.network.FakeApiService
import com.astrim.pos.core.network.httpErrorException
import com.astrim.pos.core.network.dto.CategoryDto
import com.astrim.pos.core.network.dto.CompletedSaleDto
import com.astrim.pos.core.network.dto.CustomerDto
import com.astrim.pos.core.network.dto.NequiPaymentConfigDto
import com.astrim.pos.core.network.dto.ProductSummaryDto
import com.astrim.pos.core.network.dto.QrPaymentConfigDto
import com.astrim.pos.core.network.dto.SaleDraftDto
import com.astrim.pos.core.paymentmethods.PaymentMethodsRepository
import com.astrim.pos.core.sales.SalesRepository
import com.astrim.pos.core.session.FakeTokenStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

private fun emptyDraft(total: String) = SaleDraftDto(
    draftId = "draft-1",
    subtotal = total,
    discountTotal = "0",
    taxTotal = "0",
    total = total,
    items = emptyList(),
)

private fun completedSale() = CompletedSaleDto(
    id = 1,
    status = "completed",
    saleType = "direct",
    customerId = null,
    subtotal = "60000",
    discountTotal = "0",
    taxTotal = "0",
    total = "60000",
    createdAt = "2026-07-30T10:00:00Z",
    createdByUserId = 1,
    cashSessionId = 1,
    customerName = null,
    customerDocument = null,
    items = emptyList(),
    payments = emptyList(),
)

/**
 * Réplica de `SaleView._open_manual_payment_dialog` del escritorio: el
 * diálogo de QR/Nequi/Bre-B siempre muestra la configuración registrada en
 * Administración → Pagos electrónicos (nunca un valor fijo en la app) y,
 * al confirmar, aplica exactamente el saldo pendiente — nunca un monto
 * tipeado por el cajero (ver API.md §3.12).
 */
@OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
class SalesViewModelManualPaymentTest {

    @Before
    fun setMainDispatcher() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
    }

    @After
    fun resetMainDispatcher() {
        Dispatchers.resetMain()
    }

    private fun buildViewModel(api: FakeApiService): SalesViewModel {
        val tokenStore = FakeTokenStore(serverUrl = "http://server/", token = "tok")
        return SalesViewModel(
            CatalogRepository(tokenStore, apiServiceFactory = { api }),
            SalesRepository(tokenStore, apiServiceFactory = { api }),
            CustomerRepository(tokenStore, apiServiceFactory = { api }),
            PaymentMethodsRepository(tokenStore, apiServiceFactory = { api }),
        )
    }

    @Test
    fun `abrir el pago con QR carga la configuracion registrada en el escritorio`() = runTest {
        val api = FakeApiService(
            categoriesResult = Result.success(emptyList<CategoryDto>()),
            productsResult = Result.success(emptyList<ProductSummaryDto>()),
            listCustomersResult = Result.success(emptyList<CustomerDto>()),
            createDraftResult = Result.success(emptyDraft("60000")),
            qrPaymentConfigResult = Result.success(QrPaymentConfigDto(id = 3, name = "QR Bancolombia", hasImage = true)),
        )
        val viewModel = buildViewModel(api)

        viewModel.onOpenManualPayment(PaymentMethodOption.QR)

        val state = viewModel.uiState.value
        assertEquals(PaymentMethodOption.QR, state.manualPaymentMethod)
        assertEquals("QR Bancolombia", state.manualPaymentQrConfig?.name)
        assertNull(state.manualPaymentError)
    }

    @Test
    fun `abrir el pago manual sin nada pendiente por cobrar no abre el dialogo`() = runTest {
        val api = FakeApiService(
            categoriesResult = Result.success(emptyList<CategoryDto>()),
            productsResult = Result.success(emptyList<ProductSummaryDto>()),
            listCustomersResult = Result.success(emptyList<CustomerDto>()),
            createDraftResult = Result.success(emptyDraft("0")),
        )
        val viewModel = buildViewModel(api)

        viewModel.onOpenManualPayment(PaymentMethodOption.QR)

        val state = viewModel.uiState.value
        assertNull(state.manualPaymentMethod)
        assertEquals("No hay ningún monto pendiente por cobrar.", state.paymentError)
    }

    @Test
    fun `un metodo sin configurar en el escritorio muestra el error real del backend`() = runTest {
        val api = FakeApiService(
            categoriesResult = Result.success(emptyList<CategoryDto>()),
            productsResult = Result.success(emptyList<ProductSummaryDto>()),
            listCustomersResult = Result.success(emptyList<CustomerDto>()),
            createDraftResult = Result.success(emptyDraft("60000")),
            nequiPaymentConfigResult = Result.failure(
                httpErrorException(409, "No hay un número de Nequi configurado."),
            ),
        )
        val viewModel = buildViewModel(api)

        viewModel.onOpenManualPayment(PaymentMethodOption.NEQUI)

        val state = viewModel.uiState.value
        assertEquals("No hay un número de Nequi configurado.", state.manualPaymentError)
        assertNull(state.manualPaymentNequiConfig)
    }

    @Test
    fun `confirmar el pago con QR aplica todo el saldo pendiente y cobra la venta`() = runTest {
        val api = FakeApiService(
            categoriesResult = Result.success(emptyList<CategoryDto>()),
            productsResult = Result.success(emptyList<ProductSummaryDto>()),
            listCustomersResult = Result.success(emptyList<CustomerDto>()),
            createDraftResult = Result.success(emptyDraft("60000")),
            qrPaymentConfigResult = Result.success(QrPaymentConfigDto(id = 3, name = "QR Bancolombia", hasImage = true)),
            completeSaleResult = Result.success(completedSale()),
        )
        val viewModel = buildViewModel(api)
        viewModel.onOpenManualPayment(PaymentMethodOption.QR)

        viewModel.onConfirmManualPayment()

        val state = viewModel.uiState.value
        assertNull(state.manualPaymentMethod)
        assertEquals(1, state.payments.size)
        assertEquals(PaymentMethodOption.QR, state.payments[0].method)
        assertEquals(0, java.math.BigDecimal("60000").compareTo(state.payments[0].amount))
        assertTrue(state.completedSale != null)
        assertEquals("qr", api.lastCompleteSaleRequest?.payments?.single()?.paymentMethod)
    }
}
