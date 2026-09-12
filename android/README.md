# ASTRIM — Cliente Android

Cliente Android oficial de ASTRIM. Consume exclusivamente la API HTTP documentada en `../API.md` — **no tiene lógica de negocio propia**: toda regla de negocio vive en los `Service` del backend (proyecto principal, `src/pos/`), este cliente solo la refleja.

## Estado: Fase 1 — Infraestructura

Lo que ya funciona: login contra `POST /api/v1/auth/login`, guardado seguro del token, validación de sesión persistida contra `GET /api/v1/auth/me`, y una pantalla Home mínima que confirma la sesión. Las fases 2 en adelante (catálogo, ventas, despacho, etc.) se construyen sobre esta base — ver el plan completo en la conversación de la Fase 1, no repetido acá para no desincronizarse.

## ✅ Compilación real verificada

El JDK 17 y el Android SDK (command-line tools, platform-tools, build-tools, `platforms;android-35`) se instalaron por terminal en `~/android-dev/` y se usaron para compilar el proyecto de verdad: `./gradlew assembleDebug` termina en `BUILD SUCCESSFUL` y genera `app/build/outputs/apk/debug/app-debug.apk`, y `./gradlew test` corre las 11 pruebas unitarias reales (todas en verde). En el camino aparecieron y se corrigieron dos errores reales de compilación (no hipotéticos): un choque de nombre entre el método `code()` y un campo privado del mismo nombre en `retrofit2.HttpException` (resuelto capturando `this` en una variable local antes de llamarlo), y `TopAppBar` de Material3 que requiere `@OptIn(ExperimentalMaterial3Api::class)` por ser una API marcada experimental.

## 1. Instalar Android Studio

1. Descargá Android Studio desde <https://developer.android.com/studio> (incluye JDK y Android SDK — no hace falta instalarlos aparte).
2. Instalalo y abrilo al menos una vez para que baje los componentes del SDK (Android SDK Platform, Build-Tools, Platform-Tools/`adb`).

## 2. Abrir el proyecto

Abrí Android Studio → **Open** → seleccioná esta carpeta (`android/`, **no** la raíz del repo — este es un proyecto Gradle independiente, ver `FOLDER_STRUCTURE.md` del proyecto principal). Android Studio va a sincronizar Gradle automáticamente; la primera vez puede tardar varios minutos (descarga Gradle 8.14.5 y todas las dependencias).

Si Gradle Sync sugiere actualizar AGP/Kotlin/alguna librería a una versión más nueva: **aceptalo** — elegí deliberadamente la última versión *que conozco con certeza que es sintácticamente correcta* en vez de la más nueva posible (ver el comentario en `gradle/libs.versions.toml`), así que es esperable y seguro que Android Studio te ofrezca subir de versión.

## 3. Configurar la conexión al servidor

No hay ninguna URL fija en el código — cada negocio corre su propio servidor ASTRIM en su red local. La URL se ingresa **en la pantalla de Login misma** (campo "Servidor"), por ejemplo:

```
192.168.1.50:8765
```

(el servidor ASTRIM se levanta desde el panel **Sincronización → modo Servidor** de la aplicación de escritorio — ver `API.md` en la raíz del proyecto principal). El celular y la PC con el servidor deben estar en la misma red Wi-Fi/LAN.

## 4. Instalar en tu celular

1. En el celular: **Ajustes → Acerca del teléfono** → tocar 7 veces "Número de compilación" para activar Opciones de desarrollador → **Opciones de desarrollador → Depuración USB** (activar).
2. Conectá el celular por cable USB a la computadora, aceptá el diálogo "¿Confiar en esta computadora?" que aparece en el teléfono.
3. En Android Studio: seleccioná tu dispositivo en el menú desplegable de la barra superior y presioná **Run ▶**.

Alternativa sin cable: **Build → Generate Signed Bundle / APK → APK**, copiar el `.apk` resultante al celular (por ejemplo, por WhatsApp/Drive/USB) e instalarlo manualmente (hay que permitir "Instalar apps de orígenes desconocidos" para esa fuente).

## 5. Correr las pruebas unitarias

```bash
./gradlew test
```

Corren en JVM pura (sin emulador ni dispositivo) — cubren `SessionRepository` (login exitoso/fallido, restauración de sesión, logout) y `normalizeServerUrl`, con dobles de prueba (`FakeApiService`/`FakeTokenStore`), nunca contra el servidor real.

## Decisiones de arquitectura de esta fase

- **Sin Hilt/Koin todavía**: con solo dos dependencias reales (`TokenStore`, `SessionRepository`), un framework de inyección no aporta nada y suma una etapa de generación de código (KSP/kapt) imposible de verificar sin compilador en este entorno. `AppContainer` es un contenedor manual simple — se reevalúa si la cantidad de dependencias crece en fases futuras.
- **Gson, no Moshi/kotlinx.serialization**: Gson no necesita ningún plugin de compilación (`@SerializedName` alcanza) — la opción de menor riesgo dado que no hay forma de compilar y confirmar acá. Es una decisión revisable en una fase de optimización si se prefiere el enfoque más moderno.
- **AGP 8.13.2 / Retrofit 2.12.0 / OkHttp 4.12.0**, no las versiones más nuevas disponibles (AGP 9.x, Retrofit 3.x) — se probó también AGP 9.3.1 con el compilador real, pero AGP 9.x integra Kotlin de forma nativa y ya no acepta el plugin `kotlin-android` por separado (cambio arquitectónico real, no un simple ajuste de sintaxis), así que se volvió a AGP 8.13.2, bajando `core-ktx` (1.15.0), `lifecycle-*` (2.8.7) y `activity-compose` (1.9.3) a versiones compatibles con `compileSdk 35` en vez de subir el compileSdk.
- **`android:usesCleartextTraffic="true"`** en el manifest: el servidor corre por HTTP plano en la red local (ver API.md) — sin esto, Android bloquea la conexión desde API 28. Revisar en la Fase 8 si el despliegue final necesita HTTPS.
- **Wrapper de Gradle real, no escrito a mano**: `gradlew`, `gradlew.bat` y `gradle-wrapper.jar` se descargaron directo del repositorio oficial de Gradle (tag `v8.14.5`), con el checksum SHA-256 de la distribución verificado en `gradle-wrapper.properties` — no son texto generado, son los binarios/scripts reales de esa versión de Gradle.
