package com.astrim.pos.core.network

import okhttp3.Interceptor
import okhttp3.Response

/**
 * Agrega `Authorization: Bearer <token>` a toda solicitud saliente, si hay
 * un token guardado. Adjuntarlo también en las rutas públicas
 * (`/auth/login`, `/health`) es inofensivo — el middleware del backend
 * solo lo exige en las rutas protegidas (ver API.md §2.1) — así que este
 * interceptor no necesita saber cuáles son cuáles.
 *
 * `tokenProvider` es una función (no el token directo) para no capturar un
 * valor viejo: se llama en cada solicitud, así que siempre usa el token
 * más reciente que tenga [com.astrim.pos.core.session.TokenStore].
 */
class AuthInterceptor(
    private val tokenProvider: () -> String?,
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        val token = tokenProvider()
        val request = if (token != null) {
            original.newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        } else {
            original
        }
        return chain.proceed(request)
    }
}
