package com.astrim.pos.ui.common

import java.math.RoundingMode
import java.text.DecimalFormat
import java.text.DecimalFormatSymbols
import java.util.Locale

private val thousandsFormat = DecimalFormat("#,###", DecimalFormatSymbols(Locale.US))

/**
 * Mismo formato que `shared_ui/formatting.py::format_currency` del
 * escritorio (peso colombiano: "." separador de miles, "," decimal, sin
 * símbolo de moneda, y los decimales solo aparecen si hay centavos reales)
 * — para que un mismo precio se vea idéntico en escritorio y Android.
 * Compartida entre Catálogo y Ventas (ambas pantallas muestran precios).
 * `Locale.US` fija el formateador para no depender del locale del
 * teléfono (que puede tener "," como separador de miles).
 */
fun formatCurrency(raw: String): String {
    val value = raw.toBigDecimalOrNull() ?: return raw
    val quantized = value.setScale(2, RoundingMode.HALF_UP)
    val sign = if (quantized.signum() < 0) "-" else ""
    val absValue = quantized.abs()
    val integerPart = absValue.toBigInteger()
    val cents = absValue.subtract(integerPart.toBigDecimal()).movePointRight(2).toInt()
    val integerText = thousandsFormat.format(integerPart).replace(",", ".")
    return if (cents != 0) "$sign$integerText,${cents.toString().padStart(2, '0')}" else "$sign$integerText"
}
