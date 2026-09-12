package com.astrim.licensemanager.ui.common

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * Mensaje de "todavía no hay nada que mostrar" — usado por Licencias,
 * Empresas e Historial mientras no existe ningún origen de datos real
 * (ver PROGRESS.md del módulo). Un solo lugar para que las 3 pantallas se
 * vean idénticas en vez de "parecidas".
 */
@Composable
fun EmptyStateMessage(emoji: String, title: String, description: String) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(modifier = Modifier.height(80.dp))
        Text(emoji, fontSize = 40.sp)
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            title,
            color = Color.White,
            fontWeight = FontWeight.Bold,
            fontSize = 18.sp,
            textAlign = TextAlign.Center,
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            description,
            color = AppTextSecondary,
            fontSize = 14.sp,
            textAlign = TextAlign.Center,
        )
    }
}
