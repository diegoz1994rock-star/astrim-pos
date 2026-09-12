package com.astrim.pos.ui.catalog

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
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
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.astrim.pos.core.LocalAppContainer
import com.astrim.pos.core.network.dto.CategoryDto
import com.astrim.pos.core.network.dto.ProductSummaryDto
import com.astrim.pos.ui.common.formatCurrency

/**
 * Catálogo del vendedor (Fase 2) — un buscador por nombre que filtra en
 * vivo y el listado de productos resultante, acá en grilla con imagen
 * porque es una pantalla táctil. Sin campo de código de barras a propósito:
 * Android es para meseros/vendedores/despacho, que seleccionan del
 * catálogo — el escaneo con lector físico sigue siendo exclusivo del
 * escritorio (`CatalogViewModel.onBarcodeSubmit`/`CatalogRepository
 * .findProductByBarcode` y el endpoint quedan intactos por si se
 * reactiva más adelante). Ningún cálculo de negocio ocurre acá: solo se
 * listan y filtran productos ya traídos del backend.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CatalogScreen(onBack: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: CatalogViewModel = viewModel(
        factory = viewModelFactory {
            initializer { CatalogViewModel(container.catalogRepository) }
        },
    )
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Catálogo") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Volver")
                    }
                },
            )
        },
    ) { paddingValues ->
        Column(modifier = Modifier.fillMaxSize().padding(paddingValues)) {
            OutlinedTextField(
                value = uiState.searchText,
                onValueChange = viewModel::onSearchTextChange,
                label = { Text("Buscar por nombre, SKU o categoría") },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
            )

            CategoryFilterRow(
                categories = uiState.categories,
                selectedCategoryId = uiState.selectedCategoryId,
                onCategorySelected = viewModel::onCategorySelected,
            )

            when {
                uiState.isLoading -> Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
                uiState.errorMessage != null -> CatalogErrorState(
                    message = uiState.errorMessage.orEmpty(),
                    onRetry = viewModel::load,
                )
                else -> ProductGrid(
                    products = uiState.filteredProducts,
                    imageUrl = { product -> container.catalogRepository.imageUrl(product.id, product.imagePath) },
                    onProductClick = viewModel::onProductSelected,
                )
            }
        }
    }

    val selectedProduct = uiState.selectedProduct
    if (selectedProduct != null) {
        ProductDetailDialog(
            product = selectedProduct,
            imageUrl = container.catalogRepository.imageUrl(selectedProduct.id, selectedProduct.imagePath),
            onDismiss = { viewModel.onProductSelected(null) },
        )
    }
}

@Composable
private fun CategoryFilterRow(
    categories: List<CategoryDto>,
    selectedCategoryId: Int?,
    onCategorySelected: (Int?) -> Unit,
) {
    LazyRow(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
    ) {
        item {
            FilterChip(
                selected = selectedCategoryId == null,
                onClick = { onCategorySelected(null) },
                label = { Text("Todas") },
            )
        }
        items(categories, key = { it.id }) { category ->
            FilterChip(
                selected = selectedCategoryId == category.id,
                onClick = { onCategorySelected(category.id) },
                label = { Text(category.name) },
            )
        }
    }
}

@Composable
private fun CatalogErrorState(message: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(text = message, color = MaterialTheme.colorScheme.error)
        Button(onClick = onRetry, modifier = Modifier.padding(top = 16.dp)) {
            Text("Reintentar")
        }
    }
}

@Composable
private fun ProductGrid(
    products: List<ProductSummaryDto>,
    imageUrl: (ProductSummaryDto) -> String?,
    onProductClick: (ProductSummaryDto) -> Unit,
) {
    if (products.isEmpty()) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text("No hay productos que coincidan con la búsqueda.")
        }
        return
    }
    LazyVerticalGrid(
        columns = GridCells.Adaptive(minSize = 150.dp),
        contentPadding = PaddingValues(16.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        modifier = Modifier.fillMaxSize(),
    ) {
        items(products, key = { it.id }) { product ->
            ProductCard(product = product, imageUrl = imageUrl(product), onClick = { onProductClick(product) })
        }
    }
}

@Composable
private fun ProductCard(product: ProductSummaryDto, imageUrl: String?, onClick: () -> Unit) {
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Column {
            ProductImage(
                imageUrl = imageUrl,
                contentDescription = product.name,
                modifier = Modifier.fillMaxWidth().aspectRatio(1f),
            )
            Column(modifier = Modifier.padding(8.dp)) {
                Text(
                    text = product.name,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Bold,
                    maxLines = 2,
                )
                Text(
                    text = formatCurrency(product.unitPrice),
                    style = MaterialTheme.typography.bodyMedium,
                )
                Text(
                    text = product.sku,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

/** Si el producto no tiene imagen, ni siquiera arma la solicitud de red
 * (que sabemos de antemano que va a dar 404, ver API.md §3.4) — solo
 * muestra un cartel genérico, igual que si la carga real fallara. Texto en
 * vez de un ícono a propósito: `material-icons-extended` (el artefacto que
 * trae íconos como "imagen rota") es mucho más pesado que agregarlo solo
 * para esto — `material-icons-core` (ya usado para Buscar/Volver) no lo
 * incluye. */
@Composable
private fun ProductImage(imageUrl: String?, contentDescription: String, modifier: Modifier = Modifier) {
    if (imageUrl == null) {
        Box(
            modifier = modifier.background(MaterialTheme.colorScheme.surfaceVariant),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = "Sin imagen",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        return
    }
    val container = LocalAppContainer.current
    val context = LocalContext.current
    AsyncImage(
        model = ImageRequest.Builder(context).data(imageUrl).crossfade(true).build(),
        imageLoader = container.productImageLoader,
        contentDescription = contentDescription,
        contentScale = ContentScale.Crop,
        modifier = modifier.background(MaterialTheme.colorScheme.surfaceVariant),
    )
}

@Composable
private fun ProductDetailDialog(product: ProductSummaryDto, imageUrl: String?, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = {
            Button(onClick = onDismiss) { Text("Cerrar") }
        },
        title = { Text(product.name) },
        text = {
            Column {
                ProductImage(
                    imageUrl = imageUrl,
                    contentDescription = product.name,
                    modifier = Modifier.fillMaxWidth().aspectRatio(1f).padding(bottom = 12.dp),
                )
                Text("SKU: ${product.sku}")
                Text("Categoría: ${product.categoryName ?: "Sin categoría"}")
                Text("Precio: ${formatCurrency(product.unitPrice)}")
                Text("Unidad: ${product.unitOfMeasure}")
                if (product.barcodes.isNotEmpty()) {
                    Text("Códigos de barras: ${product.barcodes.joinToString()}")
                }
                if (!product.isActive) {
                    Text(
                        text = "Producto inactivo",
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.padding(top = 8.dp),
                    )
                }
            }
        },
    )
}
