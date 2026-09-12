package com.astrim.pos.core.session

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Implementación real de [TokenStore]: token y URL del servidor cifrados
 * en disco con Jetpack Security (AES256-GCM) — nunca en
 * `SharedPreferences` planas. Cubre el requisito explícito de la Fase 1,
 * "Persistencia segura del token".
 */
class EncryptedTokenStore(context: Context) : TokenStore {

    private val prefs: SharedPreferences by lazy {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            PREFS_FILE_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    override fun saveCredentials(serverUrl: String, token: String) {
        prefs.edit()
            .putString(KEY_SERVER_URL, serverUrl)
            .putString(KEY_TOKEN, token)
            .apply()
    }

    override fun getServerUrl(): String? = prefs.getString(KEY_SERVER_URL, null)

    override fun getToken(): String? = prefs.getString(KEY_TOKEN, null)

    override fun clear() {
        prefs.edit().clear().apply()
    }

    private companion object {
        const val PREFS_FILE_NAME = "astrim_secure_session"
        const val KEY_SERVER_URL = "server_url"
        const val KEY_TOKEN = "token"
    }
}
