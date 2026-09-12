package com.astrim.pos.core.session

import com.astrim.pos.core.network.ApiException
import com.astrim.pos.core.network.FakeApiService
import com.astrim.pos.core.network.dto.LoginResponse
import com.astrim.pos.core.network.dto.SessionInfoDto
import com.astrim.pos.core.network.httpErrorException
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

private fun sampleSession(userId: Int = 1) = SessionInfoDto(
    userId = userId,
    username = "cajero1",
    fullName = "Cajero de Prueba",
    isAdmin = false,
    permissionCodes = listOf("sales.create"),
    loggedInAt = "2026-07-24T10:00:00Z",
)

/**
 * Ninguna de estas pruebas toca la red real (ver [FakeApiService]) ni el
 * framework de Android (ver [FakeTokenStore]) — corren en JVM puro. Cubren
 * exactamente lo que pide la Fase 1: login exitoso persiste el token,
 * login fallido no persiste nada y expone el mensaje real del backend,
 * restaurar sesión valida contra `/me` (y limpia el token si ya no es
 * válido), y logout limpia todo.
 */
class SessionRepositoryTest {

    @Test
    fun `login exitoso guarda el token y pasa a LoggedIn`() = runTest {
        val tokenStore = FakeTokenStore()
        val session = sampleSession()
        val api = FakeApiService(
            loginResult = Result.success(
                LoginResponse(token = "tok-123", expiresAt = "2026-07-25T00:00:00Z", session = session),
            ),
        )
        val repository = SessionRepository(tokenStore, apiServiceFactory = { api })

        val result = repository.login("192.168.1.50:8765", "cajero1", "clave-valida")

        assertTrue(result.isSuccess)
        assertEquals("tok-123", tokenStore.getToken())
        assertEquals("http://192.168.1.50:8765/", tokenStore.getServerUrl())
        assertEquals(SessionState.LoggedIn(session), repository.state.value)
        assertEquals("cajero1", api.lastLoginRequest?.username)
    }

    @Test
    fun `login fallido no guarda token y devuelve el mensaje del backend`() = runTest {
        val tokenStore = FakeTokenStore()
        val api = FakeApiService(
            loginResult = Result.failure(
                httpErrorException(401, "Usuario o contraseña incorrectos."),
            ),
        )
        val repository = SessionRepository(tokenStore, apiServiceFactory = { api })

        val result = repository.login("192.168.1.50:8765", "cajero1", "clave-mala")

        assertTrue(result.isFailure)
        val error = result.exceptionOrNull()
        assertTrue(error is ApiException)
        assertEquals(401, (error as ApiException).statusCode)
        assertEquals("Usuario o contraseña incorrectos.", error.message)
        assertNull(tokenStore.getToken())
        assertEquals(SessionState.Loading, repository.state.value)
    }

    @Test
    fun `restoreSession sin credenciales guardadas queda en LoggedOut`() = runTest {
        val tokenStore = FakeTokenStore()
        val repository = SessionRepository(
            tokenStore,
            apiServiceFactory = { error("no debería llamarse a la API sin credenciales guardadas") },
        )

        repository.restoreSession()

        assertEquals(SessionState.LoggedOut, repository.state.value)
    }

    @Test
    fun `restoreSession con token valido confirma la sesion contra me`() = runTest {
        val tokenStore = FakeTokenStore(serverUrl = "http://192.168.1.50:8765/", token = "tok-123")
        val session = sampleSession()
        val api = FakeApiService(meResult = Result.success(session))
        val repository = SessionRepository(tokenStore, apiServiceFactory = { api })

        repository.restoreSession()

        assertEquals(SessionState.LoggedIn(session), repository.state.value)
    }

    @Test
    fun `restoreSession con token expirado limpia el almacen y vuelve a LoggedOut`() = runTest {
        val tokenStore = FakeTokenStore(serverUrl = "http://192.168.1.50:8765/", token = "tok-vencido")
        val api = FakeApiService(
            meResult = Result.failure(httpErrorException(401, "Token inválido o expirado.")),
        )
        val repository = SessionRepository(tokenStore, apiServiceFactory = { api })

        repository.restoreSession()

        assertEquals(SessionState.LoggedOut, repository.state.value)
        assertNull(tokenStore.getToken())
        assertNull(tokenStore.getServerUrl())
    }

    @Test
    fun `logout limpia el almacen y vuelve a LoggedOut`() = runTest {
        val tokenStore = FakeTokenStore(serverUrl = "http://192.168.1.50:8765/", token = "tok-123")
        val repository = SessionRepository(
            tokenStore,
            apiServiceFactory = { error("logout no debería llamar a la API") },
        )

        repository.logout()

        assertEquals(SessionState.LoggedOut, repository.state.value)
        assertNull(tokenStore.getToken())
    }
}
