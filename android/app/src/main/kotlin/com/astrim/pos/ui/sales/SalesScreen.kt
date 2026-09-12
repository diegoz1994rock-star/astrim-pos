package com.astrim.pos.ui.sales

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.ShoppingCart
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.astrim.pos.core.LocalAppContainer
import com.astrim.pos.core.network.dto.CompletedSaleDto
import com.astrim.pos.core.network.dto.CustomerDto
import com.astrim.pos.core.network.dto.ProductSummaryDto
import com.astrim.pos.core.network.dto.SaleDraftDto
import com.astrim.pos.core.network.dto.SaleDraftLineDto
import com.astrim.pos.ui.common.AppBackground
import com.astrim.pos.ui.common.AppCardBackground
import com.astrim.pos.ui.common.AppOutline
import com.astrim.pos.ui.common.AppTextMuted
import com.astrim.pos.ui.common.AppTextSecondary
import com.astrim.pos.ui.common.DarkOutlinedField
import com.astrim.pos.ui.common.GradientButton
import com.astrim.pos.ui.common.SectionCard
import com.astrim.pos.ui.common.SectionTitle
import com.astrim.pos.ui.common.StepperButton
import com.astrim.pos.ui.common.formatCurrency
import java.math.BigDecimal

private val TotalGreen = Color(0xFF4CAF50)
private val AccentBlue = Color(0xFF4A6FA5)
private val EditBlue = Color(0xFF64B5F6)
private val DeleteRed = Color(0xFFEF5350)

/**
 * Venta rápida de mostrador (Fase 3, rediseño visual) — buscar un producto
 * en el catálogo lo agrega al carrito con un solo toque, el carrito se ve
 * como una tabla tipo hoja de cálculo (cantidad ajustable en línea o desde
 * un diálogo), y se cobra con uno o más medios de pago. Sin campo de
 * código de barras a propósito: Android es para meseros/vendedores/
 * despacho, que seleccionan del catálogo — el escaneo con lector físico
 * sigue siendo exclusivo del escritorio (`sale_view.py`) y de su propia
 * API (`SalesViewModel.onBarcodeSubmit`/`CatalogRepository
 * .findProductByBarcode` quedan intactos por si se reactiva más adelante).
 * Todo cálculo (subtotal, descuentos, impuestos, total, validación de
 * stock) es del backend — ver [SalesViewModel].
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SalesScreen(onBack: () -> Unit, onOpenHistory: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: SalesViewModel = viewModel(
        factory = viewModelFactory {
            initializer {
                SalesViewModel(
                    container.catalogRepository,
                    container.salesRepository,
                    container.customerRepository,
                    container.paymentMethodsRepository,
                )
            }
        },
    )
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        containerColor = AppBackground,
        topBar = {
            TopAppBar(
                title = { Text("Venta", fontSize = 20.sp, fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Volver")
                    }
                },
                actions = {
                    HistoryButton(onClick = onOpenHistory, modifier = Modifier.padding(end = 12.dp))
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = AppBackground),
            )
        },
    ) { paddingValues ->
        val completedSale = uiState.completedSale
        Box(modifier = Modifier.fillMaxSize().background(AppBackground).padding(paddingValues)) {
            if (completedSale != null) {
                SaleCompletedContent(
                    sale = completedSale,
                    changeDue = uiState.changeDue,
                    onNewSale = viewModel::onStartNewSale,
                )
            } else {
                SalesForm(uiState = uiState, viewModel = viewModel)
            }
        }
    }

    val editingIndex = uiState.editingLineIndex
    val draft = uiState.draft
    if (editingIndex != null && draft != null && editingIndex < draft.items.size) {
        EditLineDialog(
            line = draft.items[editingIndex],
            onDismiss = viewModel::onDismissEditLine,
            onConfirm = viewModel::onConfirmEditLine,
        )
    }

    if (uiState.manualPaymentMethod != null) {
        ManualPaymentDialog(
            uiState = uiState,
            onConfirm = viewModel::onConfirmManualPayment,
            onDismiss = viewModel::onDismissManualPayment,
        )
    }
}

/** Pastilla con borde redondeado en el encabezado — solo abre el
 * historial de ventas, réplica de solo lectura de `SalesHistoryView` del
 * escritorio (ver [com.astrim.pos.ui.saleshistory.SalesHistoryScreen]). */
