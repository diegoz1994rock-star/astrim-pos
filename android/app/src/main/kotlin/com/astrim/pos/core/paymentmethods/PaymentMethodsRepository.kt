package com.astrim.pos.core.paymentmethods

import com.astrim.pos.core.network.ApiClientFactory
import com.astrim.pos.core.network.ApiException
import com.astrim.pos.core.network.ApiService
import com.astrim.pos.core.network.dto.BreBPaymentConfigDto
import com.astrim.pos.core.network.dto.NequiPaymentConfigDto
import com.astrim.pos.core.network.dto.QrPaymentConfigDto
import com.astrim.pos.core.network.toApiException
import com.astrim.pos.core.session.TokenStore
import java.io.IOException
import retrofit2.HttpException

/**
 * Sin lógica de negocio propia: cada método es una llamada directa a
 * `/api/v1/payment-methods` (ver API.md §3.12) — espejo exacto de la
 * configuración de QR/Nequi/Bre-B que ya administra el escritorio.
 * Un `409` (`ApiException.statusCode`) significa que el administrador no
 * configuró ningún método de ese tipo — nunca un valor inventado.
 *
 * `apiServiceFactory` sigue el mismo motivo que en los demás repositorios:
 * poder probar esta clase en JVM puro con un [ApiService] falso.
 */
class PaymentMethodsRepository(
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

    suspend fun getQrConfig(): Result<QrPaymentConfigDto> = runCatchingApi { it.getQrPaymentConfig() }

    suspend fun getNequiConfig(): Result<NequiPaymentConfigDto> =
        runCatchingApi { it.getNequiPaymentConfig() }

    suspend fun getBreBConfig(): Result<BreBPaymentConfigDto> =
        runCatchingApi { it.getBreBPaymentConfig() }

    /** URL completa (con token cargado vía [com.astrim.pos.core.network.AuthInterceptor]
     * en el cliente HTTP de imágenes, ver [com.astrim.pos.core.AppContainer.productImageLoader])
     * para pedir la imagen de un QR — `null` si no hay servidor configurado. */
    fun qrImageUrl(configId: Int): String? {
        val serverUrl = tokenStore.getServerUrl() ?: return null
        return "${serverUrl}api/v1/payment-methods/qr/$configId/image"
    }
}
