package com.astrim.pos.core.network

import com.google.gson.Gson
import retrofit2.HttpException

/**
 * Todo error de negocio de la API responde `{"detail": "mensaje"}` (ver
 * API.md §1/§4) — este es el único lugar que sabe leer esa forma, para no
 * repetir el parseo en cada pantalla.
 */
private data class ApiErrorBody(val detail: String?)

/** Excepción de dominio con el mensaje real del backend, listo para
 * mostrarlo tal cual en la UI — mismo mensaje que vería un usuario de
 * escritorio para el mismo error. */
class ApiException(val statusCode: Int, message: String) : Exception(message)

/**
 * Traduce el [HttpException] que Retrofit lanza automáticamente para
 * cualquier respuesta no-2xx a un [ApiException] con el `detail` real del
 * backend (ver tabla de códigos en API.md §4) en vez del mensaje genérico
 * de Retrofit ("HTTP 404 Not Found").
 */
fun HttpException.toApiException(): ApiException {
    val httpException = this
    val statusCode = httpException.code()
    val rawBody = httpException.response()?.errorBody()?.string()
    val detail = rawBody
        ?.let { runCatching { Gson().fromJson(it, ApiErrorBody::class.java).detail }.getOrNull() }
        ?: "Error del servidor (código $statusCode)."
    return ApiException(statusCode, detail)
}
