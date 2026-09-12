package com.astrim.pos.ui.vendor

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.ShoppingCart
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
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
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.astrim.pos.core.LocalAppContainer
import com.astrim.pos.core.network.dto.OrderDto
import com.astrim.pos.core.network.dto.OrderPreviewDto
import com.astrim.pos.core.network.dto.ProductSummaryDto
import com.astrim.pos.core.network.dto.SaleDraftLineDto
import com.astrim.pos.ui.common.AppBackground
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

private val VendorBlue = Color(0xFF4F8CFF)
private val VendorPurple = Color(0xFF7A5CFF)
private val VendorGreen = Color(0xFF53D769)
private val DeleteRed = Color(0xFFEF5350)

/**
 * Vendedor (rediseño visual) — mismo flujo que "Vendedor" en el escritorio
 * (`restaurant_view.py`/`restaurant_view_model.py`): un pedido rápido sin
 * mesa. Buscar producto lo agrega automáticamente al pedido (un solo
 * toque), la cantidad se ajusta con los botones −/+ en línea o el diálogo
 * del lápiz, y "Enviar pedido" lo confirma — nace sin cobrar y aparece
 * automáticamente en Despacho, réplica de `RestaurantViewModel
 * .confirm_order`. Sin escaneo de código de barras a propósito (misma
 * decisión que Ventas/Catálogo): Android es para vendedores que
 * seleccionan del catálogo, no para lectores físicos. Distinto de Ventas:
 * sin pagos, sin cliente registrado (el escritorio tampoco lo ofrece acá,
 * solo nombre/documento libres). Todo cálculo (subtotal, impuestos, total,
 * validación de stock) es del backend — ver [VendorViewModel].
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VendorScreen(onBack: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: VendorViewModel = viewModel(
        factory = viewModelFactory {
            initializer { VendorViewModel(container.catalogRepository, container.restaurantRepository) }
        },
    )
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        containerColor = AppBackground,
        topBar = {
            TopAppBar(
                title = { Text("Vendedor", fontSize = 20.sp, fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Volver")
                    }
                },
                actions = {
                    ClientePillButton(modifier = Modifier.padding(end = 12.dp))
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = AppBackground),
            )
        },
    ) { paddingValues ->
        val confirmedOrder = uiState.confirmedOrder
        Box(modifier = Modifier.fillMaxSize().background(AppBackground).padding(paddingValues)) {
            if (confirmedOrder != null) {
                OrderSentContent(order = confirmedOrder, onNewOrder = viewModel::onStartNewOrder)
            } else {
                VendorForm(uiState = uiState, viewModel = viewModel)
            }
        }
    }

    val editingIndex = uiState.editingLineIndex
    val previewLine = uiState.preview?.items?.getOrNull(editingIndex ?: -1)
    if (editingIndex != null && previewLine != null) {
        EditLineDialog(
            line = previewLine,
            onDismiss = viewModel::onDismissEditLine,
            onConfirm = viewModel::onConfirmEditLine,
        )
    }
}

/** Pastilla "👤 Cliente" del encabezado — hoy es solo decorativa: en
 * futuras versiones abrirá el historial/información del cliente, tal
 * como pide el diseño. No hace nada todavía a propósito (no se pidió
 * construir esa pantalla en esta fase). */
@Composable
private fun ClientePillButton(modifier: Modifier = Modifier) {
    val shape = RoundedCornerShape(20.dp)
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = modifier
            .clip(shape)
            .background(color = AppOutline, shape = shape)
            .padding(horizontal = 14.dp, vertical = 8.dp),
    ) {
        Icon(Icons.Default.Person, contentDescription = null, tint = VendorPurple, modifier = Modifier.size(18.dp))
        Text(
            text = "Cliente",
            color = Color.White,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(start = 6.dp),
        )
    }
}

@Composable
private fun VendorForm(uiState: VendorUiState, viewModel: VendorViewModel) {
    val productsById = remember(uiState.products) { uiState.products.associateBy { it.id } }
    LazyColumn(
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
        modifier = Modifier.fillMaxSize(),
    ) {
        item { ClienteCard(uiState = uiState, viewModel = viewModel) }
        item { BuscarProductoCard(uiState = uiState, viewModel = viewModel) }
        item { PedidoCard(uiState = uiState, viewModel = viewModel, productsById = productsById) }
        val preview = uiState.preview
        if (preview != null && uiState.items.isNotEmpty()) {
            item { ResumenCard(preview = preview) }
        }
        item {
            val sendError = uiState.sendError
            if (sendError != null) {
                Text(
                    text = sendError,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(bottom = 8.dp),
                )
            }
            val canSend = uiState.items.isNotEmpty() && !uiState.isSending && !uiState.isCartLoading
            GradientButton(
                text = "Enviar pedido",
                onClick = viewModel::onSendOrder,
                enabled = canSend,
                isLoading = uiState.isSending,
                icon = Icons.AutoMirrored.Filled.Send,
                gradientStart = VendorBlue,
                gradientEnd = VendorPurple,
                modifier = Modifier.fillMaxWidth().padding(bottom = 20.dp),
            )
        }
    }
}

