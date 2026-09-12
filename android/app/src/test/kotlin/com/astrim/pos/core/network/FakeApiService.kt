package com.astrim.pos.core.network

import com.astrim.pos.core.network.dto.AddSaleItemRequest
import com.astrim.pos.core.network.dto.BreBPaymentConfigDto
import com.astrim.pos.core.network.dto.CashRegisterStatusDto
import com.astrim.pos.core.network.dto.CashSessionDto
import com.astrim.pos.core.network.dto.CategoryDto
import com.astrim.pos.core.network.dto.CloseCashSessionRequest
import com.astrim.pos.core.network.dto.CompleteSaleRequest
import com.astrim.pos.core.network.dto.CompletedSaleDto
import com.astrim.pos.core.network.dto.CreateCustomerRequest
import com.astrim.pos.core.network.dto.CustomerDto
import com.astrim.pos.core.network.dto.DispatchOrderCardDto
import com.astrim.pos.core.network.dto.CreateOrderRequest
import com.astrim.pos.core.network.dto.LoginRequest
import com.astrim.pos.core.network.dto.LoginResponse
import com.astrim.pos.core.network.dto.NequiPaymentConfigDto
import com.astrim.pos.core.network.dto.OpenCashSessionRequest
import com.astrim.pos.core.network.dto.OrderDto
import com.astrim.pos.core.network.dto.OrderPreviewDto
import com.astrim.pos.core.network.dto.OrderPreviewRequest
import com.astrim.pos.core.network.dto.ProductSummaryDto
import com.astrim.pos.core.network.dto.QrPaymentConfigDto
import com.astrim.pos.core.network.dto.RegisterCreditPaymentRequest
import com.astrim.pos.core.network.dto.SaleDraftDto
import com.astrim.pos.core.network.dto.SessionInfoDto
import com.astrim.pos.core.network.dto.UpdateSaleItemRequest

/** Doble de prueba de [ApiService] — nunca toca la red real; cada
 * resultado se configura de antemano por prueba. */
