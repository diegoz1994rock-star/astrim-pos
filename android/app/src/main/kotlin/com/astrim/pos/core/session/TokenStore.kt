package com.astrim.pos.core.session

/**
 * Persistencia del token de sesión y la URL del servidor configurada.
 * Interfaz separada de [EncryptedTokenStore] (la implementación real, con
 * Jetpack Security) para poder probar [SessionRepository] en JVM puro con
 * un doble en memoria, sin depender del framework de Android — ver
 * `app/src/test/.../FakeTokenStore.kt`.
 */
interface TokenStore {
    fun saveCredentials(serverUrl: String, token: String)
    fun getServerUrl(): String?
    fun getToken(): String?
    fun clear()
}
