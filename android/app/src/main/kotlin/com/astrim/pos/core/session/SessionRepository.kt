package com.astrim.pos.core.session

import com.astrim.pos.core.network.ApiClientFactory
import com.astrim.pos.core.network.ApiException
import com.astrim.pos.core.network.ApiService
import com.astrim.pos.core.network.dto.LoginRequest
import com.astrim.pos.core.network.dto.SessionInfoDto
import com.astrim.pos.core.network.normalizeServerUrl
import com.astrim.pos.core.network.toApiException
import java.io.IOException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import retrofit2.HttpException

/** Estado de sesión de toda la app — una única fuente de verdad, la
 * observa la navegación (ver ui/navigation) para decidir si mostrar Login
 * u Home. */
sealed interface SessionState {
    /** Validando la sesión persistida al arrancar — ver [SessionRepository.restoreSession]. */
    data object Loading : SessionState
    data object LoggedOut : SessionState
    data class LoggedIn(val session: SessionInfoDto) : SessionState
}

/**
 * Orquesta login/restauración/logout contra la API — ninguna regla de
 * negocio propia: cada método es una llamada directa a [ApiService]
 * seguida de guardar/limpiar el token. Toda la lógica real (validar
 * credenciales, resolver permisos) vive en el backend (ver
 * `AuthenticationService` del proyecto principal) — acá solo se refleja el
 * resultado.
 *
 * `apiServiceFactory` es una función (no una instancia fija de
 * [ApiService]) porque la URL del servidor puede cambiar entre login y
 * restauración de sesión — y, sobre todo, para poder probar esta clase en
 * JVM puro inyectando un [ApiService] falso sin tocar la red real (ver
 * `app/src/test/.../SessionRepositoryTest.kt`). En producción,
 * [AppContainer][com.astrim.pos.core.AppContainer] no pasa nada especial:
 * el valor por default ya arma el cliente real vía [ApiClientFactory].
 */
class SessionRepository(
    private val tokenStore: TokenStore,
    private val apiServiceFactory: (baseUrl: String) -> ApiService = { baseUrl ->
        ApiClientFactory.create(baseUrl) { tokenStore.getToken() }
    },
) {

    private val _state = MutableStateFlow<SessionState>(SessionState.Loading)
    val state: StateFlow<SessionState> = _state.asStateFlow()

    /**
     * Se llama una vez al arrancar la app. No confía ciegamente en el
     * token guardado — lo valida contra `GET /api/v1/auth/me` (pudo
     * expirar, o el usuario pudo haber sido desactivado desde el
     * escritorio) antes de dar la sesión por buena. Así se cumple
     * "Mantener la sesión iniciada" sin arriesgar mostrar una sesión que
     * en realidad ya no es válida.
     */
    suspend fun restoreSession() {
        val serverUrl = tokenStore.getServerUrl()
        val token = tokenStore.getToken()
        if (serverUrl == null || token == null) {
            _state.value = SessionState.LoggedOut
            return
        }
        val api = apiServiceFactory(serverUrl)
        try {
            val session = api.me()
            _state.value = SessionState.LoggedIn(session)
        } catch (e: Exception) {
            // Token inválido/expirado, o el servidor no responde ahora
            // mismo: no se puede confirmar la sesión, así que se pide
            // login de nuevo — más seguro que asumir que sigue vigente.
            tokenStore.clear()
            _state.value = SessionState.LoggedOut
        }
    }

    /** [serverUrlInput] es lo que el usuario escribió tal cual (ver
     * [normalizeServerUrl]) — cada negocio corre su propio servidor en su
     * propia red, no hay una URL fija en la app. */
    suspend fun login(serverUrlInput: String, username: String, password: String): Result<Unit> {
        val serverUrl = normalizeServerUrl(serverUrlInput)
        val api = apiServiceFactory(serverUrl)
        return try {
            val response = api.login(LoginRequest(username, password))
            tokenStore.saveCredentials(serverUrl, response.token)
            _state.value = SessionState.LoggedIn(response.session)
            Result.success(Unit)
        } catch (e: HttpException) {
            Result.failure(e.toApiException())
        } catch (e: IOException) {
            Result.failure(
                ApiException(
                    statusCode = 0,
                    message = "No se pudo conectar con el servidor. Verificá la dirección y la red.",
                ),
            )
        }
    }

    fun logout() {
        tokenStore.clear()
        _state.value = SessionState.LoggedOut
    }
}
