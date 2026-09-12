package com.astrim.pos.core.network

import java.util.concurrent.TimeUnit
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

/**
 * Construye un [ApiService] nuevo para una URL de servidor dada — no hay
 * una URL fija en el código: cada negocio corre su propio servidor ASTRIM
 * en su propia red local (ver API.md, "Base URL"), así que la URL la
 * ingresa el usuario en el login (ver [normalizeServerUrl]) y puede
 * cambiar entre instalaciones.
 */
object ApiClientFactory {
    fun create(baseUrl: String, tokenProvider: () -> String?): ApiService {
        val loggingInterceptor = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BASIC
        }
        val okHttpClient = OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor(tokenProvider))
            .addInterceptor(loggingInterceptor)
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .writeTimeout(15, TimeUnit.SECONDS)
            .build()

        val retrofit = Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()

        return retrofit.create(ApiService::class.java)
    }
}

/**
 * Normaliza lo que el usuario escribe ("192.168.1.50:8765",
 * "http://192.168.1.50:8765", con o sin "/" final) a una base URL válida
 * para Retrofit, que exige esquema y "/" final. Nunca agrega "/api/v1" acá
 * — eso ya es parte de cada ruta declarada en [ApiService], para que la
 * URL base sea solo "protocolo + host + puerto", igual que la muestra el
 * panel de Sincronización del escritorio.
 */
fun normalizeServerUrl(input: String): String {
    var url = input.trim()
    if (!url.startsWith("http://") && !url.startsWith("https://")) {
        url = "http://$url"
    }
    if (!url.endsWith("/")) {
        url = "$url/"
    }
    return url
}
