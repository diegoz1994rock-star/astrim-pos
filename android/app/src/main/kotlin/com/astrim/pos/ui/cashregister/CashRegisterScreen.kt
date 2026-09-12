package com.astrim.pos.ui.cashregister

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.astrim.pos.core.LocalAppContainer
import com.astrim.pos.core.network.dto.CashSessionDto
import com.astrim.pos.ui.common.formatCurrency

/** "T" → espacio y se corta a minutos — sin agregar una librería de
 * fechas para una sola pantalla; mismo criterio minimalista que
 * [formatCurrency] (una función pura, sin estado). */
private fun formatDateTime(iso: String): String =
    iso.replace('T', ' ').take(16)

/**
 * Caja (Fase 6) — mismo flujo que la pantalla "Caja" del escritorio
 * (`cash_register_view.py`): ver el estado del turno del punto de caja,
 * abrirlo y cerrarlo. Sin selector de punto de caja ni de "usuario que
 * opera el turno" (a diferencia del escritorio): el backend ya resuelve
 * el único punto de caja activo y usa el usuario autenticado como quien
 * abre/cierra (ver API.md §3.10) — un cajero con el teléfono en la mano
 * es siempre él mismo, no hay a quién elegir. Ni el monto esperado ni la
 * diferencia del arqueo se calculan acá, ver [CashRegisterViewModel].
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CashRegisterScreen(onBack: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: CashRegisterViewModel = viewModel(
        factory = viewModelFactory {
            initializer { CashRegisterViewModel(container.cashRegisterRepository) }
        },
    )
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Caja") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Volver")
                    }
                },
            )
        },
    ) { paddingValues ->
        when {
            uiState.isLoading -> Box(
                modifier = Modifier.fillMaxSize().padding(paddingValues),
                contentAlignment = Alignment.Center,
            ) {
                CircularProgressIndicator()
            }
            uiState.errorMessage != null -> Column(
                modifier = Modifier.fillMaxSize().padding(paddingValues).padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Text(text = uiState.errorMessage.orEmpty(), color = MaterialTheme.colorScheme.error)
                Button(onClick = viewModel::load, modifier = Modifier.padding(top = 16.dp)) {
                    Text("Reintentar")
                }
            }
            else -> CashRegisterContent(uiState = uiState, viewModel = viewModel)
        }
    }
}

@Composable
private fun CashRegisterContent(uiState: CashRegisterUiState, viewModel: CashRegisterViewModel) {
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text(
            text = uiState.cashRegisterName ?: "",
            style = MaterialTheme.typography.titleMedium,
        )
        val session = uiState.session
        if (session != null) {
            OpenSessionCard(session = session)
            Text(
                text = "Cerrar turno",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(top = 24.dp),
            )
            OutlinedTextField(
                value = uiState.countedAmountText,
                onValueChange = viewModel::onCountedAmountChange,
                label = { Text("Monto contado") },
                singleLine = true,
                isError = uiState.closeError != null,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            )
            val closeError = uiState.closeError
            if (closeError != null) {
                Text(closeError, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 4.dp))
            }
            Button(
                onClick = viewModel::onCloseSession,
                enabled = !uiState.isClosing,
                modifier = Modifier.padding(top = 8.dp),
            ) {
                Text("Cerrar turno")
            }
        } else {
            val lastClosed = uiState.lastClosedSession
            if (lastClosed != null) {
                Text(
                    text = "Turno cerrado. Diferencia: ${formatCurrency(lastClosed.difference.orEmpty())}",
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(top = 16.dp),
                )
            }
            Text(
                text = "Sin turno abierto",
                style = MaterialTheme.typography.bodyLarge,
                modifier = Modifier.padding(top = 16.dp),
            )
            Text(
                text = "Abrir turno",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(top = 24.dp),
            )
            OutlinedTextField(
                value = uiState.openingAmountText,
                onValueChange = viewModel::onOpeningAmountChange,
                label = { Text("Monto de apertura") },
                singleLine = true,
                isError = uiState.openError != null,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            )
            val openError = uiState.openError
            if (openError != null) {
                Text(openError, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 4.dp))
            }
            Button(
                onClick = viewModel::onOpenSession,
                enabled = !uiState.isOpening,
                modifier = Modifier.padding(top = 8.dp),
            ) {
                Text("Abrir turno")
            }
        }
    }
}

@Composable
private fun OpenSessionCard(session: CashSessionDto) {
    Card(modifier = Modifier.fillMaxWidth().padding(top = 12.dp)) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text("Turno abierto", fontWeight = FontWeight.Bold)
            Text(
                text = "Desde ${formatDateTime(session.openedAt)}",
                style = MaterialTheme.typography.bodyMedium,
            )
            Text(
                text = "Apertura: ${formatCurrency(session.openingAmount)}",
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}
