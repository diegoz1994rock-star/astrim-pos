package com.astrim.pos.ui.dispatch

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.ArrowForward
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.ScaffoldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.astrim.pos.core.LocalAppContainer
import com.astrim.pos.core.network.dto.CompletedSaleDto
import com.astrim.pos.core.network.dto.DispatchOrderCardDto
import com.astrim.pos.ui.common.AppBackground as DispatchBackground
import com.astrim.pos.ui.common.AppCardBackground as DispatchCardBackground
import com.astrim.pos.ui.common.AppOutline as DispatchOutline
import com.astrim.pos.ui.common.AppTextMuted as DispatchTextMuted
import com.astrim.pos.ui.common.AppTextSecondary as DispatchTextSecondary
import com.astrim.pos.ui.common.GradientButton
import com.astrim.pos.ui.common.formatCurrency

private val DispatchAccent = Color(0xFF5C6BC0)
private val StatusPendingColor = Color(0xFFE53935)
private val StatusPreparingColor = Color(0xFFFFC107)
private val StatusDeliveredColor = Color(0xFF2196F3)

private data class StatusStyle(val label: String, val color: Color, val icon: String)

/** Mismo color/ícono por estado en toda la pantalla (tarjeta, badge, botón
 * "Detalle") — el usuario reconoce el estado con solo mirar el color, tal
 * como pide el diseño. */
private fun statusStyle(status: String): StatusStyle = when (status) {
    "pending" -> StatusStyle("PENDIENTE", StatusPendingColor, "🕒")
    "preparing", "ready" -> StatusStyle("EN PREPARACIÓN", StatusPreparingColor, "🛒")
    "delivered" -> StatusStyle("ENTREGADO", StatusDeliveredColor, "✔")
    else -> StatusStyle(dispatchStatusLabel(status).uppercase(), DispatchTextSecondary, "•")
}

/** "T" → espacio y se corta a minutos — mismo criterio minimalista que ya
 * usa `CashRegisterScreen.kt` para no sumar una librería de fechas nueva. */
private fun formatDateTime(iso: String?): String = iso?.replace('T', ' ')?.take(16) ?: "Sin fecha"

