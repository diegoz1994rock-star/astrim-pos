package com.astrim.pos.ui.saleshistory

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.astrim.pos.core.LocalAppContainer
import com.astrim.pos.core.network.dto.CompletedSaleDto
import com.astrim.pos.ui.common.AppBackground
import com.astrim.pos.ui.common.AppCardBackground
import com.astrim.pos.ui.common.AppTextSecondary
import com.astrim.pos.ui.common.formatCurrency

/** "T" → espacio y se corta a minutos — mismo criterio minimalista que ya
 * usa `CashRegisterScreen.kt`/`DispatchScreen.kt` para no sumar una
 * librería de fechas nueva. */
private fun formatDateTime(iso: String?): String = iso?.replace('T', ' ')?.take(16) ?: "Sin fecha"

/**
 * Historial de ventas — botón "Historial" de Ventas. Solo lectura: lista
 * de ventas recientes con fecha, cliente, método de pago y total, mismo
 * criterio y mismos datos que `SalesHistoryView` del escritorio. Ver
 * [SalesHistoryViewModel].
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SalesHistoryScreen(onBack: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: SalesHistoryViewModel = viewModel(
        factory = viewModelFactory {
            initializer { SalesHistoryViewModel(container.salesRepository) }
        },
    )
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        containerColor = AppBackground,
        topBar = {
            TopAppBar(
                title = { Text("Historial") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Volver")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = AppBackground),
            )
        },
    ) { paddingValues ->
        Box(modifier = Modifier.fillMaxSize().background(AppBackground).padding(paddingValues)) {
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
                uiState.sales.isEmpty() -> Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("Todavía no hay ventas registradas.", color = AppTextSecondary)
                }
                else -> LazyColumn(
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                    modifier = Modifier.fillMaxSize(),
                ) {
                    items(uiState.sales, key = { it.id }) { sale -> SaleHistoryCard(sale) }
                }
            }
        }
    }
}

@Composable
private fun SaleHistoryCard(sale: CompletedSaleDto) {
    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = AppCardBackground),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Venta #${sale.id}", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                Text(
                    formatCurrency(sale.total),
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.titleMedium,
                )
            }
            Text(
                text = formatDateTime(sale.createdAt),
                color = AppTextSecondary,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 4.dp),
            )
            Text(
                text = sale.customerName?.takeIf { it.isNotBlank() } ?: "Sin nombre",
                color = AppTextSecondary,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 8.dp),
            )
            Text(
                text = paymentMethodSummary(sale),
                color = AppTextSecondary,
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}
