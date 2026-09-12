package com.astrim.pos.ui.common

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/** Campo de texto con estilo oscuro consistente en toda la app (Venta,
 * Vendedor) — un solo lugar para el color de fondo/borde en vez de
 * repetirlo en cada pantalla. */
@Composable
fun DarkOutlinedField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    readOnly: Boolean = false,
    keyboardOptions: KeyboardOptions = KeyboardOptions.Default,
    leadingIcon: (@Composable () -> Unit)? = null,
    trailingIcon: (@Composable () -> Unit)? = null,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        label = { Text(label) },
        readOnly = readOnly,
        singleLine = true,
        keyboardOptions = keyboardOptions,
        leadingIcon = leadingIcon,
        trailingIcon = trailingIcon,
        colors = OutlinedTextFieldDefaults.colors(
            focusedContainerColor = AppOutline,
            unfocusedContainerColor = AppOutline,
            focusedTextColor = Color.White,
            unfocusedTextColor = Color.White,
            focusedBorderColor = GradientButtonStart,
            unfocusedBorderColor = AppOutline,
            focusedLabelColor = GradientButtonStart,
            unfocusedLabelColor = AppTextSecondary,
            cursorColor = GradientButtonStart,
        ),
        modifier = modifier,
    )
}

/** Botón cuadrado "−"/"+" — mismo control en Venta (ajuste de línea) y
 * Vendedor (ajuste de línea, botones más grandes por diseño). */
@Composable
fun StepperButton(symbol: String, onClick: () -> Unit, size: Dp = 28.dp) {
    Box(
        contentAlignment = Alignment.Center,
        modifier = Modifier
            .size(size)
            .clip(RoundedCornerShape(8.dp))
            .background(AppOutline)
            .clickable(onClick = onClick),
    ) {
        Text(symbol, color = Color.White, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
    }
}