@Composable
private fun HistoryButton(onClick: () -> Unit, modifier: Modifier = Modifier) {
    val shape = RoundedCornerShape(20.dp)
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = modifier
            .clip(shape)
            .background(color = AppCardBackground, shape = shape)
            .border(width = 1.dp, color = AppOutline, shape = shape)
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 8.dp),
    ) {
        Text("🕒", fontSize = 14.sp)
        Text(
            text = "Historial",
            color = Color.White,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(start = 6.dp),
        )
    }
}

@Composable
private fun SalesForm(uiState: SalesUiState, viewModel: SalesViewModel) {
    LazyColumn(
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp),
        modifier = Modifier.fillMaxSize(),
    ) {
        item { ClienteCard(uiState = uiState, viewModel = viewModel) }
        item { BuscarProductoCard(uiState = uiState, viewModel = viewModel) }
        item { DetalleVentaCard(uiState = uiState, viewModel = viewModel) }
        item { ResumenCard(draft = uiState.draft) }
        item { PagoCard(uiState = uiState, viewModel = viewModel) }
        item {
            val draft = uiState.draft
            val canComplete = draft != null && draft.items.isNotEmpty() &&
                uiState.payments.isNotEmpty() && !uiState.isCompleting
            val cobrarText = if (draft != null && draft.items.isNotEmpty()) {
                "Cobrar ${formatCurrency(draft.total)}"
            } else {
                "Cobrar"
            }
            GradientButton(
                text = cobrarText,
                onClick = viewModel::onCompleteSale,
                enabled = canComplete,
                isLoading = uiState.isCompleting,
                modifier = Modifier.fillMaxWidth().padding(top = 4.dp, bottom = 20.dp),
            )
        }
    }
}

@Composable
private fun ClienteCard(uiState: SalesUiState, viewModel: SalesViewModel) {
    SectionCard {
        SectionTitle(icon = Icons.Default.Person, emoji = null, text = "Cliente (Opcional)", tint = AccentBlue)
        val selectedCustomer = uiState.selectedCustomer
        if (selectedCustomer != null) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column {
                    Text(selectedCustomer.fullName, color = Color.White, fontWeight = FontWeight.Bold)
                    Text(
                        "Deuda actual: ${formatCurrency(selectedCustomer.currentDebt)}",
                        color = AppTextSecondary,
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                IconButton(onClick = viewModel::onClearRegisteredCustomer) {
                    Icon(Icons.Default.Close, contentDescription = "Quitar cliente", tint = AppTextSecondary)
                }
            }
        } else {
            DarkOutlinedField(
                value = uiState.customerName,
                onValueChange = {
                    viewModel.onCustomerNameChange(it)
                    viewModel.onCustomerSearchTextChange(it)
                },
                label = "Nombre del cliente",
                modifier = Modifier.fillMaxWidth(),
            )
            if (uiState.customerSearchText.isNotBlank()) {
                CustomerSuggestions(uiState.filteredCustomers, onSelect = viewModel::onSelectRegisteredCustomer)
            }
            DarkOutlinedField(
                value = uiState.customerDocument,
                onValueChange = viewModel::onCustomerDocumentChange,
                label = "Documento",
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
            )
        }
    }
}

