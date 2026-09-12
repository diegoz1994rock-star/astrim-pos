package com.astrim.pos.core.network

import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.ResponseBody.Companion.toResponseBody
import retrofit2.HttpException
import retrofit2.Response

/** Construye un [HttpException] con el mismo cuerpo `{"detail": "..."}`
 * que ya documenta API.md §1/§4, para probar [toApiException] sin un
 * servidor real. */
fun httpErrorException(code: Int, detail: String): HttpException {
    val body = """{"detail":"$detail"}"""
        .toResponseBody("application/json".toMediaTypeOrNull())
    return HttpException(Response.error<Any>(code, body))
}