@Composable
private fun ClienteCard(uiState: VendorUiState, viewModel: VendorViewModel) {
    SectionCard {
        SectionTitle(icon = Icons.Default.Person, emoji = null, text = "Cliente (Opcional)", tint = VendorPurple)
        DarkOutlinedField(
            value = uiState.customerName,
            onValueChange = viewModel::onCustomerNameChange,
            label = "Ingrese el nombre del cliente",
            leadingIcon = { Icon(Icons.Outlined.Person, contentDescription = null, tint = AppTextSecondary) },
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
        )
        DarkOutlinedField(
            value = uiState.customerDocument,
            onValueChange = viewModel::onCustomerDocumentChange,
            label = "Número de documento",
            leadingIcon = { Text("🪪", fontSize = 16.sp) },
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
        )
    }
}

@Composable
private fun BuscarProductoCard(uiState: VendorUiState, viewModel: VendorViewModel) {
    SectionCard {
        SectionTitle(icon = Icons.Default.Search, emoji = null, text = "Buscar producto", tint = VendorBlue)
        DarkOutlinedField(
            value = uiState.searchText,
            onValueChange = viewModel::onSearchTextChange,
            label = "Buscar por nombre o código SKU",
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
        )
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
                        Box(modifier = Modifier.padding(top = 8.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun ProductSearchRow(product: ProductSummaryDto, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(AppOutline)
            .clickable(onClick = onClick)
            .padding(12.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Column {
            Text(product.name, color = Color.White, fontWeight = FontWeight.Bold)
            Text(product.sku, color = AppTextSecondary, style = MaterialTheme.typography.bodySmall)
        }
        Text(formatCurrency(product.unitPrice), color = Color.White)
    }
}

@Composable
private fun PedidoCard(uiState: VendorUiState, viewModel: VendorViewModel, productsById: Map<Int, ProductSummaryDto>) {
    val container = LocalAppContainer.current
    SectionCard {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            SectionTitle(icon = Icons.Default.ShoppingCart, emoji = null, text = "Pedido", tint = VendorBlue)
            if (uiState.items.isNotEmpty()) {
                val count = uiState.items.size
                Text(
                    text = if (count == 1) "1 producto" else "$count productos",
                    color = VendorBlue,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier
                        .clip(RoundedCornerShape(12.dp))
                        .background(VendorBlue.copy(alpha = 0.15f))
                        .padding(horizontal = 10.dp, vertical = 4.dp),
                )
            }
        }
        val preview = uiState.preview
        if (uiState.items.isEmpty()) {
            Text(
                "El pedido está vacío.",
                color = AppTextMuted,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 12.dp),
            )
        } else if (preview != null) {
            Column(modifier = Modifier.padding(top = 12.dp)) {
                preview.items.forEachIndexed { index, line ->
                    PedidoLineRow(
                        line = line,
                        imageUrl = productsById[line.productId]?.let { container.catalogRepository.imageUrl(it.id, it.imagePath) },
                        onIncrement = { viewModel.onIncrementLine(index) },
                        onDecrement = { viewModel.onDecrementLine(index) },
                        onEdit = { viewModel.onEditLine(index) },
                        onRemove = { viewModel.onRemoveLine(index) },
                    )
                    if (index < preview.items.lastIndex) {
                        HorizontalDivider(color = AppOutline, modifier = Modifier.padding(vertical = 12.dp))
                    }
                }
            }
        }
        val cartError = uiState.cartError
        if (cartError != null) {
            Text(cartError, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 8.dp))
        }
        if (uiState.isCartLoading) {
            Box(modifier = Modifier.fillMaxWidth().padding(top = 8.dp), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
            }
        }
    }
}

@Composable
private fun PedidoLineRow(
    line: SaleDraftLineDto,
    imageUrl: String?,
    onIncrement: () -> Unit,
    onDecrement: () -> Unit,
    onEdit: () -> Unit,
    onRemove: () -> Unit,
) {
    var showDeleteConfirm by remember { mutableStateOf(false) }
    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        ProductThumbnail(imageUrl = imageUrl, contentDescription = line.productName)
        Column(modifier = Modifier.weight(1f).padding(start = 12.dp)) {
            Text(line.productName, color = Color.White, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyMedium)
            Text(formatCurrency(line.unitPrice), color = VendorBlue, style = MaterialTheme.typography.bodySmall)
            val note = line.note
            if (!note.isNullOrBlank()) {
                Text("Nota: $note", color = AppTextSecondary, style = MaterialTheme.typography.bodySmall)
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(horizontal = 8.dp)) {
            StepperButton(symbol = "−", onClick = onDecrement, size = 36.dp)
            Text(
                line.quantity.toBigDecimalOrNull()?.stripTrailingZeros()?.toPlainString() ?: line.quantity,
                color = Color.White,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(horizontal = 10.dp),
            )
            StepperButton(symbol = "+", onClick = onIncrement, size = 36.dp)
        }
        Text(
            formatCurrency(line.lineTotal),
            color = Color.White,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(horizontal = 8.dp),
        )
        Column {
            IconButton(onClick = onEdit, modifier = Modifier.size(30.dp)) {
                Icon(Icons.Default.Edit, contentDescription = "Editar", tint = VendorBlue, modifier = Modifier.size(18.dp))
            }
            IconButton(onClick = { showDeleteConfirm = true }, modifier = Modifier.size(30.dp).padding(top = 4.dp)) {
                Icon(Icons.Default.Delete, contentDescription = "Eliminar", tint = DeleteRed, modifier = Modifier.size(18.dp))
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
private fun ProductThumbnail(imageUrl: String?, contentDescription: String) {
    val container = LocalAppContainer.current
    val modifier = Modifier.size(70.dp).clip(RoundedCornerShape(10.dp))
    if (imageUrl == null) {
        Box(modifier = modifier.background(AppOutline), contentAlignment = Alignment.CenterStart) {
            Text("📦", fontSize = 22.sp, modifier = Modifier.fillMaxWidth().padding(start = 22.dp))
        }
        return
    }
    AsyncImage(
        model = ImageRequest.Builder(LocalContext.current).data(imageUrl).crossfade(true).build(),
        imageLoader = container.productImageLoader,
        contentDescription = contentDescription,
        contentScale = ContentScale.Crop,
        modifier = modifier.background(AppOutline),
    )
}

@Composable
private fun ResumenCard(preview: OrderPreviewDto) {
    SectionCard {
        SectionTitle(icon = null, emoji = "🧾", text = "Resumen del pedido", tint = VendorBlue)
        Column(modifier = Modifier.padding(top = 12.dp)) {
            TotalRow("Subtotal", preview.subtotal)
            if (preview.discountTotal.toBigDecimalOrNull()?.signum() == 1) {
                TotalRow("Descuentos", "-${preview.discountTotal}")
            }
            if (preview.taxTotal.toBigDecimalOrNull()?.signum() == 1) {
                TotalRow("Impuestos", preview.taxTotal)
            }
            HorizontalDivider(color = AppOutline, modifier = Modifier.padding(vertical = 10.dp))
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Total", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 22.sp)
                Text(formatCurrency(preview.total), color = VendorGreen, fontWeight = FontWeight.Bold, fontSize = 22.sp)
            }
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

/**
 * Diálogo del lápiz — NO edita el nombre del producto, solo la cantidad
 * (con botones −/+ o tipeándola) y la nota opcional de la línea, mismo
 * criterio que el diálogo equivalente de Ventas.
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
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 12.dp)) {
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
private fun OrderSentContent(order: OrderDto, onNewOrder: () -> Unit) {
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("Pedido #${order.id} enviado a Despacho", color = Color.White, style = MaterialTheme.typography.titleLarge)
        Text(
            text = "Cliente: ${order.customerName ?: "Consumidor Final"}",
            color = AppTextSecondary,
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(top = 8.dp),
        )
        LazyColumn(modifier = Modifier.weight(1f).padding(top = 16.dp)) {
            item { Text("Productos", color = Color.White, style = MaterialTheme.typography.titleMedium) }
            items(order.items) { item ->
                Row(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text("${item.quantity} x ${item.productName}", color = AppTextSecondary)
                    val notes = item.notes
                    if (!notes.isNullOrBlank()) {
                        Text(notes, color = AppTextSecondary, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
        GradientButton(
            text = "Nuevo pedido",
            onClick = onNewOrder,
            enabled = true,
            gradientStart = VendorBlue,
            gradientEnd = VendorPurple,
            modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
        )
    }
}
