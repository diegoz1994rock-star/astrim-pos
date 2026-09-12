package com.astrim.pos.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.astrim.pos.core.session.SessionRepository
import com.astrim.pos.core.session.SessionState
import com.astrim.pos.ui.login.LoginScreen
import com.astrim.pos.ui.navigation.AstrimNavHost

/**
 * Raíz de la UI: decide Login vs. la app autenticada según
 * [SessionRepository.state] — no es una ruta más dentro de
 * `AstrimNavHost` a propósito, para que ninguna pantalla autenticada
 * pueda quedar alcanzable por navegación si la sesión se cae (ver
 * `SessionRepository.restoreSession`, que también limpia el token cuando
 * `/api/v1/auth/me` ya no lo valida).
 */
@Composable
fun AstrimApp(sessionRepository: SessionRepository) {
    val state by sessionRepository.state.collectAsStateWithLifecycle()

    LaunchedEffect(Unit) {
        sessionRepository.restoreSession()
    }

    when (val current = state) {
        SessionState.Loading -> LoadingScreen()
        SessionState.LoggedOut -> LoginScreen()
        is SessionState.LoggedIn -> AstrimNavHost(
            session = current.session,
            onLogout = sessionRepository::logout,
        )
    }
}

@Composable
private fun LoadingScreen() {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        CircularProgressIndicator()
    }
}
