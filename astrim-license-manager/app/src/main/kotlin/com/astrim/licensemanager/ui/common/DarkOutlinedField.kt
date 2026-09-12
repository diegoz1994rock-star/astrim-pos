package com.astrim.licensemanager.ui.common

import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color

/** Campo de texto con estilo oscuro consistente en toda la app — mismo
 * componente que ya usa el POS (android/app/.../ui/common/DarkOutlinedField.kt),
 * un solo lugar para el color de fondo/borde en vez de repetirlo en cada
 * pantalla. */
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
