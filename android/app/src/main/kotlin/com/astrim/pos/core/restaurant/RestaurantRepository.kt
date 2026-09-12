package com.astrim.pos.core.restaurant

import com.astrim.pos.core.network.ApiClientFactory
import com.astrim.pos.core.network.ApiException
import com.astrim.pos.core.network.ApiService
import com.astrim.pos.core.network.dto.CreateOrderRequest
import com.astrim.pos.core.network.dto.OrderDto
import com.astrim.pos.core.network.dto.OrderItemLineRequest
import com.astrim.pos.core.network.dto.OrderPreviewDto
import com.astrim.pos.core.network.dto.OrderPreviewRequest
import com.astrim.pos.core.network.toApiException
import com.astrim.pos.core.session.TokenStore
import java.io.IOException
import retrofit2.HttpException

/**
 * Sin lógica de negocio propia: cada método es una llamada directa a
 * `/api/v1/restaurant` (ver API.md §3.11). Ni el total ni los impuestos se
 * calculan acá — el pedido en construcción (líneas producto/cantidad/nota)
 * vive en memoria de este cliente, igual que vive en memoria del
 * `ViewModel` Qt del escritorio (`RestaurantViewModel._items`) hasta
 * confirmarlo; el total en vivo siempre viene de `previewOrder`, la misma
 * `SalesService.preview_sale` que ya usa el carrito de Ventas.
 *
 * `apiServiceFactory` sigue el mismo motivo que en los demás repositorios:
 * poder probar esta clase en JVM puro con un [ApiService] falso.
 */
class RestaurantRepository(
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

    suspend fun previewOrder(items: List<OrderItemLineRequest>): Result<OrderPreviewDto> =
        runCatchingApi { it.previewOrder(OrderPreviewRequest(items)) }

    suspend fun createOrder(
        items: List<OrderItemLineRequest>,
        customerName: String?,
        customerDocument: String?,
    ): Result<OrderDto> =
        runCatchingApi {
            it.createOrder(CreateOrderRequest(items, customerName, customerDocument))
        }
}
