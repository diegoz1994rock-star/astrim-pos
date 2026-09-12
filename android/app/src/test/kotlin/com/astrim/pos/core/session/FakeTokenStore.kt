package com.astrim.pos.core.session

/** Doble de prueba de [TokenStore] — en memoria, sin Android Framework, para
 * poder probar [SessionRepository] en JVM puro. */
class FakeTokenStore(
    private var serverUrl: String? = null,
    private var token: String? = null,
) : TokenStore {
    override fun saveCredentials(serverUrl: String, token: String) {
        this.serverUrl = serverUrl
        this.token = token
    }

    override fun getServerUrl(): String? = serverUrl

    override fun getToken(): String? = token

    override fun clear() {
        serverUrl = null
        token = null
    }
}
