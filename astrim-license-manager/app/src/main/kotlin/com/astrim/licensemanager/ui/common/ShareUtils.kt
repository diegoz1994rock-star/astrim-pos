package com.astrim.licensemanager.ui.common

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.widget.Toast

/** Copia texto al portapapeles usando el servicio de plataforma
 * directamente (no el `LocalClipboardManager` de Compose, deprecado a
 * favor de una API basada en suspend que no hace falta para un caso tan
 * simple). */
fun copyToClipboard(context: Context, label: String, text: String) {
    val clipboardManager = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    clipboardManager.setPrimaryClip(ClipData.newPlainText(label, text))
}

/** Comparte texto (código de licencia) por WhatsApp si está instalado, o
 * por el selector genérico de Android si no — todo vía Intent del
 * sistema operativo, sin ninguna llamada de red propia de la app. */
fun shareLicenseText(context: Context, message: String) {
    val whatsAppIntent = Intent(Intent.ACTION_SEND).apply {
        type = "text/plain"
        putExtra(Intent.EXTRA_TEXT, message)
        setPackage("com.whatsapp")
    }
    try {
        context.startActivity(whatsAppIntent)
    } catch (error: Exception) {
        val genericIntent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, message)
        }
        context.startActivity(Intent.createChooser(genericIntent, "Compartir código"))
    }
}

fun showToast(context: Context, message: String) {
    Toast.makeText(context, message, Toast.LENGTH_SHORT).show()
}
