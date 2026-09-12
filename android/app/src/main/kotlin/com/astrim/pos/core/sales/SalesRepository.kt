package com.astrim.pos.core.sales

import com.astrim.pos.core.network.ApiClientFactory
import com.astrim.pos.core.network.ApiException
import com.astrim.pos.core.network.ApiService
import com.astrim.pos.core.network.dto.AddSaleItemRequest
import com.astrim.pos.core.network.dto.CompleteSaleRequest
import com.astrim.pos.core.network.dto.CompletedSaleDto
import com.astrim.pos.core.network.dto.SaleDraftDto
import com.astrim.pos.core.network.dto.SalePaymentRequest
import com.astrim.pos.core.network.dto.UpdateSaleItemRequest
import com.astrim.pos.core.network.toApiException
import com.astrim.pos.core.session.TokenStore
import java.io.IOException
import retrofit2.HttpException

/**
 * Sin lógica de negocio propia: cada método es una llamada directa a
 * `/api/v1/sales/` (ver API.md §3.5/§3.6). Ni subtotal, ni descuentos, ni
 * impuestos, ni total, ni validación de stock se calculan acá — el carrito
 * que devuelve cada respuesta (`SaleDraftDto`) ya viene recalculado por
 * `SalesService.preview_sale` en el backend, la misma función que usa el
 * carrito del escritorio.
 *
 * `apiServiceFactory` sigue el mismo motivo que en `SessionRepository`/
 * `CatalogRepository`: poder probar esta clase en JVM puro con un
 * [ApiService] falso, sin tocar la red real.
 */
class SalesRepository(
    private val tokenStore: TokenStore,
    private val apiServiceFactory: (baseUrl: String) -> ApiService = { baseUrl ->
        ApiClientFactory.create(baseUrl) { tokenStore.getToken() }
    },
) {
    private fun currentApi(): Result<ApiService> {
        val serverUrl = tokenStore.getServerUrl()
            ?: return Result.failure(
                ApiException(statusCode = 0, message = "No hay una sesión activa con un servidor configurado."),
            )
        return Result.success(apiServiceFactory(serverUrl))
    }

    private suspend fun <T> runCatchingApi(block: suspend (ApiService) -> T): Result<T> {
        val api = currentApi().getOrElse { return Result.failure(it) }
        return try {
            Result.success(block(api))
        } catch (e: HttpException) {
            Result.failure(e.toApiException())
        } catch (e: IOException) {
            Result.failure(
                ApiException(statusCode = 0, message = "No se pudo conectar con el servidor. Verificá la red."),
            )
        }
    }

    suspend fun createDraft(): Result<SaleDraftDto> = runCatchingApi { it.createSaleDraft() }

    suspend fun getDraft(draftId: String): Result<SaleDraftDto> =
        runCatchingApi { it.getSaleDraft(draftId) }

    suspend fun addItem(draftId: String, productId: Int, quantity: String, note: String? = null): Result<SaleDraftDto> =
        runCatchingApi { it.addSaleItem(draftId, AddSaleItemRequest(productId, quantity, note)) }

    suspend fun updateItem(draftId: String, itemIndex: Int, quantity: String, note: String?): Result<SaleDraftDto> =
        runCatchingApi { it.updateSaleItem(draftId, itemIndex, UpdateSaleItemRequest(quantity, note)) }

    suspend fun removeItem(draftId: String, itemIndex: Int): Result<SaleDraftDto> =
        runCatchingApi { it.removeSaleItem(draftId, itemIndex) }

    suspend fun completeSale(
        draftId: String,
        payments: List<SalePaymentRequest>,
        customerId: Int?,
        customerName: String?,
        customerDocument: String?,
    ): Result<CompletedSaleDto> =
        runCatchingApi {
            it.completeSaleDraft(
                draftId,
                CompleteSaleRequest(
                    payments = payments,
                    customerId = customerId,
                    customerName = customerName,
                    customerDocument = customerDocument,
                ),
            )
        }

    /** Réplica de `GET /sales/{sale_id}` (API.md §3.6) — usado por
     * Despacho para mostrar el precio/pago real de un pedido ya cobrado
     * (`DispatchOrderCardDto.saleId`), sin duplicar ese cálculo. Requiere
     * el permiso `sales.create`, no necesariamente el mismo que ve
     * Despacho (`kitchen.manage`) — un `403` acá es un caso esperado, no
     * un error de la app. */
    suspend fun getSale(saleId: Int): Result<CompletedSaleDto> = runCatchingApi { it.getSale(saleId) }

    /** Réplica de `GET /sales` (API.md §3.6) — historial de ventas
     * recientes, botón "Historial" de Ventas. Solo lectura: anular venta y
     * generar factura siguen siendo exclusivos del escritorio. */
    suspend fun listSales(limit: Int = 50): Result<List<CompletedSaleDto>> =
        runCatchingApi { it.listSales(limit) }
}
