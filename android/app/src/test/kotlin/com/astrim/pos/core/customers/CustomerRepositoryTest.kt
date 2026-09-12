package com.astrim.pos.core.customers

import com.astrim.pos.core.network.ApiException
import com.astrim.pos.core.network.FakeApiService
import com.astrim.pos.core.network.dto.CustomerDto
import com.astrim.pos.core.network.httpErrorException
import com.astrim.pos.core.session.FakeTokenStore
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

private fun sampleCustomer(
    id: Int = 7,
    fullName: String = "Juan Pérez",
    currentDebt: String = "0",
) = CustomerDto(
    id = id,
    fullName = fullName,
    documentId = "123456",
    email = null,
    phone = null,
    address = null,
    creditLimit = "100000",
    currentDebt = currentDebt,
    loyaltyPointsBalance = 0,
)

/**
 * Ninguna de estas pruebas toca la red real (ver [FakeApiService]) ni el
 * framework de Android (ver [FakeTokenStore]) — corren en JVM puro, mismo
 * patrón que `DispatchRepositoryTest`/`SalesRepositoryTest`.
 */
class CustomerRepositoryTest {

    @Test
    fun `listCustomers sin servidor configurado devuelve error sin llamar a la API`() = runTest {
        val repository = CustomerRepository(
            FakeTokenStore(),
            apiServiceFactory = { error("no debería construirse un ApiService sin servidor") },
        )

        val result = repository.listCustomers()

        assertTrue(result.isFailure)
    }

    @Test
    fun `listCustomers exitoso devuelve la lista tal cual`() = runTest {
        val customers = listOf(sampleCustomer())
        val api = FakeApiService(listCustomersResult = Result.success(customers))
        val repository = CustomerRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.listCustomers()

        assertTrue(result.isSuccess)
        assertEquals(customers, result.getOrNull())
    }

    @Test
    fun `createCustomer envia los datos y devuelve el cliente creado`() = runTest {
        val created = sampleCustomer(id = 9, fullName = "María Gómez")
        val api = FakeApiService(createCustomerResult = Result.success(created))
        val repository = CustomerRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.createCustomer(
            fullName = "María Gómez",
            documentId = "987654",
            email = null,
            phone = null,
            address = null,
            creditLimit = "50000",
        )

        assertTrue(result.isSuccess)
        assertEquals(created, result.getOrNull())
        assertEquals("María Gómez", api.lastCreateCustomerRequest?.fullName)
        assertEquals("50000", api.lastCreateCustomerRequest?.creditLimit)
    }

    @Test
    fun `createCustomer con datos invalidos devuelve el 422 del backend`() = runTest {
        val api = FakeApiService(
            createCustomerResult = Result.failure(httpErrorException(422, "El nombre completo es obligatorio.")),
        )
        val repository = CustomerRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.createCustomer(
            fullName = "",
            documentId = null,
            email = null,
            phone = null,
            address = null,
            creditLimit = "0",
        )

        assertTrue(result.isFailure)
        assertEquals(422, (result.exceptionOrNull() as ApiException).statusCode)
    }

    @Test
    fun `registerPayment envia el id del cliente y el monto y devuelve el cliente actualizado`() = runTest {
        val updated = sampleCustomer(currentDebt = "0")
        val api = FakeApiService(registerCustomerPaymentResult = Result.success(updated))
        val repository = CustomerRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.registerPayment(customerId = 7, amount = "25000", reference = "Abono")

        assertTrue(result.isSuccess)
        assertEquals(updated, result.getOrNull())
        assertEquals(7, api.lastRegisterCustomerPaymentCustomerId)
        assertEquals("25000", api.lastRegisterCustomerPaymentRequest?.amount)
        assertEquals("Abono", api.lastRegisterCustomerPaymentRequest?.reference)
    }

    @Test
    fun `registerPayment que excede la deuda devuelve el 422 del backend`() = runTest {
        val api = FakeApiService(
            registerCustomerPaymentResult = Result.failure(httpErrorException(422, "El pago excede la deuda actual.")),
        )
        val repository = CustomerRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.registerPayment(customerId = 7, amount = "999999", reference = null)

        assertTrue(result.isFailure)
        assertEquals(422, (result.exceptionOrNull() as ApiException).statusCode)
    }
}
