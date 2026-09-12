package com.astrim.pos.ui.customers

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.AlertDialog
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
import androidx.compose.material3.TextButton
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
import com.astrim.pos.core.network.dto.CustomerDto
import com.astrim.pos.ui.common.formatCurrency

/**
 * Clientes (Fase 5) — misma información que la pantalla "Clientes" del
 * escritorio (`customers_view.py`: nombre, documento, teléfono, deuda,
 * cupo, puntos), con búsqueda instantánea agregada (el escritorio no tiene
 * una, pero el criterio es el mismo que ya usan Catálogo/Despacho). "Nuevo
 * cliente" y "Registrar abono" son las mismas dos acciones reales de esa
 * pantalla — nada de deuda/cupo se calcula acá, ver [CustomersViewModel].
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CustomersScreen(onBack: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: CustomersViewModel = viewModel(
        factory = viewModelFactory {
            initializer { CustomersViewModel(container.customerRepository) }
        },
    )
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Clientes") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Volver")
                    }
                },
            )
        },
    ) { paddingValues ->
        Column(modifier = Modifier.fillMaxSize().padding(paddingValues)) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                OutlinedTextField(
                    value = uiState.searchText,
                    onValueChange = viewModel::onSearchTextChange,
                    label = { Text("Buscar por nombre, documento o teléfono") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
                Button(onClick = viewModel::onOpenCreateDialog, modifier = Modifier.padding(start = 8.dp)) {
                    Text("Nuevo")
                }
            }

            when {
                uiState.isLoading -> Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
                uiState.errorMessage != null -> Column(
                    modifier = Modifier.fillMaxSize().padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                ) {
                    Text(text = uiState.errorMessage.orEmpty(), color = MaterialTheme.colorScheme.error)
                    Button(onClick = viewModel::load, modifier = Modifier.padding(top = 16.dp)) {
                        Text("Reintentar")
                    }
                }
                uiState.filteredCustomers.isEmpty() -> Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center,
                ) {
                    Text("No hay clientes que coincidan con la búsqueda.")
                }
                else -> LazyColumn(
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(uiState.filteredCustomers, key = { it.id }) { customer ->
                        CustomerCard(customer = customer, onClick = { viewModel.onSelectCustomer(customer.id) })
                    }
                }
            }
        }
    }

    val selected = uiState.selectedCustomer
    if (selected != null) {
        CustomerDetailDialog(
            customer = selected,
            paymentAmount = uiState.paymentAmount,
            paymentError = uiState.paymentError,
            isRegisteringPayment = uiState.isRegisteringPayment,
            onPaymentAmountChange = viewModel::onPaymentAmountChange,
            onRegisterPayment = viewModel::onRegisterPayment,
            onDismiss = { viewModel.onSelectCustomer(null) },
        )
    }

    if (uiState.showCreateDialog) {
        CreateCustomerDialog(uiState = uiState, viewModel = viewModel)
    }
}

@Composable
private fun CustomerCard(customer: CustomerDto, onClick: () -> Unit) {
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(customer.fullName, fontWeight = FontWeight.Bold)
            Text(
                text = customer.documentId?.let { "Documento: $it" } ?: "Sin documento",
                style = MaterialTheme.typography.bodySmall,
            )
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Deuda: ${formatCurrency(customer.currentDebt)}", style = MaterialTheme.typography.bodySmall)
                Text("Cupo: ${formatCurrency(customer.creditLimit)}", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun CustomerDetailDialog(
    customer: CustomerDto,
    paymentAmount: String,
    paymentError: String?,
    isRegisteringPayment: Boolean,
    onPaymentAmountChange: (String) -> Unit,
    onRegisterPayment: () -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(customer.fullName) },
        text = {
            Column {
                Text("Documento: ${customer.documentId ?: "Sin documento"}")
                Text("Teléfono: ${customer.phone ?: "Sin teléfono"}")
                Text("Correo: ${customer.email ?: "Sin correo"}")
                Text("Dirección: ${customer.address ?: "Sin dirección"}")
                Text("Cupo de crédito: ${formatCurrency(customer.creditLimit)}")
                Text("Deuda actual: ${formatCurrency(customer.currentDebt)}")
                Text("Puntos de fidelidad: ${customer.loyaltyPointsBalance}")

                Text(
                    text = "Registrar abono",
                    style = MaterialTheme.typography.titleSmall,
                    modifier = Modifier.padding(top = 16.dp),
                )
                OutlinedTextField(
                    value = paymentAmount,
                    onValueChange = onPaymentAmountChange,
                    label = { Text("Monto") },
                    singleLine = true,
                    isError = paymentError != null,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    modifier = Modifier.padding(top = 8.dp),
                )
                val error = paymentError
                if (error != null) {
                    Text(error, color = MaterialTheme.colorScheme.error)
                }
                Button(
                    onClick = onRegisterPayment,
                    enabled = !isRegisteringPayment,
                    modifier = Modifier.padding(top = 8.dp),
                ) {
                    Text("Registrar abono")
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text("Cerrar") }
        },
    )
}

@Composable
private fun CreateCustomerDialog(uiState: CustomersUiState, viewModel: CustomersViewModel) {
    AlertDialog(
        onDismissRequest = viewModel::onDismissCreateDialog,
        title = { Text("Nuevo cliente") },
        text = {
            Column(modifier = Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState())) {
                OutlinedTextField(
                    value = uiState.newFullName,
                    onValueChange = viewModel::onNewFullNameChange,
                    label = { Text("Nombre completo") },
                    singleLine = true,
                    isError = uiState.createError != null,
                )
                OutlinedTextField(
                    value = uiState.newDocumentId,
                    onValueChange = viewModel::onNewDocumentIdChange,
                    label = { Text("Documento (opcional)") },
                    singleLine = true,
                    modifier = Modifier.padding(top = 8.dp),
                )
                OutlinedTextField(
                    value = uiState.newEmail,
                    onValueChange = viewModel::onNewEmailChange,
                    label = { Text("Correo (opcional)") },
                    singleLine = true,
                    modifier = Modifier.padding(top = 8.dp),
                )
                OutlinedTextField(
                    value = uiState.newPhone,
                    onValueChange = viewModel::onNewPhoneChange,
                    label = { Text("Teléfono (opcional)") },
                    singleLine = true,
                    modifier = Modifier.padding(top = 8.dp),
                )
                OutlinedTextField(
                    value = uiState.newAddress,
                    onValueChange = viewModel::onNewAddressChange,
                    label = { Text("Dirección (opcional)") },
                    singleLine = true,
                    modifier = Modifier.padding(top = 8.dp),
                )
                OutlinedTextField(
                    value = uiState.newCreditLimit,
                    onValueChange = viewModel::onNewCreditLimitChange,
                    label = { Text("Cupo de crédito") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    modifier = Modifier.padding(top = 8.dp),
                )
                val error = uiState.createError
                if (error != null) {
                    Text(error, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 8.dp))
                }
            }
        },
        confirmButton = {
            Button(onClick = viewModel::onCreateCustomer, enabled = !uiState.isCreating) {
                Text("Guardar")
            }
        },
        dismissButton = {
            TextButton(onClick = viewModel::onDismissCreateDialog) { Text("Cancelar") }
        },
    )
}
