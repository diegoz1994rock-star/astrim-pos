package com.astrim.pos.ui.login

import com.astrim.pos.core.network.FakeApiService
import com.astrim.pos.core.network.dto.LoginResponse
import com.astrim.pos.core.network.dto.SessionInfoDto
import com.astrim.pos.core.session.FakeTokenStore
import com.astrim.pos.core.session.SessionRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

private fun sampleSession() = SessionInfoDto(
    userId = 1,
    username = "DiegoGutierrez",
    fullName = "Diego Gutiérrez",
    isAdmin = true,
    permissionCodes = emptyList(),
    loggedInAt = "2026-07-25T01:00:00Z",
)

/**
 * Regresión encontrada validando la Fase 3: el teclado del celular
 * (autocompletar/autocorregir) agrega un espacio final invisible al
 * usuario, que rompe la comparación exacta del backend y se veía como
 * "usuario o contraseña incorrectos" — ver `login_view_model.py::
 * attempt_login` del escritorio, que ya recorta el usuario antes de
 * autenticar.
 */
@OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
class LoginViewModelTest {

    /** `LoginViewModel.login()` lanza en `viewModelScope`, que corre sobre
     * `Dispatchers.Main` — no inicializado en un test JVM puro sin esto. */
    @Before
    fun setMainDispatcher() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
    }

    @After
    fun resetMainDispatcher() {
        Dispatchers.resetMain()
    }

    @Test
    fun `login recorta espacios del usuario antes de enviarlo`() = runTest {
        val api = FakeApiService(
            loginResult = Result.success(
                LoginResponse(token = "tok-123", expiresAt = "2026-07-25T13:00:00Z", session = sampleSession()),
            ),
        )
        val sessionRepository = SessionRepository(FakeTokenStore(), apiServiceFactory = { api })
        val viewModel = LoginViewModel(sessionRepository)

        viewModel.onServerUrlChange("192.168.1.50:8765")
        viewModel.onUsernameChange("DiegoGutierrez ")
        viewModel.onPasswordChange("clave-valida")
        viewModel.login()

        assertEquals("DiegoGutierrez", api.lastLoginRequest?.username)
    }

    @Test
    fun `login no recorta la contrasena`() = runTest {
        val api = FakeApiService(
            loginResult = Result.success(
                LoginResponse(token = "tok-123", expiresAt = "2026-07-25T13:00:00Z", session = sampleSession()),
            ),
        )
        val sessionRepository = SessionRepository(FakeTokenStore(), apiServiceFactory = { api })
        val viewModel = LoginViewModel(sessionRepository)

        viewModel.onServerUrlChange("192.168.1.50:8765")
        viewModel.onUsernameChange("DiegoGutierrez")
        viewModel.onPasswordChange(" clave-con-espacio ")
        viewModel.login()

        assertEquals(" clave-con-espacio ", api.lastLoginRequest?.password)
    }
}
