package com.astrim.pos.core.cashregister

import com.astrim.pos.core.network.ApiException
import com.astrim.pos.core.network.FakeApiService
import com.astrim.pos.core.network.dto.CashRegisterDto
import com.astrim.pos.core.network.dto.CashRegisterStatusDto
import com.astrim.pos.core.network.dto.CashSessionDto
import com.astrim.pos.core.network.httpErrorException
import com.astrim.pos.core.session.FakeTokenStore
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

private fun sampleRegister(id: Int = 1, name: String = "Caja Principal") = CashRegisterDto(
    id = id,
    name = name,
    location = null,
    isActive = true,
)

private fun sampleSession(status: String = "open") = CashSessionDto(
    id = 4,
    cashRegisterId = 1,
    cashRegisterName = "Caja Principal",
    status = status,
    openedByUserId = 7,
    openedAt = "2026-07-25T09:00:00Z",
    openingAmount = "50000",
    closedAt = if (status == "closed") "2026-07-25T18:00:00Z" else null,
    closingAmount = if (status == "closed") "49000" else null,
    expectedAmount = if (status == "closed") "50000" else null,
    difference = if (status == "closed") "-1000" else null,
)

/**
 * Ninguna de estas pruebas toca la red real (ver [FakeApiService]) ni el
 * framework de Android (ver [FakeTokenStore]) — corren en JVM puro, mismo
 * patrón que `CustomerRepositoryTest`/`DispatchRepositoryTest`.
 */
class CashRegisterRepositoryTest {

    @Test
    fun `getStatus sin servidor configurado devuelve error sin llamar a la API`() = runTest {
        val repository = CashRegisterRepository(
            FakeTokenStore(),
            apiServiceFactory = { error("no debería construirse un ApiService sin servidor") },
        )

        val result = repository.getStatus()

        assertTrue(result.isFailure)
    }

    @Test
    fun `getStatus exitoso devuelve la caja y la sesion tal cual`() = runTest {
        val status = CashRegisterStatusDto(cashRegister = sampleRegister(), session = sampleSession())
        val api = FakeApiService(cashRegisterStatusResult = Result.success(status))
        val repository = CashRegisterRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.getStatus()

        assertTrue(result.isSuccess)
        assertEquals(status, result.getOrNull())
    }

    @Test
    fun `getStatus sin turno abierto devuelve session nula`() = runTest {
        val status = CashRegisterStatusDto(cashRegister = sampleRegister(), session = null)
        val api = FakeApiService(cashRegisterStatusResult = Result.success(status))
        val repository = CashRegisterRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.getStatus()

        assertTrue(result.isSuccess)
        assertNull(result.getOrNull()?.session)
    }

    @Test
    fun `getStatus sin permiso devuelve el 403 del backend`() = runTest {
        val api = FakeApiService(
            cashRegisterStatusResult = Result.failure(httpErrorException(403, "No tienes permiso para esta acción.")),
        )
        val repository = CashRegisterRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.getStatus()

        assertTrue(result.isFailure)
        assertEquals(403, (result.exceptionOrNull() as ApiException).statusCode)
    }

    @Test
    fun `openSession envia el monto de apertura y devuelve la sesion abierta`() = runTest {
        val session = sampleSession()
        val api = FakeApiService(openCashSessionResult = Result.success(session))
        val repository = CashRegisterRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.openSession("50000")

        assertTrue(result.isSuccess)
        assertEquals(session, result.getOrNull())
        assertEquals("50000", api.lastOpenCashSessionRequest?.openingAmount)
    }

    @Test
    fun `openSession con un turno ya abierto devuelve el 422 del backend`() = runTest {
        val api = FakeApiService(
            openCashSessionResult = Result.failure(
                httpErrorException(422, "El punto de caja 'Caja Principal' ya tiene un turno abierto."),
            ),
        )
        val repository = CashRegisterRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.openSession("50000")

        assertTrue(result.isFailure)
        assertEquals(422, (result.exceptionOrNull() as ApiException).statusCode)
    }

    @Test
    fun `closeSession envia el monto contado y devuelve la sesion cerrada con la diferencia`() = runTest {
        val closed = sampleSession(status = "closed")
        val api = FakeApiService(closeCashSessionResult = Result.success(closed))
        val repository = CashRegisterRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.closeSession("49000")

        assertTrue(result.isSuccess)
        assertEquals(closed, result.getOrNull())
        assertEquals("-1000", result.getOrNull()?.difference)
        assertEquals("49000", api.lastCloseCashSessionRequest?.countedAmount)
    }

    @Test
    fun `closeSession sin turno abierto devuelve el 409 del backend`() = runTest {
        val api = FakeApiService(
            closeCashSessionResult = Result.failure(httpErrorException(409, "No hay un turno de caja abierto.")),
        )
        val repository = CashRegisterRepository(FakeTokenStore(serverUrl = "http://192.168.1.50:8765/"), apiServiceFactory = { api })

        val result = repository.closeSession("0")

        assertTrue(result.isFailure)
        assertEquals(409, (result.exceptionOrNull() as ApiException).statusCode)
    }
}