/**
 * Despacho — mismo caso de uso que `kitchen_view.py` del escritorio:
 * pedidos organizados por cliente (una tarjeta por pedido, no por
 * producto), con filtros y búsqueda en memoria sobre la cola ya cargada, y
 * dos acciones — "Siguiente proceso" sobre la tarjeta seleccionada, y
 * "Marcar como entregado" desde el detalle. Un tap selecciona una tarjeta
 * (equivalente al clic simple del escritorio); el botón "Detalle" abre una
 * pantalla completa (equivalente al doble clic, que en el escritorio abre
 * un diálogo). Ningún estado se calcula acá — ver [DispatchViewModel].
 *
 * Rediseño visual: fondo casi negro, tarjetas oscuras con borde/ícono/
 * badge coloreados según el estado (rojo/amarillo/azul), y la tarjeta
 * principal solo muestra cliente, número de pedido y origen/pago — el
 * resto (fecha, vendedor, productos, precio si ya se cobró) vive
 * únicamente en la pantalla de Detalle.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DispatchScreen(onBack: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: DispatchViewModel = viewModel(
        factory = viewModelFactory {
            initializer { DispatchViewModel(container.dispatchRepository, container.salesRepository) }
        },
    )
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    val detailOrder = uiState.orders.firstOrNull { it.orderId == uiState.detailOrderId }
    if (detailOrder != null) {
        DispatchOrderDetailScreen(
            card = detailOrder,
            isLoadingSaleDetail = uiState.isLoadingSaleDetail,
            saleDetail = uiState.saleDetail,
            saleDetailError = uiState.saleDetailError,
            isActing = uiState.isActing,
            onBack = viewModel::onDismissDetail,
            onDeliver = { viewModel.onDeliverOrder(detailOrder.orderId) },
        )
        return
    }

    Scaffold(
        containerColor = DispatchBackground,
        contentWindowInsets = ScaffoldDefaults.contentWindowInsets,
        topBar = {
            TopAppBar(
                title = {
                    Text("Despacho", style = MaterialTheme.typography.headlineSmall, color = Color.White)
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Volver", tint = Color.White)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = DispatchBackground),
            )
        },
    ) { paddingValues ->
        Column(modifier = Modifier.fillMaxSize().background(DispatchBackground).padding(paddingValues)) {
            OutlinedTextField(
                value = uiState.searchText,
                onValueChange = viewModel::onSearchTextChange,
                placeholder = {
                    Text(
                        "Buscar por cliente, documento, pedido o empleado",
                        color = DispatchTextMuted,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null, tint = DispatchTextSecondary) },
                singleLine = true,
                shape = RoundedCornerShape(16.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedContainerColor = DispatchCardBackground,
                    unfocusedContainerColor = DispatchCardBackground,
                    focusedBorderColor = DispatchAccent,
                    unfocusedBorderColor = DispatchOutline,
                    focusedTextColor = Color.White,
                    unfocusedTextColor = Color.White,
                    cursorColor = DispatchAccent,
                ),
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp),
            )

            LazyRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
            ) {
                items(DispatchFilter.entries.toList(), key = { it.name }) { filter ->
                    val selected = uiState.activeFilter == filter
                    FilterChip(
                        selected = selected,
                        onClick = { viewModel.onFilterSelected(filter) },
                        label = { Text(filter.label) },
                        colors = FilterChipDefaults.filterChipColors(
                            containerColor = DispatchCardBackground,
                            labelColor = DispatchTextSecondary,
                            selectedContainerColor = DispatchAccent,
                            selectedLabelColor = Color.White,
                        ),
                        border = FilterChipDefaults.filterChipBorder(
                            enabled = true,
                            selected = selected,
                            borderColor = DispatchOutline,
                            selectedBorderColor = DispatchAccent,
                        ),
                    )
                }
            }

            val actionError = uiState.actionError
            if (actionError != null) {
                Text(
                    text = actionError,
                    color = StatusPendingColor,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                )
            }

            when {
                uiState.isLoading -> Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = DispatchAccent)
                }
                uiState.errorMessage != null -> DispatchErrorState(
                    message = uiState.errorMessage.orEmpty(),
                    onRetry = viewModel::load,
                )
                else -> OrderList(
                    orders = uiState.filteredOrders,
                    selectedOrderId = uiState.selectedOrderId,
                    onSelect = viewModel::onSelectOrder,
                    onOpenDetail = viewModel::onOpenDetail,
                    modifier = Modifier.weight(1f),
                )
            }

            GradientButton(
                text = "Siguiente proceso",
                onClick = viewModel::onAdvanceSelected,
                enabled = uiState.selectedOrderId != null && !uiState.isActing,
                isLoading = uiState.isActing,
                icon = Icons.Default.ArrowForward,
                modifier = Modifier.fillMaxWidth().padding(16.dp),
            )
        }
    }
}

@Composable
private fun DispatchErrorState(message: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(text = message, color = StatusPendingColor)
        Button(onClick = onRetry, modifier = Modifier.padding(top = 16.dp)) {
            Text("Reintentar")
        }
    }
}

@Composable
private fun OrderList(
    orders: List<DispatchOrderCardDto>,
    selectedOrderId: Int?,
    onSelect: (Int) -> Unit,
    onOpenDetail: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    if (orders.isEmpty()) {
        Box(modifier = modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text("No hay pedidos que coincidan con el filtro.", color = DispatchTextSecondary)
        }
        return
    }
    LazyColumn(
        modifier = modifier.fillMaxWidth(),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        items(orders, key = { it.orderId }) { card ->
            OrderCard(
                card = card,
                selected = card.orderId == selectedOrderId,
                onClick = { onSelect(card.orderId) },
                onDetailClick = { onOpenDetail(card.orderId) },
            )
        }
    }
}

@Composable
private fun OrderCard(
    card: DispatchOrderCardDto,
    selected: Boolean,
    onClick: () -> Unit,
    onDetailClick: () -> Unit,
) {
    val style = statusStyle(card.dispatchStatus)
    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = DispatchCardBackground),
        border = BorderStroke(if (selected) 3.dp else 1.5.dp, style.color),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.weight(1f)) {
                    Box(
                        modifier = Modifier
                            .size(40.dp)
                            .clip(CircleShape)
                            .background(style.color.copy(alpha = 0.22f)),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(style.icon, fontSize = 18.sp)
                    }
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text(
                            text = card.customerName,
                            color = Color.White,
                            fontWeight = FontWeight.Bold,
                            style = MaterialTheme.typography.titleMedium,
                        )
                        Text(
                            text = "#${card.orderId.toString().padStart(6, '0')}",
                            color = DispatchTextSecondary,
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
                Text(
                    text = style.label,
                    color = style.color,
                    fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.End,
                    style = MaterialTheme.typography.titleSmall,
                    modifier = Modifier.padding(start = 8.dp),
                )
            }
            Text(
                text = "${dispatchOriginLabel(card.origin)} • ${if (card.isPaid) "Pagado" else "No pagado"}",
                color = DispatchTextSecondary,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 10.dp),
            )
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                horizontalArrangement = Arrangement.End,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                TextButton(onClick = onDetailClick) {
                    Text("Detalle", color = style.color, fontWeight = FontWeight.Bold)
                    Icon(
                        Icons.Default.ArrowForward,
                        contentDescription = null,
                        tint = style.color,
                        modifier = Modifier.size(16.dp).padding(start = 2.dp),
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DispatchOrderDetailScreen(
    card: DispatchOrderCardDto,
    isLoadingSaleDetail: Boolean,
    saleDetail: CompletedSaleDto?,
    saleDetailError: String?,
    isActing: Boolean,
    onBack: () -> Unit,
    onDeliver: () -> Unit,
) {
    val style = statusStyle(card.dispatchStatus)
    Scaffold(
        containerColor = DispatchBackground,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        "Pedido #${card.orderId.toString().padStart(6, '0')}",
                        color = Color.White,
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Volver", tint = Color.White)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = DispatchBackground),
            )
        },
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(DispatchBackground)
                .padding(paddingValues)
                .padding(16.dp),
        ) {
            LazyColumn(modifier = Modifier.weight(1f)) {
                item {
                    Text(card.customerName, color = Color.White, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                    Text(
                        text = style.label,
                        color = style.color,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(top = 8.dp),
                    )
                    DetailRow("Documento", card.customerDocument ?: "Sin documento")
                    DetailRow("Fecha y hora", formatDateTime(card.createdAt))
                    DetailRow("Vendedor responsable", card.createdByUserName ?: "Sin registrar")
                    DetailRow("Origen", dispatchOriginLabel(card.origin))
                    DetailRow("Caja asignada", card.cajaName ?: "Sin caja asignada")
                    DetailRow("Estado del pago", if (card.isPaid) "PAGADO" else "NO PAGADO")

                    Text(
                        text = "Productos",
                        color = DispatchTextSecondary,
                        style = MaterialTheme.typography.titleSmall,
                        modifier = Modifier.padding(top = 20.dp, bottom = 4.dp),
                    )
                }
                items(card.items) { item ->
                    val unitPrice = saleDetail?.items?.firstOrNull { it.productId == item.productId }?.unitPrice
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Text("${item.quantity} x ${item.productName}", color = Color.White)
                        if (unitPrice != null) {
                            Text(formatCurrency(unitPrice), color = DispatchTextSecondary)
                        }
                    }
                }
                item {
                    Text(
                        text = "Total de artículos: ${card.totalUnits}",
                        color = DispatchTextSecondary,
                        modifier = Modifier.padding(top = 4.dp),
                    )

                    Text(
                        text = "Observaciones",
                        color = DispatchTextSecondary,
                        style = MaterialTheme.typography.titleSmall,
                        modifier = Modifier.padding(top = 20.dp, bottom = 4.dp),
                    )
                    val notes = card.items.mapNotNull { it.notes?.takeIf { note -> note.isNotBlank() } }
                    Text(
                        text = if (notes.isEmpty()) "Sin observaciones" else notes.joinToString(" · "),
                        color = Color.White,
                    )

                    Text(
                        text = "Cobro",
                        color = DispatchTextSecondary,
                        style = MaterialTheme.typography.titleSmall,
                        modifier = Modifier.padding(top = 20.dp, bottom = 4.dp),
                    )
                    when {
                        card.saleId == null -> Text("Aún no cobrado.", color = DispatchTextSecondary)
                        isLoadingSaleDetail -> CircularProgressIndicator(
                            color = DispatchAccent,
                            modifier = Modifier.size(20.dp).padding(top = 4.dp),
                            strokeWidth = 2.dp,
                        )
                        saleDetailError != null -> Text(
                            "No se pudo obtener el detalle de cobro: $saleDetailError",
                            color = StatusPendingColor,
                        )
                        saleDetail != null -> Column {
                            DetailRow("Subtotal", formatCurrency(saleDetail.subtotal))
                            if (saleDetail.discountTotal.toBigDecimalOrNull()?.signum() == 1) {
                                DetailRow("Descuentos", "-${formatCurrency(saleDetail.discountTotal)}")
                            }
                            DetailRow("Impuestos", formatCurrency(saleDetail.taxTotal))
                            DetailRow("Total", formatCurrency(saleDetail.total))
                            saleDetail.payments.forEach { payment ->
                                DetailRow(
                                    "Método de pago",
                                    "${paymentMethodLabelFor(payment.paymentMethod)} — ${formatCurrency(payment.amount)}",
                                )
                            }
                        }
                    }
                }
            }

            GradientButton(
                text = "Marcar como entregado",
                onClick = onDeliver,
                enabled = card.dispatchStatus != "delivered" && !isActing,
                isLoading = isActing,
                icon = Icons.Default.ArrowForward,
                modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
            )
        }
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, color = DispatchTextSecondary)
        Text(value, color = Color.White, fontWeight = FontWeight.Bold, textAlign = TextAlign.End)
    }
}

/** Mismas etiquetas que `sale_view.py` — sin depender de `ui.sales` para no
 * crear una dependencia cruzada de módulos por un simple mapa de texto. */
private fun paymentMethodLabelFor(apiValue: String): String = when (apiValue) {
    "cash" -> "Efectivo"
    "card" -> "Tarjeta"
    "qr" -> "QR"
    "nequi" -> "Nequi"
    "bre_b" -> "Bre-B"
    "customer_credit" -> "Agregar a la deuda"
    else -> apiValue
}
