package com.astrim.pos.core.customers

import com.astrim.pos.core.network.ApiClientFactory
import com.astrim.pos.core.network.ApiException
import com.astrim.pos.core.network.ApiService
import com.astrim.pos.core.network.dto.CreateCustomerRequest
import com.astrim.pos.core.network.dto.CustomerDto
import com.astrim.pos.core.network.dto.RegisterCreditPaymentRequest
import com.astrim.pos.core.network.toApiException
import com.astrim.pos.core.session.TokenStore
import java.io.IOException
import retrofit2.HttpException

/**
 * Sin lógica de negocio propia: cada método es una llamada directa a
 * `/api/v1/customers` (ver API.md §3.9). Ni la deuda ni el cupo disponible
 * se calculan acá — el cliente que devuelve cada respuesta ya viene
 * resuelto por `CustomerManagementService`, la misma lógica que usan la
 * pantalla Clientes y el buscador de cliente registrado de Ventas en el
 * escritorio.
 *
 * `apiServiceFactory` sigue el mismo motivo que en los demás repositorios:
 * poder probar esta clase en JVM puro con un [ApiService] falso.
 */
class CustomerRepository(
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

    suspend fun listCustomers(): Result<List<CustomerDto>> = runCatchingApi { it.listCustomers() }

    suspend fun createCustomer(
        fullName: String,
        documentId: String?,
        email: String?,
        phone: String?,
        address: String?,
        creditLimit: String,
    ): Result<CustomerDto> = runCatchingApi {
        it.createCustomer(CreateCustomerRequest(fullName, documentId, email, phone, address, creditLimit))
    }

    suspend fun registerPayment(customerId: Int, amount: String, reference: String?): Result<CustomerDto> =
        runCatchingApi { it.registerCustomerPayment(customerId, RegisterCreditPaymentRequest(amount, reference)) }
}
