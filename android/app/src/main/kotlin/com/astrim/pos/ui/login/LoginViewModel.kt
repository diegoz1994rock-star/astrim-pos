package com.astrim.pos.ui.login

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.astrim.pos.core.session.SessionRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class LoginUiState(
    val serverUrl: String = "",
    val username: String = "",
    val password: String = "",
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
)

/**
 * Sin lógica de negocio propia: valida solo que los campos no estén
 * vacíos (una regla de formulario, no de negocio) y delega todo lo demás
 * en [SessionRepository.login] — las credenciales las valida el backend,
 * el mismo `AuthenticationService` que usa el escritorio.
 */
class LoginViewModel(private val sessionRepository: SessionRepository) : ViewModel() {

    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState.asStateFlow()

    fun onServerUrlChange(value: String) {
        _uiState.update { it.copy(serverUrl = value, errorMessage = null) }
    }

    fun onUsernameChange(value: String) {
        _uiState.update { it.copy(username = value, errorMessage = null) }
    }

    fun onPasswordChange(value: String) {
        _uiState.update { it.copy(password = value, errorMessage = null) }
    }

    fun login() {
        val current = _uiState.value
        if (current.serverUrl.isBlank() || current.username.isBlank() || current.password.isBlank()) {
            _uiState.update { it.copy(errorMessage = "Completá servidor, usuario y contraseña.") }
            return
        }
        // Mismo recorte que `login_view_model.py::attempt_login` del
        // escritorio: el teclado (autocompletar/autocorregir) suele agregar
        // un espacio final invisible al usuario, que rompe la comparación
        // exacta del backend y se ve como "usuario o contraseña
        // incorrectos" — bug real encontrado validando la Fase 3. La
        // contraseña no se recorta, igual que el escritorio.
        val username = current.username.trim()
        _uiState.update { it.copy(isLoading = true, errorMessage = null) }
        viewModelScope.launch {
            val result = sessionRepository.login(current.serverUrl, username, current.password)
            result.onFailure { error ->
                _uiState.update {
                    it.copy(isLoading = false, errorMessage = error.message ?: "Error desconocido.")
                }
            }
            // En éxito no hace falta tocar el estado local acá: SessionRepository.state
            // pasa a LoggedIn y AstrimApp cambia de pantalla sola.
        }
    }
}
