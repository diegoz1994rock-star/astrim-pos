package com.astrim.pos.core.catalog

import com.astrim.pos.core.network.ApiClientFactory
import com.astrim.pos.core.network.ApiException
import com.astrim.pos.core.network.ApiService
import com.astrim.pos.core.network.dto.CategoryDto
import com.astrim.pos.core.network.dto.ProductSummaryDto
import com.astrim.pos.core.network.toApiException
import com.astrim.pos.core.session.TokenStore
import java.io.IOException
import retrofit2.HttpException

/** Categorías y catálogo completo de productos, tal como los devuelve el
 * backend — sin filtrar activos/inactivos (esa decisión es de cada
 * pantalla, igual que en el escritorio, ver API.md §3.3/§3.4). */
data class CatalogData(
    val categories: List<CategoryDto>,
    val products: List<ProductSummaryDto>,
)

/** Intervalo de sondeo periódico del catálogo (Catálogo/Ventas/Vendedor) —
 * mismo valor que ya usa el escritorio para su propia sincronización entre
 * estaciones (`ws_client.py::_POLL_INTERVAL_SECONDS = 3.0`), para no
 * inventar un criterio de "tiempo real" distinto al que ya está aceptado
 * en el sistema. Altas/ediciones/bajas de productos hechas en el
 * escritorio quedan reflejadas en Android sin reinstalar ni reiniciar la
 * app, con este mismo margen. */
const val CATALOG_POLL_INTERVAL_MS = 3_000L

/**
 * Sin lógica de negocio propia: cada método es una llamada directa a
 * [ApiService] (ver [SessionRepository][com.astrim.pos.core.session.SessionRepository]
 * para el mismo patrón). La búsqueda instantánea por nombre/categoría vive
 * en la UI (filtra en memoria sobre [CatalogData.products] ya cargado, igual
 * que el buscador del escritorio filtra sobre la tabla ya cargada) — acá
 * solo se resuelve la búsqueda por código de barras, que sí necesita ir al
 * servidor porque un código puede no estar entre los productos ya
 * cargados si el catálogo se pagina en el futuro.
 *
 * `apiServiceFactory` sigue el mismo motivo que en `SessionRepository`:
 * poder probar esta clase en JVM puro con un [ApiService] falso.
 */
class CatalogRepository(
    private val tokenStore: TokenStore,
    private val apiServiceFactory: (baseUrl: String) -> ApiService = { baseUrl ->
        ApiClientFactory.create(baseUrl) { tokenStore.getToken() }
    },
) {
    private fun currentApi(): Result<ApiService> {
        val serverUrl = tokenStore.getServerUrl()
            ?: return Result.failure(
                ApiException(statusCode = 0, message = "No hay una sesión activa con un servidor configurado."),
            )
        return Result.success(apiServiceFactory(serverUrl))
    }

    suspend fun loadCatalog(): Result<CatalogData> {
        val api = currentApi().getOrElse { return Result.failure(it) }
        return try {
            val categories = api.listCategories()
            val products = api.listProducts()
            Result.success(CatalogData(categories, products))
        } catch (e: HttpException) {
            Result.failure(e.toApiException())
        } catch (e: IOException) {
            Result.failure(
                ApiException(statusCode = 0, message = "No se pudo conectar con el servidor. Verificá la red."),
            )
        }
    }

    suspend fun findProductByBarcode(code: String): Result<ProductSummaryDto> {
        val api = currentApi().getOrElse { return Result.failure(it) }
        return try {
            Result.success(api.getProductByBarcode(code))
        } catch (e: HttpException) {
            Result.failure(e.toApiException())
        } catch (e: IOException) {
            Result.failure(
                ApiException(statusCode = 0, message = "No se pudo conectar con el servidor. Verificá la red."),
            )
        }
    }

    /** URL completa (con token cargado vía [com.astrim.pos.core.network.AuthInterceptor]
     * en el cliente HTTP de imágenes, ver [AppContainer][com.astrim.pos.core.AppContainer])
     * para pedir la imagen de un producto — `null` si no hay servidor configurado.
     *
     * `imagePath` se agrega como parámetro de caché (`?v=`) porque el
     * backend sirve la imagen siempre en la misma ruta
     * `/products/{id}/image` sin importar cuál sea el archivo real —
     * `image_path` cambia de nombre en cada carga (ver `image_storage.py
     * ::save_product_image`, que usa un UUID nuevo siempre). Sin este
     * parámetro, Coil seguiría mostrando la imagen vieja en caché después
     * de que el administrador la reemplace, aunque el sondeo periódico
     * (ver [CATALOG_POLL_INTERVAL_MS]) ya haya traído el resto de los
     * datos del producto actualizados. */
    fun imageUrl(productId: Int, imagePath: String?): String? {
        val serverUrl = tokenStore.getServerUrl() ?: return null
        val base = "${serverUrl}api/v1/products/$productId/image"
        return if (imagePath != null) "$base?v=${imagePath.hashCode()}" else base
    }
}
