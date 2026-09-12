package com.astrim.pos.ui.home

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ExitToApp
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.astrim.pos.R
import com.astrim.pos.core.network.dto.SessionInfoDto
import com.astrim.pos.core.session.ModulePermissions
import com.astrim.pos.core.session.hasModuleAccess
import com.astrim.pos.core.session.roleLabel

private data class HomeModule(
    val label: String,
    val icon: String,
    val permissionCode: String,
    val onOpen: () -> Unit,
)

/**
 * Réplica de `_build_nav_panels`/`_panel_visible` del escritorio
 * (`main.py`): el menú no es una lista fija — se arma en cada composición
 * filtrando por lo que [hasModuleAccess] autoriza para el cargo de
 * `session`, igual que el sidebar solo dibuja los paneles cuyo
 * `permission_code` está en `session.permission_codes` (o cualquiera si
 * `is_admin`). Dos usuarios con cargos distintos ven cuadrículas de
 * tarjetas distintas, nunca la misma con algunas deshabilitadas u
 * ocultas a mano — no hay ninguna tarjeta fija que dependa de esconderse
 * después. Solo cambió la presentación (tarjetas en cuadrícula de 2
 * columnas en vez de botones apilados); ningún criterio de acceso se tocó.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    session: SessionInfoDto,
    onLogout: () -> Unit,
    onOpenCatalog: () -> Unit,
    onOpenSales: () -> Unit,
    onOpenDispatch: () -> Unit,
    onOpenCustomers: () -> Unit,
    onOpenCashRegister: () -> Unit,
    onOpenVendor: () -> Unit,
) {
    val modules = listOf(
        HomeModule("Ventas", "🛒", ModulePermissions.SALES, onOpenSales),
        HomeModule("Catálogo", "📦", ModulePermissions.CATALOG, onOpenCatalog),
        HomeModule("Vendedor", "🧾", ModulePermissions.VENDOR, onOpenVendor),
        HomeModule("Despacho", "🚚", ModulePermissions.DISPATCH, onOpenDispatch),
        HomeModule("Clientes", "👥", ModulePermissions.CUSTOMERS, onOpenCustomers),
        HomeModule("Caja", "💰", ModulePermissions.CASH_REGISTER, onOpenCashRegister),
    ).filter { hasModuleAccess(session, it.permissionCode) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("ASTRIM") },
                actions = {
                    IconButton(onClick = onLogout) {
                        Icon(Icons.Default.ExitToApp, contentDescription = "Cerrar sesión")
                    }
                },
            )
        },
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(paddingValues)
                .padding(horizontal = 20.dp, vertical = 16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            // Misma identidad visual que la pantalla de login (`ui/login/
            // LoginScreen.kt`) y que el escritorio (`login_view.py`): logo
            // arriba, wordmark debajo, ambos centrados. Los PNG ya vienen
            // recortados a su contenido visible (ver `docs/branding/`),
            // nunca redibujados.
            Image(
                painter = painterResource(R.drawable.brand_logo),
                contentDescription = null,
                modifier = Modifier.height(72.dp),
            )
            Image(
                painter = painterResource(R.drawable.brand_wordmark),
                contentDescription = null,
                modifier = Modifier.padding(top = 4.dp).width(140.dp),
            )

            Text(
                text = session.fullName,
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 20.dp),
            )
            Text(
                text = "Usuario: ${session.username}",
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 4.dp),
            )
            Text(
                text = "Cargo: ${roleLabel(session)}",
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 2.dp),
            )

            // Cuadrícula de 2 columnas: los módulos se recorren de a pares
            // en vez de usar LazyVerticalGrid a propósito — con a lo sumo
            // un puñado de tarjetas no hace falta virtualización, y así se
            // evita anidar dos contenedores scrolleables (la columna de
            // arriba ya tiene su propio scroll).
            modules.chunked(2).forEach { row ->
                Row(
                    modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    row.forEach { module ->
                        ModuleCard(module = module, modifier = Modifier.weight(1f))
                    }
                    if (row.size == 1) {
                        Spacer(modifier = Modifier.weight(1f))
                    }
                }
            }
        }
    }
}

@Composable
private fun ModuleCard(module: HomeModule, modifier: Modifier = Modifier) {
    Card(
        onClick = module.onOpen,
        modifier = modifier.aspectRatio(1f),
        shape = RoundedCornerShape(20.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
    ) {
        Column(
            modifier = Modifier.fillMaxSize().padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Text(text = module.icon, fontSize = 40.sp)
            Text(
                text = module.label,
                style = MaterialTheme.typography.titleMedium,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 12.dp),
            )
        }
    }
}
