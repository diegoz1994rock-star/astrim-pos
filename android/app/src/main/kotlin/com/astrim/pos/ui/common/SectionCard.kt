package com.astrim.pos.ui.common

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Contenedor base de cada sección (Venta, Vendedor) — fondo gris oscuro,
 * esquinas redondeadas de 16dp y 16dp de padding interno, un solo lugar
 * para que ambas pantallas se vean idénticas en vez de "parecidas". */
@Composable
fun SectionCard(content: @Composable ColumnScope.() -> Unit) {
    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = AppCardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(16.dp), content = content)
    }
}

/** Título de sección con ícono Material o, si el ícono no existe en
 * `material-icons-core` (ej. "recibo"/"insignia"), un emoji equivalente —
 * mismo criterio que ya usa el resto de la app para no sumar la librería
 * `material-icons-extended` completa por un puñado de íconos sueltos. */
@Composable
fun SectionTitle(icon: ImageVector?, emoji: String?, text: String, tint: Color = Color(0xFF64B5F6)) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        if (icon != null) {
            Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(20.dp))
        } else if (emoji != null) {
            Text(emoji, fontSize = 18.sp)
        }
        Text(
            text = text,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            color = Color.White,
            modifier = Modifier.padding(start = 8.dp),
        )
    }
}
