package com.astrim.pos.core.dispatch

import com.astrim.pos.core.network.ApiClientFactory
import com.astrim.pos.core.network.ApiException
import com.astrim.pos.core.network.ApiService
import com.astrim.pos.core.network.dto.DispatchOrderCardDto
import com.astrim.pos.core.network.toApiException
import com.astrim.pos.core.session.TokenStore
import java.io.IOException
import retrofit2.HttpException

/**
 * Sin lógica de negocio propia: cada método es una llamada directa a
 * `/api/v1/dispatch` (ver API.md §3.7). Ni el paso siguiente del estado
 * de despacho ni qué pedidos aparecen se deciden acá — la cola que
 * devuelve cada respuesta ya viene resuelta por `KitchenService`, la misma
 * lógica que usa la pantalla Despacho del escritorio. Filtros y búsqueda
 * (Todos/Pendientes/.../Pedidos de Ventas) son responsabilidad de la UI,
 * igual que en `kitchen_view.py`.
 *
 * `apiServiceFactory` sigue el mismo motivo que en `SessionRepository`/
 * `CatalogRepository`/`SalesRepository`: poder probar esta clase en JVM
 * puro con un [ApiService] falso, sin tocar la red real.
 */
class DispatchRepository(
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

    suspend fun listOrders(): Result<List<DispatchOrderCardDto>> =
        runCatchingApi { it.listDispatchOrders() }

    suspend fun advanceOrder(orderId: Int): Result<List<DispatchOrderCardDto>> =
        runCatchingApi { it.advanceDispatchOrder(orderId) }

    suspend fun deliverOrder(orderId: Int): Result<List<DispatchOrderCardDto>> =
        runCatchingApi { it.deliverDispatchOrder(orderId) }
}
