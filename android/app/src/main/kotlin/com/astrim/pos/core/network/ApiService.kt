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
import com.astrim.pos.core.network.dto.CreateOrderRequest
import com.astrim.pos.core.network.dto.CustomerDto
import com.astrim.pos.core.network.dto.DispatchOrderCardDto
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
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Contrato de la API HTTP del backend ASTRIM (ver API.md). Cada fase futura
 * agrega acá los endpoints que consuma, siempre reflejando exactamente lo
 * que ya documenta API.md, nunca una interpretación propia.
 */
interface ApiService {
    @POST("api/v1/auth/login")
    suspend fun login(@Body request: LoginRequest): LoginResponse

    @GET("api/v1/auth/me")
    suspend fun me(): SessionInfoDto

    @GET("api/v1/categories")
    suspend fun listCategories(): List<CategoryDto>

    @GET("api/v1/products")
    suspend fun listProducts(): List<ProductSummaryDto>

    @GET("api/v1/products/by-barcode/{code}")
    suspend fun getProductByBarcode(@Path("code") code: String): ProductSummaryDto

    @POST("api/v1/sales/drafts")
    suspend fun createSaleDraft(): SaleDraftDto

    @GET("api/v1/sales/drafts/{draftId}")
    suspend fun getSaleDraft(@Path("draftId") draftId: String): SaleDraftDto

    @POST("api/v1/sales/drafts/{draftId}/items")
    suspend fun addSaleItem(
        @Path("draftId") draftId: String,
        @Body request: AddSaleItemRequest,
    ): SaleDraftDto

    @PATCH("api/v1/sales/drafts/{draftId}/items/{itemIndex}")
    suspend fun updateSaleItem(
        @Path("draftId") draftId: String,
        @Path("itemIndex") itemIndex: Int,
        @Body request: UpdateSaleItemRequest,
    ): SaleDraftDto

    @DELETE("api/v1/sales/drafts/{draftId}/items/{itemIndex}")
    suspend fun removeSaleItem(
        @Path("draftId") draftId: String,
        @Path("itemIndex") itemIndex: Int,
    ): SaleDraftDto

    @POST("api/v1/sales/drafts/{draftId}/complete")
    suspend fun completeSaleDraft(
        @Path("draftId") draftId: String,
        @Body request: CompleteSaleRequest,
    ): CompletedSaleDto

    @GET("api/v1/sales/{saleId}")
    suspend fun getSale(@Path("saleId") saleId: Int): CompletedSaleDto

    @GET("api/v1/sales")
    suspend fun listSales(@Query("limit") limit: Int = 50): List<CompletedSaleDto>

    @GET("api/v1/dispatch/orders")
    suspend fun listDispatchOrders(): List<DispatchOrderCardDto>

    @POST("api/v1/dispatch/orders/{orderId}/advance")
    suspend fun advanceDispatchOrder(@Path("orderId") orderId: Int): List<DispatchOrderCardDto>

    @POST("api/v1/dispatch/orders/{orderId}/deliver")
    suspend fun deliverDispatchOrder(@Path("orderId") orderId: Int): List<DispatchOrderCardDto>

    @GET("api/v1/customers")
    suspend fun listCustomers(): List<CustomerDto>

    @POST("api/v1/customers")
    suspend fun createCustomer(@Body request: CreateCustomerRequest): CustomerDto

    @POST("api/v1/customers/{customerId}/payments")
    suspend fun registerCustomerPayment(
        @Path("customerId") customerId: Int,
        @Body request: RegisterCreditPaymentRequest,
    ): CustomerDto

    @GET("api/v1/cash-register/status")
    suspend fun getCashRegisterStatus(): CashRegisterStatusDto

    @POST("api/v1/cash-register/sessions/open")
    suspend fun openCashSession(@Body request: OpenCashSessionRequest): CashSessionDto

    @POST("api/v1/cash-register/sessions/close")
    suspend fun closeCashSession(@Body request: CloseCashSessionRequest): CashSessionDto

    @POST("api/v1/restaurant/orders/preview")
    suspend fun previewOrder(@Body request: OrderPreviewRequest): OrderPreviewDto

    @POST("api/v1/restaurant/orders")
    suspend fun createOrder(@Body request: CreateOrderRequest): OrderDto

    @GET("api/v1/payment-methods/qr")
    suspend fun getQrPaymentConfig(): QrPaymentConfigDto

    @GET("api/v1/payment-methods/nequi")
    suspend fun getNequiPaymentConfig(): NequiPaymentConfigDto

    @GET("api/v1/payment-methods/bre-b")
    suspend fun getBreBPaymentConfig(): BreBPaymentConfigDto
}
