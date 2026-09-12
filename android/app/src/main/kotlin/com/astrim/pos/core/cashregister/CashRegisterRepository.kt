package com.astrim.pos.core.cashregister

import com.astrim.pos.core.network.ApiClientFactory
import com.astrim.pos.core.network.ApiException
import com.astrim.pos.core.network.ApiService
import com.astrim.pos.core.network.dto.CashRegisterStatusDto
import com.astrim.pos.core.network.dto.CashSessionDto
import com.astrim.pos.core.network.dto.CloseCashSessionRequest
import com.astrim.pos.core.network.dto.OpenCashSessionRequest
import com.astrim.pos.core.network.toApiException
import com.astrim.pos.core.session.TokenStore
import java.io.IOException
import retrofit2.HttpException

/**
 * Sin lógica de negocio propia: cada método es una llamada directa a
 * `/api/v1/cash-register` (ver API.md §3.10). Ni el monto esperado ni la
 * diferencia del arqueo se calculan acá — la sesión que devuelve cada
 * respuesta ya viene resuelta por `CashRegisterService`, la misma lógica
 * que usa la pantalla "Caja" del escritorio.
 *
 * `apiServiceFactory` sigue el mismo motivo que en los demás repositorios:
 * poder probar esta clase en JVM puro con un [ApiService] falso.
 */
class CashRegisterRepository(
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

    suspend fun getStatus(): Result<CashRegisterStatusDto> = runCatchingApi { it.getCashRegisterStatus() }

    suspend fun openSession(openingAmount: String): Result<CashSessionDto> =
        runCatchingApi { it.openCashSession(OpenCashSessionRequest(openingAmount)) }

    suspend fun closeSession(countedAmount: String): Result<CashSessionDto> =
        runCatchingApi { it.closeCashSession(CloseCashSessionRequest(countedAmount)) }
}