class FakeApiService(
    private val loginResult: Result<LoginResponse>? = null,
    private val meResult: Result<SessionInfoDto>? = null,
    private val categoriesResult: Result<List<CategoryDto>>? = null,
    private val productsResult: Result<List<ProductSummaryDto>>? = null,
    private val barcodeResult: Result<ProductSummaryDto>? = null,
    private val createDraftResult: Result<SaleDraftDto>? = null,
    private val getDraftResult: Result<SaleDraftDto>? = null,
    private val addItemResult: Result<SaleDraftDto>? = null,
    private val updateItemResult: Result<SaleDraftDto>? = null,
    private val removeItemResult: Result<SaleDraftDto>? = null,
    private val completeSaleResult: Result<CompletedSaleDto>? = null,
    private val listDispatchOrdersResult: Result<List<DispatchOrderCardDto>>? = null,
    private val advanceDispatchOrderResult: Result<List<DispatchOrderCardDto>>? = null,
    private val deliverDispatchOrderResult: Result<List<DispatchOrderCardDto>>? = null,
    private val listCustomersResult: Result<List<CustomerDto>>? = null,
    private val createCustomerResult: Result<CustomerDto>? = null,
    private val registerCustomerPaymentResult: Result<CustomerDto>? = null,
    private val cashRegisterStatusResult: Result<CashRegisterStatusDto>? = null,
    private val openCashSessionResult: Result<CashSessionDto>? = null,
    private val closeCashSessionResult: Result<CashSessionDto>? = null,
    private val previewOrderResult: Result<OrderPreviewDto>? = null,
    private val createOrderResult: Result<OrderDto>? = null,
    private val getSaleResult: Result<CompletedSaleDto>? = null,
    private val qrPaymentConfigResult: Result<QrPaymentConfigDto>? = null,
    private val nequiPaymentConfigResult: Result<NequiPaymentConfigDto>? = null,
    private val breBPaymentConfigResult: Result<BreBPaymentConfigDto>? = null,
    private val listSalesResult: Result<List<CompletedSaleDto>>? = null,
) : ApiService {
    var lastLoginRequest: LoginRequest? = null
        private set
    var lastBarcodeQueried: String? = null
        private set
    var lastAddItemDraftId: String? = null
        private set
    var lastAddItemRequest: AddSaleItemRequest? = null
        private set
    var lastUpdateItemDraftId: String? = null
        private set
    var lastUpdateItemIndex: Int? = null
        private set
    var lastUpdateItemRequest: UpdateSaleItemRequest? = null
        private set
    var lastRemoveItemDraftId: String? = null
        private set
    var lastRemoveItemIndex: Int? = null
        private set
    var lastCompleteSaleDraftId: String? = null
        private set
    var lastCompleteSaleRequest: CompleteSaleRequest? = null
        private set
    var lastAdvanceDispatchOrderId: Int? = null
        private set
    var lastDeliverDispatchOrderId: Int? = null
        private set
    var lastCreateCustomerRequest: CreateCustomerRequest? = null
        private set
    var lastRegisterCustomerPaymentCustomerId: Int? = null
        private set
    var lastRegisterCustomerPaymentRequest: RegisterCreditPaymentRequest? = null
        private set
    var lastOpenCashSessionRequest: OpenCashSessionRequest? = null
        private set
    var lastCloseCashSessionRequest: CloseCashSessionRequest? = null
        private set
    var lastPreviewOrderRequest: OrderPreviewRequest? = null
        private set
    var lastCreateOrderRequest: CreateOrderRequest? = null
        private set
    var lastGetSaleId: Int? = null
        private set

    override suspend fun login(request: LoginRequest): LoginResponse {
        lastLoginRequest = request
        return (loginResult ?: error("FakeApiService: loginResult no configurado")).getOrThrow()
    }

    override suspend fun me(): SessionInfoDto {
        return (meResult ?: error("FakeApiService: meResult no configurado")).getOrThrow()
    }

    override suspend fun listCategories(): List<CategoryDto> {
        return (categoriesResult ?: error("FakeApiService: categoriesResult no configurado")).getOrThrow()
    }

    override suspend fun listProducts(): List<ProductSummaryDto> {
        return (productsResult ?: error("FakeApiService: productsResult no configurado")).getOrThrow()
    }

    override suspend fun getProductByBarcode(code: String): ProductSummaryDto {
        lastBarcodeQueried = code
        return (barcodeResult ?: error("FakeApiService: barcodeResult no configurado")).getOrThrow()
    }

    override suspend fun createSaleDraft(): SaleDraftDto {
        return (createDraftResult ?: error("FakeApiService: createDraftResult no configurado")).getOrThrow()
    }

    override suspend fun getSaleDraft(draftId: String): SaleDraftDto {
        return (getDraftResult ?: error("FakeApiService: getDraftResult no configurado")).getOrThrow()
    }

    override suspend fun addSaleItem(draftId: String, request: AddSaleItemRequest): SaleDraftDto {
        lastAddItemDraftId = draftId
        lastAddItemRequest = request
        return (addItemResult ?: error("FakeApiService: addItemResult no configurado")).getOrThrow()
    }

    override suspend fun updateSaleItem(
        draftId: String,
        itemIndex: Int,
        request: UpdateSaleItemRequest,
    ): SaleDraftDto {
        lastUpdateItemDraftId = draftId
        lastUpdateItemIndex = itemIndex
        lastUpdateItemRequest = request
        return (updateItemResult ?: error("FakeApiService: updateItemResult no configurado")).getOrThrow()
    }

    override suspend fun removeSaleItem(draftId: String, itemIndex: Int): SaleDraftDto {
        lastRemoveItemDraftId = draftId
        lastRemoveItemIndex = itemIndex
        return (removeItemResult ?: error("FakeApiService: removeItemResult no configurado")).getOrThrow()
    }

    override suspend fun completeSaleDraft(draftId: String, request: CompleteSaleRequest): CompletedSaleDto {
        lastCompleteSaleDraftId = draftId
        lastCompleteSaleRequest = request
        return (completeSaleResult ?: error("FakeApiService: completeSaleResult no configurado")).getOrThrow()
    }

    override suspend fun getSale(saleId: Int): CompletedSaleDto {
        lastGetSaleId = saleId
        return (getSaleResult ?: error("FakeApiService: getSaleResult no configurado")).getOrThrow()
    }

    override suspend fun listSales(limit: Int): List<CompletedSaleDto> {
        return (listSalesResult ?: error("FakeApiService: listSalesResult no configurado")).getOrThrow()
    }

    override suspend fun listDispatchOrders(): List<DispatchOrderCardDto> {
        return (listDispatchOrdersResult ?: error("FakeApiService: listDispatchOrdersResult no configurado"))
            .getOrThrow()
    }

    override suspend fun advanceDispatchOrder(orderId: Int): List<DispatchOrderCardDto> {
        lastAdvanceDispatchOrderId = orderId
        return (advanceDispatchOrderResult ?: error("FakeApiService: advanceDispatchOrderResult no configurado"))
            .getOrThrow()
    }

    override suspend fun deliverDispatchOrder(orderId: Int): List<DispatchOrderCardDto> {
        lastDeliverDispatchOrderId = orderId
        return (deliverDispatchOrderResult ?: error("FakeApiService: deliverDispatchOrderResult no configurado"))
            .getOrThrow()
    }

    override suspend fun listCustomers(): List<CustomerDto> {
        return (listCustomersResult ?: error("FakeApiService: listCustomersResult no configurado")).getOrThrow()
    }

    override suspend fun createCustomer(request: CreateCustomerRequest): CustomerDto {
        lastCreateCustomerRequest = request
        return (createCustomerResult ?: error("FakeApiService: createCustomerResult no configurado")).getOrThrow()
    }

    override suspend fun registerCustomerPayment(customerId: Int, request: RegisterCreditPaymentRequest): CustomerDto {
        lastRegisterCustomerPaymentCustomerId = customerId
        lastRegisterCustomerPaymentRequest = request
        return (registerCustomerPaymentResult ?: error("FakeApiService: registerCustomerPaymentResult no configurado"))
            .getOrThrow()
    }

    override suspend fun getCashRegisterStatus(): CashRegisterStatusDto {
        return (cashRegisterStatusResult ?: error("FakeApiService: cashRegisterStatusResult no configurado"))
            .getOrThrow()
    }

    override suspend fun openCashSession(request: OpenCashSessionRequest): CashSessionDto {
        lastOpenCashSessionRequest = request
        return (openCashSessionResult ?: error("FakeApiService: openCashSessionResult no configurado")).getOrThrow()
    }

    override suspend fun closeCashSession(request: CloseCashSessionRequest): CashSessionDto {
        lastCloseCashSessionRequest = request
        return (closeCashSessionResult ?: error("FakeApiService: closeCashSessionResult no configurado")).getOrThrow()
    }

    override suspend fun previewOrder(request: OrderPreviewRequest): OrderPreviewDto {
        lastPreviewOrderRequest = request
        return (previewOrderResult ?: error("FakeApiService: previewOrderResult no configurado")).getOrThrow()
    }

    override suspend fun createOrder(request: CreateOrderRequest): OrderDto {
        lastCreateOrderRequest = request
        return (createOrderResult ?: error("FakeApiService: createOrderResult no configurado")).getOrThrow()
    }

    override suspend fun getQrPaymentConfig(): QrPaymentConfigDto {
        return (qrPaymentConfigResult ?: error("FakeApiService: qrPaymentConfigResult no configurado"))
            .getOrThrow()
    }

    override suspend fun getNequiPaymentConfig(): NequiPaymentConfigDto {
        return (nequiPaymentConfigResult ?: error("FakeApiService: nequiPaymentConfigResult no configurado"))
            .getOrThrow()
    }

    override suspend fun getBreBPaymentConfig(): BreBPaymentConfigDto {
        return (breBPaymentConfigResult ?: error("FakeApiService: breBPaymentConfigResult no configurado"))
            .getOrThrow()
    }
}
