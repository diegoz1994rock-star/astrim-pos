package com.astrim.pos.core

import android.content.Context
import coil.ImageLoader
import com.astrim.pos.core.cashregister.CashRegisterRepository
import com.astrim.pos.core.catalog.CatalogRepository
import com.astrim.pos.core.customers.CustomerRepository
import com.astrim.pos.core.dispatch.DispatchRepository
import com.astrim.pos.core.network.AuthInterceptor
import com.astrim.pos.core.paymentmethods.PaymentMethodsRepository
import com.astrim.pos.core.restaurant.RestaurantRepository
import com.astrim.pos.core.sales.SalesRepository
import com.astrim.pos.core.session.EncryptedTokenStore
import com.astrim.pos.core.session.SessionRepository
import com.astrim.pos.core.session.TokenStore
import okhttp3.OkHttpClient

/**
 * Contenedor de dependencias manual — deliberadamente sin Hilt/Koin. Con
 * pocas dependencias reales, un framework de inyección no aporta nada
 * todavía y suma una etapa de generación de código (KSP/kapt) que este
 * entorno no puede verificar compilando (ver README.md de esta carpeta).
 * Se reevalúa si la cantidad de dependencias crece en fases futuras.
 */
class AppContainer(context: Context) {
    val tokenStore: TokenStore = EncryptedTokenStore(context.applicationContext)
    val sessionRepository: SessionRepository = SessionRepository(tokenStore)
    val catalogRepository: CatalogRepository = CatalogRepository(tokenStore)
    val salesRepository: SalesRepository = SalesRepository(tokenStore)
    val dispatchRepository: DispatchRepository = DispatchRepository(tokenStore)
    val customerRepository: CustomerRepository = CustomerRepository(tokenStore)
    val cashRegisterRepository: CashRegisterRepository = CashRegisterRepository(tokenStore)
    val restaurantRepository: RestaurantRepository = RestaurantRepository(tokenStore)
    val paymentMethodsRepository: PaymentMethodsRepository = PaymentMethodsRepository(tokenStore)

    /** [ImageLoader] propio (no el default de Coil) porque la imagen de
     * producto (`GET /products/{id}/image`, ver API.md §3.4) — y, con el
     * mismo criterio, la del QR de pago (`GET /payment-methods/qr/{id}/image`,
     * API.md §3.12) — exige el mismo `Authorization: Bearer <token>` que el
     * resto de la API. Reutiliza [AuthInterceptor], igual que
     * [com.astrim.pos.core.network.ApiClientFactory]. */
    val productImageLoader: ImageLoader = ImageLoader.Builder(context.applicationContext)
        .okHttpClient(
            OkHttpClient.Builder()
                .addInterceptor(AuthInterceptor(tokenStore::getToken))
                .build(),
        )
        .build()
}