@Composable
private fun CustomerSuggestions(customers: List<CustomerDto>, onSelect: (CustomerDto) -> Unit) {
    if (customers.isEmpty()) {
        Text(
            "No hay clientes que coincidan con la búsqueda.",
            color = AppTextMuted,
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(top = 4.dp),
        )
        return
    }
    Column(modifier = Modifier.padding(top = 4.dp)) {
        customers.take(5).forEach { customer ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(AppOutline, RoundedCornerShape(10.dp))
                    .padding(12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(customer.fullName, color = Color.White, fontWeight = FontWeight.Bold)
                    val document = customer.documentId
                    if (!document.isNullOrBlank()) {
                        Text(document, color = AppTextSecondary, style = MaterialTheme.typography.bodySmall)
                    }
                }
                TextButton(onClick = { onSelect(customer) }) { Text("Elegir") }
            }
            Box(modifier = Modifier.height(6.dp))
        }
    }
}

@Composable
private fun BuscarProductoCard(uiState: SalesUiState, viewModel: SalesViewModel) {
    SectionCard {
        SectionTitle(icon = Icons.Default.Search, emoji = null, text = "Buscar producto", tint = AccentBlue)
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            DarkOutlinedField(
                value = uiState.searchText,
                onValueChange = viewModel::onSearchTextChange,
                label = "Buscar por nombre, SKU o categoría",
                modifier = Modifier.weight(1f),
            )
            Button(
                onClick = { uiState.filteredProducts.firstOrNull()?.let(viewModel::onAddProduct) },
                enabled = uiState.filteredProducts.isNotEmpty(),
                colors = ButtonDefaults.buttonColors(containerColor = AccentBlue, contentColor = Color.White, disabledContainerColor = AppOutline, disabledContentColor = AppTextMuted),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.padding(start = 12.dp).height(56.dp),
            ) {
                Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(18.dp))
                Text("Agregar", modifier = Modifier.padding(start = 4.dp))
            }
        }
        if (uiState.searchText.isNotBlank()) {
            if (uiState.filteredProducts.isEmpty()) {
                Text(
                    "No hay productos que coincidan con la búsqueda.",
                    color = AppTextMuted,
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(top = 12.dp),
                )
            } else {
                Column(modifier = Modifier.padding(top = 12.dp)) {
                    uiState.filteredProducts.take(6).forEach { product ->
                        ProductSearchRow(product = product, onClick = { viewModel.onAddProduct(product) })
                        Box(modifier = Modifier.height(8.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun ProductSearchRow(product: ProductSummaryDto, onClick: () -> Unit) {
    Card(
        onClick = onClick,
        shape = RoundedCornerShape(10.dp),
        colors = CardDefaults.cardColors(containerColor = AppOutline),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Column {
                Text(product.name, color = Color.White, fontWeight = FontWeight.Bold)
                Text(product.sku, color = AppTextSecondary, style = MaterialTheme.typography.bodySmall)
            }
            Text(formatCurrency(product.unitPrice), color = Color.White)
        }
    }
}

/**
 * "Detalle de venta" — tabla tipo hoja de cálculo: encabezado de columnas,
 * líneas divisoras horizontales entre filas y verticales entre columnas.
 * Cantidad se ajusta con los botones "−"/"+" en línea (un toque) o con el
 * diálogo del lápiz (cantidad exacta + nota) — ver [EditLineDialog].
 */
@Composable
private fun DetalleVentaCard(uiState: SalesUiState, viewModel: SalesViewModel) {
    SectionCard {
        SectionTitle(icon = Icons.Default.ShoppingCart, emoji = null, text = "Detalle de venta", tint = AccentBlue)
        val draft = uiState.draft
        Box(modifier = Modifier.padding(top = 12.dp)) {
            if (draft == null || draft.items.isEmpty()) {
                Text(
                    "El carrito está vacío.",
                    color = AppTextMuted,
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(vertical = 12.dp),
                )
            } else {
                Column {
                    TableHeaderRow()
                    HorizontalDivider(color = AppOutline)
                    draft.items.forEachIndexed { index, line ->
                        TableLineRow(
                            line = line,
                            onIncrement = { viewModel.onIncrementLine(index) },
                            onDecrement = { viewModel.onDecrementLine(index) },
                            onEdit = { viewModel.onEditLine(index) },
                            onRemove = { viewModel.onRemoveLine(index) },
                        )
                        HorizontalDivider(color = AppOutline)
                    }
                }
            }
        }
        val cartError = uiState.cartError
        if (cartError != null) {
            Text(
                text = cartError,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(top = 8.dp),
            )
        }
    }
}

@Composable
private fun TableHeaderRow() {
    Row(modifier = Modifier.fillMaxWidth().height(IntrinsicSize.Min).padding(bottom = 8.dp)) {
        TableCell(weight = 1.1f) {
            Text("Producto", color = AccentBlue, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
        }
        VerticalDivider()
        TableCell(weight = 1.4f) {
            Text(
                "Cantidad",
                color = AccentBlue,
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.fillMaxWidth(),
                textAlign = TextAlign.Center,
            )
        }
        VerticalDivider()
        TableCell(weight = 0.9f) {
            Text("Precio", color = AccentBlue, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
        }
        VerticalDivider()
        TableCell(weight = 0.9f) {
            Text("Total", color = AccentBlue, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
        }
        VerticalDivider()
        TableCell(weight = 1.3f) { }
    }
}

@Composable
private fun TableLineRow(
    line: SaleDraftLineDto,
    onIncrement: () -> Unit,
    onDecrement: () -> Unit,
    onEdit: () -> Unit,
    onRemove: () -> Unit,
) {
    var showDeleteConfirm by remember { mutableStateOf(false) }
    Row(
        modifier = Modifier.fillMaxWidth().height(IntrinsicSize.Min).padding(vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        TableCell(weight = 1.1f) {
            Column {
                Text(line.productName, color = Color.White, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyMedium)
                val note = line.note
                if (!note.isNullOrBlank()) {
                    Text("Nota: $note", color = AppTextSecondary, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
        VerticalDivider()
        TableCell(weight = 1.4f) {
            Row(
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth(),
            ) {
                StepperButton(symbol = "−", onClick = onDecrement)
                Text(
                    line.quantity.toBigDecimalOrNull()?.stripTrailingZeros()?.toPlainString() ?: line.quantity,
                    color = Color.White,
                    modifier = Modifier.padding(horizontal = 8.dp),
                )
                StepperButton(symbol = "+", onClick = onIncrement)
            }
        }
        VerticalDivider()
        TableCell(weight = 0.9f) {
            Text(formatCurrency(line.unitPrice), color = AppTextSecondary, style = MaterialTheme.typography.bodyMedium)
        }
        VerticalDivider()
        TableCell(weight = 0.9f) {
            Text(formatCurrency(line.lineTotal), color = Color.White, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyMedium)
        }
        VerticalDivider()
        TableCell(weight = 1.3f) {
            Row {
                IconButton(onClick = onEdit, modifier = Modifier.size(28.dp)) {
                    Icon(Icons.Default.Edit, contentDescription = "Editar", tint = EditBlue, modifier = Modifier.size(18.dp))
                }
                IconButton(
                    onClick = { showDeleteConfirm = true },
                    modifier = Modifier.size(28.dp).padding(start = 6.dp),
                ) {
                    Icon(Icons.Default.Delete, contentDescription = "Eliminar", tint = DeleteRed, modifier = Modifier.size(18.dp))
                }
            }
        }
    }
    if (showDeleteConfirm) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirm = false },
            title = { Text("¿Desea eliminar este producto?") },
            text = { Text(line.productName) },
            confirmButton = {
                TextButton(onClick = { showDeleteConfirm = false; onRemove() }) {
                    Text("Eliminar", color = DeleteRed)
                }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteConfirm = false }) { Text("Cancelar") }
            },
        )
    }
}

@Composable
private fun VerticalDivider() {
    Box(
        modifier = Modifier
            .fillMaxHeight()
            .width(1.dp)
            .background(AppOutline),
    )
}

@Composable
private fun RowScope.TableCell(
    weight: Float,
    content: @Composable () -> Unit,
) {
    Box(
        modifier = Modifier.weight(weight).padding(horizontal = 6.dp),
        contentAlignment = Alignment.CenterStart,
    ) {
        content()
    }
}

@Composable
private fun ResumenCard(draft: SaleDraftDto?) {
    if (draft == null) return
    SectionCard {
        TotalRow("Subtotal", draft.subtotal)
        if (draft.discountTotal.toBigDecimalOrNull()?.signum() == 1) {
            TotalRow("Descuentos", "-${draft.discountTotal}")
        }
        if (draft.taxTotal.toBigDecimalOrNull()?.signum() == 1) {
            TotalRow("Impuestos", draft.taxTotal)
        }
        HorizontalDivider(color = AppOutline, modifier = Modifier.padding(vertical = 10.dp))
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("Total", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 22.sp)
            Text(formatCurrency(draft.total), color = TotalGreen, fontWeight = FontWeight.Bold, fontSize = 22.sp)
        }
    }
}

@Composable
private fun TotalRow(label: String, amount: String) {
    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = AppTextSecondary, style = MaterialTheme.typography.bodyMedium)
        Text(formatCurrency(amount), color = AppTextSecondary, style = MaterialTheme.typography.bodyMedium)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PagoCard(uiState: SalesUiState, viewModel: SalesViewModel) {
    SectionCard {
        SectionTitle(icon = null, emoji = "💳", text = "Pago")
        Row(modifier = Modifier.fillMaxWidth().padding(top = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            var expanded by remember { mutableStateOf(false) }
            ExposedDropdownMenuBox(
                expanded = expanded,
                onExpandedChange = { expanded = it },
                modifier = Modifier.weight(1f),
            ) {
                DarkOutlinedField(
                    value = uiState.selectedPaymentMethod.label,
                    onValueChange = {},
                    label = "Método",
                    readOnly = true,
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
                    modifier = Modifier.menuAnchor().fillMaxWidth(),
                )
                ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                    uiState.availablePaymentMethods.forEach { option ->
                        DropdownMenuItem(
                            text = { Text(option.label) },
                            onClick = {
                                viewModel.onPaymentMethodSelected(option)
                                expanded = false
                            },
                        )
                    }
                }
            }
            if (!requiresManualPaymentDialog(uiState.selectedPaymentMethod)) {
                DarkOutlinedField(
                    value = uiState.paymentAmountText,
                    onValueChange = viewModel::onPaymentAmountChange,
                    label = "Monto recibido",
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    modifier = Modifier.weight(1f).padding(start = 12.dp),
                )
            }
        }
        if (requiresManualPaymentDialog(uiState.selectedPaymentMethod)) {
            Button(
                onClick = { viewModel.onOpenManualPayment(uiState.selectedPaymentMethod) },
                colors = ButtonDefaults.buttonColors(containerColor = AccentBlue, contentColor = Color.White, disabledContainerColor = AppOutline, disabledContentColor = AppTextMuted),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.padding(top = 12.dp),
            ) {
                Text("Pagar con ${uiState.selectedPaymentMethod.label}")
            }
        } else {
            Button(
                onClick = viewModel::onAddPayment,
                colors = ButtonDefaults.buttonColors(containerColor = AccentBlue, contentColor = Color.White, disabledContainerColor = AppOutline, disabledContentColor = AppTextMuted),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.padding(top = 12.dp),
            ) {
                Text("Agregar pago")
            }
        }
        val paymentError = uiState.paymentError
        if (paymentError != null) {
            Text(paymentError, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 8.dp))
        }
        if (uiState.payments.isNotEmpty()) {
            Column(modifier = Modifier.padding(top = 12.dp)) {
                uiState.payments.forEachIndexed { index, payment ->
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text("${payment.method.label} — ${formatCurrency(payment.amount.toPlainString())}", color = Color.White)
                        IconButton(onClick = { viewModel.onRemovePayment(index) }) {
                            Icon(Icons.Default.Close, contentDescription = "Quitar pago", tint = AppTextSecondary)
                        }
                    }
                }
                Text(
                    "Pagado: ${formatCurrency(totalPaid(uiState.payments).toPlainString())}",
                    color = AppTextSecondary,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
        }
        if (uiState.changeDue.signum() == 1) {
            Text(
                "Cambio: ${formatCurrency(uiState.changeDue.toPlainString())}",
                color = TotalGreen,
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(top = 8.dp),
            )
        }
        val completeError = uiState.completeError
        if (completeError != null) {
            Text(completeError, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 8.dp))
        }
    }
}

/**
 * Réplica visual de `QrPaymentDialog`/`NequiPaymentDialog`/`BreBPaymentDialog`
 * del escritorio: muestra en vivo la configuración registrada en
 * Administración → Pagos electrónicos (imagen de QR, número de Nequi o
 * llave Bre-B) — nunca un valor fijo en la app (ver API.md §3.12). Si el
 * administrador no configuró ese método, el botón "Confirmar pago" queda
 * deshabilitado, igual que el escritorio deshabilita `accept_button` en
 * `QrPaymentDialog.__init__` cuando no hay imagen.
 */
@Composable
private fun ManualPaymentDialog(
    uiState: SalesUiState,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
) {
    val container = LocalAppContainer.current
    val method = uiState.manualPaymentMethod ?: return
    val configReady = when (method) {
        PaymentMethodOption.QR -> uiState.manualPaymentQrConfig != null
        PaymentMethodOption.NEQUI -> uiState.manualPaymentNequiConfig != null
        PaymentMethodOption.BRE_B -> uiState.manualPaymentBreBConfig != null
        else -> false
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Pago con ${method.label}") },
        text = {
            Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.fillMaxWidth()) {
                when {
                    uiState.isLoadingManualPaymentConfig -> CircularProgressIndicator()
                    uiState.manualPaymentError != null -> Text(
                        text = uiState.manualPaymentError,
                        color = MaterialTheme.colorScheme.error,
                    )
                    method == PaymentMethodOption.QR -> {
                        val qrConfig = uiState.manualPaymentQrConfig
                        if (qrConfig != null) {
                            Text(qrConfig.name, style = MaterialTheme.typography.titleMedium)
                            if (qrConfig.hasImage) {
                                AsyncImage(
                                    model = ImageRequest.Builder(LocalContext.current)
                                        .data(container.paymentMethodsRepository.qrImageUrl(qrConfig.id))
                                        .crossfade(true)
                                        .build(),
                                    imageLoader = container.productImageLoader,
                                    contentDescription = "Código QR",
                                    modifier = Modifier.padding(top = 12.dp).size(240.dp),
                                )
                            }
                            Text(
                                text = "Escanee este código con la aplicación de su banco.",
                                style = MaterialTheme.typography.bodySmall,
                                modifier = Modifier.padding(top = 12.dp),
                            )
                        }
                    }
                    method == PaymentMethodOption.NEQUI -> {
                        val nequiConfig = uiState.manualPaymentNequiConfig
                        if (nequiConfig != null) {
                            Text("Número de Nequi", style = MaterialTheme.typography.bodyMedium)
                            Text(
                                nequiConfig.number,
                                style = MaterialTheme.typography.headlineSmall,
                                modifier = Modifier.padding(top = 8.dp),
                            )
                        }
                    }
                    method == PaymentMethodOption.BRE_B -> {
                        val brebConfig = uiState.manualPaymentBreBConfig
                        if (brebConfig != null) {
                            Text("Llave Bre-B", style = MaterialTheme.typography.bodyMedium)
                            Text(
                                brebConfig.key,
                                style = MaterialTheme.typography.headlineSmall,
                                modifier = Modifier.padding(top = 8.dp),
                            )
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onConfirm, enabled = configReady) { Text("Confirmar pago") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } },
    )
}

/**
 * Diálogo del lápiz — NO edita el nombre del producto, solo la cantidad
 * (con botones −/+ o tipeándola, útil para productos por peso) y la nota
 * opcional de la línea, tal como pide el diseño ("Producto, Cantidad
 * actual, Botón -, Botón +, Guardar, Cancelar").
 */
@Composable
private fun EditLineDialog(
    line: SaleDraftLineDto,
    onDismiss: () -> Unit,
    onConfirm: (quantity: String, note: String?) -> Unit,
) {
    var quantityText by remember(line) { mutableStateOf(line.quantity) }
    var noteText by remember(line) { mutableStateOf(line.note.orEmpty()) }
    var error by remember { mutableStateOf<String?>(null) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(line.productName) },
        text = {
            Column {
                Text("Cantidad actual: ${line.quantity}", style = MaterialTheme.typography.bodyMedium)
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.padding(top = 12.dp),
                ) {
                    StepperButton(symbol = "−", onClick = {
                        val current = quantityText.toBigDecimalOrNull() ?: BigDecimal.ONE
                        val next = current - BigDecimal.ONE
                        if (next.signum() > 0) quantityText = next.toPlainString()
                    })
                    OutlinedTextField(
                        value = quantityText,
                        onValueChange = { quantityText = it; error = null },
                        label = { Text("Cantidad") },
                        singleLine = true,
                        isError = error != null,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                        modifier = Modifier.weight(1f).padding(horizontal = 8.dp),
                    )
                    StepperButton(symbol = "+", onClick = {
                        val current = quantityText.toBigDecimalOrNull() ?: BigDecimal.ZERO
                        quantityText = (current + BigDecimal.ONE).toPlainString()
                    })
                }
                val currentError = error
                if (currentError != null) {
                    Text(currentError, color = MaterialTheme.colorScheme.error)
                }
                OutlinedTextField(
                    value = noteText,
                    onValueChange = { noteText = it },
                    label = { Text("Nota (opcional)") },
                    singleLine = true,
                    modifier = Modifier.padding(top = 12.dp),
                )
            }
        },
        confirmButton = {
            Button(onClick = {
                val quantity = quantityText.trim().toBigDecimalOrNull()
                if (quantity == null || quantity.signum() <= 0) {
                    error = "La cantidad debe ser un número mayor que cero."
                    return@Button
                }
                onConfirm(quantityText.trim(), noteText.trim().ifEmpty { null })
            }) { Text("Guardar") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancelar") }
        },
    )
}

@Composable
private fun SaleCompletedContent(
    sale: CompletedSaleDto,
    changeDue: BigDecimal,
    onNewSale: () -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("Venta #${sale.id} completada", color = Color.White, style = MaterialTheme.typography.titleLarge)
        Text(
            text = "Total: ${formatCurrency(sale.total)}",
            color = TotalGreen,
            fontWeight = FontWeight.Bold,
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(top = 8.dp),
        )
        if (changeDue.signum() == 1) {
            Text(
                text = "Cambio a entregar: ${formatCurrency(changeDue.toPlainString())}",
                color = TotalGreen,
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(top = 4.dp),
            )
        }
        LazyColumn(modifier = Modifier.weight(1f).padding(top = 16.dp)) {
            item { Text("Productos", color = Color.White, style = MaterialTheme.typography.titleMedium) }
            items(sale.items) { item ->
                Row(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text("${item.quantity} x ${item.productName}", color = AppTextSecondary)
                    Text(formatCurrency(item.lineTotal), color = Color.White)
                }
            }
            item {
                Text(
                    "Pagos",
                    color = Color.White,
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(top = 16.dp),
                )
            }
            items(sale.payments) { payment ->
                Row(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(paymentMethodLabel(payment.paymentMethod), color = AppTextSecondary)
                    Text(formatCurrency(payment.amount), color = Color.White)
                }
            }
        }
        GradientButton(
            text = "Nueva venta",
            onClick = onNewSale,
            enabled = true,
            modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
        )
    }
}
