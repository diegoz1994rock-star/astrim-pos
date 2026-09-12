# DESIGN_SYSTEM.md

Especificación oficial del lenguaje visual del sistema POS. Este documento es la única fuente de verdad para color, tipografía, espaciado, radios, elevación, iconografía y movimiento — ninguna pantalla debe definir un valor visual propio que contradiga lo que está aquí (mismo principio que `tokens.py` ya establecía para color, ahora extendido a todo lo demás).

Se construye **sobre** el sistema de tokens que ya existía (`shared_ui/theme/tokens.py` + `theme_manager.py`), no lo reemplaza — esa base (QSS generado a partir de un `ThemeTokens`, aplicado una vez a nivel de `QApplication`) es correcta y se conserva.

Este documento es el resultado de la Fase 0 (auditoría). La implementación ocurre en las fases descritas en el mensaje de entrega, una por una, cada una revisada antes de continuar con la siguiente.

---

## 0. Principios

1. **Un solo lenguaje visual.** Ningún módulo define su propio color, fuente, radio, sombra o espaciado. Todo viene de este documento.
2. **Cada cambio se justifica con evidencia**, no con gusto personal — ver la sección "Hallazgos de auditoría" de la entrega para el porqué de cada decisión.
3. **Restricción, no exceso.** Sombra, color, movimiento e íconos se usan donde comunican algo (estado, jerarquía, retroalimentación) — nunca por decoración.
4. **Rendimiento primero.** Un cajero hace cientos de clics por turno. Ninguna animación puede introducir demora percibida en una acción repetitiva (cobrar, escanear, guardar). Ver §7.
5. **El sistema debe seguir funcionando exactamente igual.** Esta fase es 100% visual — cero cambios de lógica, flujo, permisos o reglas de negocio.

---

## 1. Color

### 1.1 Qué se conserva

La estructura light/dark de `ThemeTokens` y el color primario (`#2F6FED` claro / `#5B8DEF` oscuro, un azul confiable y ya usado en toda la app) se conservan sin cambios — no hay evidencia de que el primario tenga un problema.

### 1.2 Qué cambia y por qué

| Token | Valor actual | Valor propuesto | Por qué |
|---|---|---|---|
| `background` (claro) | `#FFFBE0` (crema/amarillo) | `#F4F5F7` (gris neutro clarísimo) | Un fondo con tinte amarillo compite visualmente con los estados semánticos (que también usan amarillo para "warning") y no es el tono neutro que usan las suites empresariales de referencia (Microsoft 365, SAP Fiori, Stripe Dashboard) — un fondo neutro deja que el color con significado (primario, éxito, alerta, error) sea lo único que llame la atención. |
| `header_accent` | `#F5D76E` (mostaza saturado) | `#E8EBF0` (gris azulado sutil) | Mismo motivo — un encabezado de tabla no debería competir visualmente con una fila en estado "warning" real. |
| `font_family` | `"Comic Sans MS, Chalkboard SE, Comic Sans, Noteworthy, sans-serif"` | `"Segoe UI, SF Pro Text, Helvetica Neue, Ubuntu, Noto Sans, sans-serif"` | Ver §2 — Comic Sans es la fuente por defecto de **todo texto de la app** ahora mismo (`tokens.py:33`). En Windows (plataforma principal del instalador) esto renderiza Comic Sans real. Es el hallazgo de mayor impacto de toda la auditoría. |

### 1.3 Tokens nuevos (no reemplazan nada, llenan un vacío real)

Se encontraron **4 archivos** que redefinen sus propios colores de éxito/alerta/error en vez de usar los tokens (`inventory_table_model.py`, `customer_history_dialog.py`, `profits_table_model.py`, `product_form_dialog.py`) — cada uno con valores ligeramente distintos, y ninguno reacciona al cambiar de tema (se ven mal en modo oscuro). Para eliminar esa duplicación sin perder el matiz que necesitan (una fila necesita un *fondo* tenue, no solo texto de color), se agregan tres tokens nuevos, derivados matemáticamente del token semántico correspondiente (mismo tono, ~85% de opacidad sobre `surface`):

```python
success_tint: str   # fondo sutil para filas/celdas "bien" (pagado, stock normal, margen alto)
warning_tint: str    # fondo sutil para filas/celdas "atención" (stock bajo, margen medio, parcial)
danger_tint: str     # fondo sutil para filas/celdas "mal" (sin stock, vencido, margen bajo)
```

Claro: `#DCF3E3`, `#FCEFD1`, `#FBE1E1`. Oscuro: `#173829`, `#3A2E12`, `#3A1F20`.

Los 4 archivos señalados se migran a estos tokens en la fase correspondiente — mismo resultado visual (son los tonos que ya usaban, casi sin cambio perceptible), pero desde un solo lugar y correctos en ambos temas.

### 1.4 Paleta de datos (gráficos)

`simple_bar_chart.py`/`simple_line_chart.py`/`simple_area_chart.py`/`simple_pie_chart.py` hardcodean su propia paleta. Se define una paleta de datos de 6 colores derivada del primario (variaciones de tono/saturación, nunca colores arbitrarios nuevos), documentada en el mismo `tokens.py`, para que un gráfico nuevo nunca tenga que inventar color.

---

## 2. Tipografía

**Hallazgo crítico**: `font_family` por defecto de toda la aplicación es `"Comic Sans MS, Chalkboard SE, Comic Sans, Noteworthy, sans-serif"` (`tokens.py:33`) — cada `QLabel`, botón, campo, encabezado de tabla y menú de la app hereda esta fuente vía `QWidget { font-family: ... }` en el QSS global. No hay ninguna fuente "seria" antes de esa lista — es la primera opción, no un *fallback* real.

**Fuente oficial**: pila de fuentes nativas del sistema operativo (cero fuentes nuevas que empaquetar, cero riesgo de licencia, siempre disponible):

```
"Segoe UI", "SF Pro Text", "Helvetica Neue", "Ubuntu", "Noto Sans", sans-serif
```
Windows → Segoe UI (nativa desde Windows Vista). macOS → SF Pro Text/Helvetica Neue. Linux → Ubuntu/Noto Sans según distro. Es exactamente el patrón que usa VS Code, Slack de escritorio y la mayoría del software empresarial multiplataforma.

### 2.1 Escala tipográfica

Ya existían 4 tamaños con propósito real (`font_size_pt=13` cuerpo, `title_font_size_pt=16`, `amount_font_size_pt=28`, `hero_font_size_pt=72`, `status_font_size_pt=22`) — **se conservan tal cual**, tienen buena justificación documentada en el propio `tokens.py` y no hay evidencia de que sobren o falten. Se agrega un escalón que sí falta:

| Token | pt | Uso |
|---|---|---|
| `caption_font_size_pt` | 11 | Texto auxiliar/metadatos (ej. "Última actualización hace 2 min") — hoy no existe, algunas pantallas usan `role="secondary"` al mismo tamaño que el cuerpo cuando en realidad quieren un peso visual menor. |

### 2.2 Pesos

Qt QSS solo permite `normal`/`bold` (no hay pesos intermedios sin cargar variantes de fuente reales, que no vamos a empaquetar). Regla: **bold se reserva para jerarquía real** (títulos, valores destacados, encabezados de tabla) — nunca para dar énfasis dentro de una oración. Esto ya se respeta bastante bien hoy; se documenta para que se mantenga así.

---

## 3. Espaciado

**Hallazgo**: no existe ningún token/constante de espaciado en todo el proyecto. Muestreo de `setSpacing(...)` en `src/pos/modules/`: **7 valores distintos sin patrón** (2, 8, 10, 12, 14, 16, 18). Muestreo de `setContentsMargins(...)`: 5 patrones distintos. `build_scrollable_page()` (el contenedor que usa *toda* pantalla de nivel superior) no fija ningún margen/espaciado por defecto — cada pantalla decide el suyo desde cero.

### 3.1 Escala oficial (base 4px)

```python
SPACING_XS = 4    # separación mínima entre elementos muy relacionados (ícono + texto)
SPACING_SM = 8    # separación entre controles de una misma fila
SPACING_MD = 16   # separación entre grupos de controles, márgenes de tarjeta
SPACING_LG = 24   # margen de página, separación entre secciones
SPACING_XL = 32   # separación entre bloques mayores (ej. KPIs vs. contenido)
```

`build_scrollable_page()` pasa a fijar `SPACING_MD` de spacing y `SPACING_LG` de márgenes por defecto en su `content_layout` — así toda pantalla nueva hereda un espaciado correcto sin tener que pensarlo, y las que ya tienen un valor explícito lo conservan (no se les fuerza nada).

---

## 4. Radios de borde

**Hallazgo**: existe un solo token (`radius_px=8`), aplicado consistentemente vía QSS — esto en sí *no* es un problema (es la razón por la que los bordes redondeados ya se ven uniformes hoy). El vacío es que no hay variantes para casos que necesitan un radio distinto, así que cualquiera que lo necesite tendría que hardcodearlo.

| Token | px | Uso |
|---|---|---|
| `radius_sm_px` | 4 | Chips/badges (ver §8), etiquetas pequeñas |
| `radius_px` | 8 (sin cambio) | Botones, campos, tarjetas, diálogos — el radio "por defecto" |
| `radius_lg_px` | 12 | Superficies grandes elevadas (ver §6): diálogos importantes, panel de bienvenida |

---

## 5. Botones — estilo único, 6 estados

**Hallazgo**: el QSS actual de `QPushButton` solo define **reposo** y **deshabilitado** (`theme_manager.py:67-79`). No existe `:hover`, `:pressed` ni `:focus`. Un cajero no recibe ninguna confirmación visual de que un botón reaccionó a su clic hasta que el resultado de la acción aparece — en una pantalla táctil/mouse esto se percibe como que el software "no respondió".

Además, se encontraron overrides locales de altura que rompen la consistencia que el token `touch_control_min_height_px=52` ya buscaba dar: `setMinimumHeight()` con 72, 56, 48, 44, 40 y 36px repartidos en distintos módulos, todos ignorando el valor global.

### 5.1 Estados (los 6 pedidos)

| Estado | Regla |
|---|---|
| Reposo | `background: primary`, `color: on_primary` (sin cambio) |
| Hover | `background` del primario oscurecido ~8% (`primary_hover`, nuevo token) |
| Presionado | `background` del primario oscurecido ~16% (`primary_pressed`, nuevo token) — más oscuro que hover, confirma que el clic "aterrizó" |
| Deshabilitado | sin cambio (`border`/`text_secondary`) |
| Focus (navegación por teclado) | contorno de 2px en `primary` alrededor del botón — hoy el foco es invisible |
| Activo/seleccionado (ej. un botón de filtro tipo toggle) | `background: primary_pressed` + borde — mismo tratamiento visual que "presionado" para que un botón que queda "activado" se lea igual que uno que se está presionando ahora mismo |

### 5.2 Variantes (no son botones nuevos, son roles sobre el mismo estilo)

Ya existe la convención `QLabel[role=...]` para texto; se extiende la misma idea a botones vía `QPushButton[role="secondary"|"danger"|"ghost"]`, todas obedeciendo los mismos 6 estados de arriba con su propio color base:

- **Primario** (por defecto, sin `role`): la acción principal de la pantalla ("Guardar", "Completar venta").
- **`role="secondary"`**: fondo `surface` + borde, texto `text_primary` — para "Cancelar" y acciones no destructivas secundarias.
- **`role="danger"`**: fondo `danger` — para "Eliminar". Hoy estos botones usan el mismo azul primario que "Guardar", lo cual no distingue una acción destructiva de una segura (encontrado en múltiples diálogos de confirmación de borrado).
- **`role="ghost"`**: sin fondo, solo texto — para acciones terciarias dentro de una fila/tarjeta.

### 5.3 Tamaños (variantes cerradas, no ad-hoc)

`touch_control_min_height_px=52` sigue siendo el tamaño estándar de cualquier botón/campo. Se agregan exactamente dos variantes con nombre, para que los `setMinimumHeight()` sueltos encontrados en la auditoría tengan un destino claro en vez de seguir siendo números arbitrarios:

- `role="compact"` → 36px (fila de tabla, acción inline)
- `size="hero"` (nuevo, reutiliza el patrón `size=` ya usado en `QLabel[size="status"]`) → 64px (una única acción de pantalla completa, ej. "Completar venta" en el carrito)

---

## 6. Campos de texto — 5 estados

**Hallazgo**: mismo problema que los botones — `QLineEdit`/`QComboBox`/etc. solo tienen estilo de reposo (`theme_manager.py:81-88`). Sin foco visible, un usuario no sabe en qué campo está escribiendo sin mirar el cursor. Sin estado de error, los formularios muestran errores solo vía `QMessageBox` bloqueante (ver §7), nunca resaltando el campo específico.

| Estado | Regla |
|---|---|
| Normal | sin cambio (`border: 1px solid border`) |
| Hover | `border-color: text_secondary` — señal sutil de que el campo es interactivo antes de hacer foco |
| Focus | `border: 2px solid primary` — mismo lenguaje que el foco de botones |
| Error | `border: 2px solid danger` vía `QLineEdit[state="error"]` (propiedad nueva, mismo patrón que `role=`) — para usarse junto a un mensaje de error puntual, no reemplazarlo |
| Deshabilitado | `background: background`, `color: text_secondary`, sin cambio real de intención pero hoy no está definido explícitamente (hereda por accidente) — se declara a propósito |

---

## 7. Tablas

**Hallazgo**: el estilo de tabla ya es consistente entre módulos (todas comparten el mismo QSS global — `QListWidget, QTableWidget, QTreeWidget` en `theme_manager.py:246`), lo cual es una fortaleza real a conservar. Los ajustes son puntuales:

- **Selección**: hoy `background: primary` a toda la fila — funciona, se conserva.
- **Hover de fila**: hoy usa `background: border` (el mismo gris que un borde) — se cambia a un tinte del primario muy sutil (`primary` al 8% sobre `surface`, token `hover_overlay` nuevo) para que hover y selección se lean como dos estados relacionados pero distintos (hoy hover se parece más a "deshabilitado" que a "estoy por seleccionar esto").
- **Encabezado**: pasa de `header_accent` mostaza a la versión neutra (§1.2) — deja de competir con las filas en estado "warning" reales.
- **Scroll**: ya está resuelto correctamente (`build_scrollable_page` + `fit_table_to_contents`, documentado con su propia justificación) — sin cambios.

---

## 8. Tarjetas y elevación

**Hallazgo**: toda "tarjeta" de la app (`KpiCard`, `QFrame#surface` en general) es un rectángulo con borde de 1px y esquinas redondeadas — cero profundidad. No existe ningún uso de `QGraphicsDropShadowEffect` en todo el proyecto (verificado por búsqueda exhaustiva). Qt QSS no soporta `box-shadow`, así que esto requiere un helper de código, no solo QSS.

### 8.1 Escala de elevación

Se crea `shared_ui/theme/elevation.py` con una función `apply_shadow(widget, level)`:

| Nivel | Uso | Sombra |
|---|---|---|
| `"none"` | superficies densas (tablas, formularios largos) — se dejan planas a propósito, una sombra ahí sería ruido | — |
| `"sm"` | `KpiCard`, tarjetas dentro de una grilla | blur 12px, offset (0, 2px), 12% opacidad negro |
| `"lg"` | diálogos modales, menús desplegables | blur 24px, offset (0, 8px), 18% opacidad negro |

Esto es exactamente el criterio "sombras únicamente donde aporten valor" — no se aplica a todo, solo a superficies que de verdad "flotan" sobre el fondo (una tarjeta de KPI, un modal) y no a contenido que vive plano en el flujo de la pantalla (una tabla, un formulario).

---

## 9. Diálogos

**Hallazgo**: no hay una plantilla única — algunos diálogos usan `QDialogButtonBox` (orden de botones nativo del SO), otros arman una fila de `QPushButton` a mano con orden inconsistente (a veces "Cancelar" a la izquierda, a veces a la derecha).

**Regla oficial**: todo diálogo nuevo/tocado usa `QDialogButtonBox` con orden `Cancelar` (`role="secondary"`) a la izquierda del botón de acción principal (primario o `role="danger"` si es destructivo) a la derecha — es el orden nativo de Qt en Windows/Linux (en macOS Qt ya invierte el orden automáticamente para respetar la convención del SO, no hay que hacer nada extra). Título del diálogo siempre `role="title"` (ya existe). Elevación `"lg"` (§8) en todos.

---

## 10. Iconografía

**Hallazgo — el de mayor visibilidad después de la tipografía**: la navegación principal del Dashboard (los 13 accesos rápidos, lo primero que ve cualquier usuario después de iniciar sesión) usa emoji como ícono (`main.py::_PANEL_ICONS` — 🛠️📈📋🧾📦👥💰🛒📊🔑💾🔄). La barra superior también (🔔 campana de despacho, 👤 usuario). Fuera de eso, `QIcon` real solo se usa en 3 archivos, y únicamente para miniaturas de fotos de usuario/producto — no hay ningún ícono de acción (editar, eliminar, agregar, etc.) en ningún botón de toda la app; son 100% texto.

Esto no es "íconos mezclados" en el sentido de dos sistemas compitiendo — es que **no existe un sistema de íconos real**: el emoji cubre navegación/identidad, y el resto de la app no usa íconos en absoluto. El emoji además renderiza de forma distinta e impredecible entre Windows/macOS/Linux (distintas fuentes de emoji del sistema, distinto color/estilo), lo que contradice directamente "el usuario debe sentir desde los primeros segundos... un producto premium".

**Decisión**: adoptar un set de íconos vectoriales real (SVG, licencia MIT, sin costo ni dependencia nueva — Qt ya soporta SVG vía `QtSvg`, que el proyecto ya usa transitivamente por PySide6). Un ícono por concepto, mismo grosor de trazo, mismo tamaño base (20px), coloreado vía QSS (`currentColor`-equivalente en Qt: se recolorea el SVG con el token que corresponda, así el ícono cambia de color solo con el tema, igual que el texto).

**Alcance de esta fase**: reemplazar únicamente lo que es *navegación/identidad* (los 13 íconos del Dashboard + campana + usuario del top bar) — es donde vive el 90% del impacto visual y el 100% del emoji actual. Agregar íconos a botones de acción individuales (Editar/Eliminar/etc.) queda documentado como extensión futura opcional, fuera del alcance de esta fase para no inflarla.

---

## 11. Movimiento y microinteracciones

**Hallazgo**: cero animaciones en todo el proyecto (`QPropertyAnimation`, `QVariantAnimation`, efectos de opacidad: 0 resultados). Esto no es necesariamente un problema por sí solo (un POS debe sentirse *rápido*, no "bonito"), pero hay un caso concreto donde la ausencia de retroalimentación no-bloqueante sí cuesta velocidad real: **cada confirmación de "guardado exitoso" en toda la app es un `QMessageBox.information` modal** — una ventana que el cajero debe cerrar con un clic extra, para una acción que ya salió bien. Se cuenta por decenas de sitios (todo `operation_succeeded.connect(self._show_info)` de este proyecto usa este patrón).

**Regla**: la animación se usa solo donde ahorra un paso o confirma un estado que de otro modo pasaría desapercibido — nunca para decorar.

| Interacción | Hoy | Propuesto | Por qué |
|---|---|---|---|
| Confirmación de guardado exitoso | `QMessageBox.information` (bloqueante, requiere clic) | Notificación tipo "toast": aparece abajo-derecha, fade-in 150ms, se auto-oculta a los 2.5s, no bloquea la ventana | Elimina un clic redundante en la acción más frecuente de toda la app (guardar). Duración corta a propósito — no es decorativo, es la mínima confirmación necesaria para que el ojo la registre. |
| Clic de botón | instantáneo (Qt nativo) | sin cambio | Un botón de POS debe responder en el mismo frame — cualquier demora animada ahí sería directamente el tipo de degradación de rendimiento que se prohíbe explícitamente. |
| Cambio de pestaña | instantáneo (Qt nativo) | sin cambio | Mismo motivo — la velocidad de cambiar de pestaña ya es correcta. |
| Operación de dispositivo en curso (conectar báscula, imprimir, etc.) | ya existe: texto de estado en vivo vía `DeviceOperationWorker` ("Conectando…" → resultado) | sin cambio funcional; solo se valida que el patrón visual (texto + color de estado) sea consistente entre los módulos que ya lo usan | El patrón en sí ya es bueno (asíncrono, no bloqueante) — es una cuestión de aplicar el mismo QSS/tokens en todos los sitios donde aparece, no de agregar movimiento nuevo. |
| Error de validación en un campo | `QMessageBox.warning` bloqueante | sin cambio en esta fase | Un error sí debe detener al usuario hasta que lo lea — a diferencia de un éxito, no es candidato a notificación pasiva. Fuera de alcance de la Fase Omega (sería un cambio de flujo, no visual). |

---

## 12. Consistencia — componentes duplicados encontrados

| Componente repetido | Implementaciones distintas encontradas | Unificación |
|---|---|---|
| Fila de color según estado (bien/atención/mal) | `inventory_table_model.py`, `customer_history_dialog.py`, `profits_table_model.py` — 3 paletas ligeramente distintas, ninguna reactiva al tema | Tokens `success_tint`/`warning_tint`/`danger_tint` (§1.3) |
| Paleta de un formulario | `product_form_dialog.py` define `_BACKGROUND_COLOR`/`_TEXT_COLOR`/`_FIELD_BACKGROUND_COLOR` propios | Elimina el `setStyleSheet()` local, hereda del QSS global igual que el resto de formularios |
| Ícono de "sin imagen" | emoji 🖼️ en `table_utils.py` (2 sitios) | Se conserva como excepción documentada — es un placeholder de contenido de usuario (foto de producto), no navegación/identidad; no es donde vive el problema de percepción de marca |
| Botón de acción destructiva | mismo azul primario que "Guardar" en varios diálogos de confirmación de borrado | `role="danger"` (§5.2) |

---

## 14. Dashboard — tarjeta KPI con ícono/tendencia y tarjeta de acceso rápido

**Hallazgo**: el Dashboard es la primera pantalla que ve cualquier usuario tras iniciar sesión, y antes de este cambio era la más "plana" de toda la app — `KpiCard` era solo texto (sin ícono, sin borde de categoría, sin indicio de tendencia) y los accesos rápidos eran botones pequeños de ícono+texto agrupados en un `QGroupBox` nativo (sin descripción, sin jerarquía visual entre categorías). El usuario aportó una referencia visual externa (un mockup con estética "premium": ícono + acento de color por categoría + mini-gráfico de tendencia en las tarjetas, accesos rápidos como tarjetas grandes con descripción) — se adoptó la *estructura* (proporción, sombra, jerarquía, tamaño de tarjeta) sin adoptar su paleta de color (ver §0/§1: la paleta de `tokens.py` no cambió).

- **`shared_ui/widgets/icon_badge.py`** (nuevo): círculo de fondo tenue (`*_tint` o `header_accent`) + ícono centrado — compartido por `KpiCard` y la tarjeta de acceso rápido (mismo criterio de unificación que success/warning/danger_tint, §12).
- **`shared_ui/widgets/sparkline.py`** (nuevo): mini-gráfico de línea sin ejes para el pie de una `KpiCard` — deliberadamente *no* reutiliza `SimpleLineChart` (pensado para Reportes, con ejes/etiquetas y `minimumHeight=240`, no cabe en 28px).
- **`KpiCard`**: gana `icon`/`accent` (`"primary"|"success"|"secondary"`, sin colores nuevos) /`trend`/`delta_pct`, todos opcionales — las ~16 tarjetas de Ganancias/Ventas/Backups que no pasan estos parámetros se ven exactamente igual que antes. El borde de acento (`QFrame#surface[accent=...]`) es el color base mezclado al 40% sobre `surface` (`_blend()`, mismo mecanismo que `hover_overlay`), sutil por diseño.
- **`QuickAccessPanel`**: pasa de `QGroupBox` + botones pequeños a un encabezado de grupo (etiqueta + regla horizontal) y tarjetas grandes clicables (`_NavItemCard`, mismo patrón `QFrame`+`mousePressEvent` ya usado en `kitchen_view.py::_OrderCard`) con ícono, título, descripción (`main.py::_PANEL_DESCRIPTIONS`) y flecha (`chevron-right`). El grid usa `columnas = min(items_del_grupo, 4)` en vez de un fijo global — un grupo de 1 ítem ocupa el ancho completo en vez de dejar 3 columnas vacías.
- **`TopBar`**: ícono de marca junto al nombre del sistema; la campana y el botón de usuario ganan el mismo chip (`QFrame#surface`) que el resto de "superficies" de la app, antes eran los únicos elementos sin contorno propio.
- **Dato nuevo, explícitamente acotado**: el % de variación ("▲18.2% vs mes anterior") en Ventas/Ganancias del mes es de solo lectura, calculado con métodos ya existentes de `ReportsService` (`sales_report`/`product_profit`/`sales_and_profit_chart`) sobre el mes anterior — cero lógica de negocio nueva, mismo patrón que el resto de `_compute_dashboard_metrics`. Con base `$0` se muestra `None` (sin dato) en vez de inventar un porcentaje.

---

## 15. Qué NO cambia en esta fase (explícito)

Flujo de venta, facturación, caja, inventario, permisos, reglas de negocio, estructura de datos, nombres de módulos, comportamiento de ningún botón (qué hace al hacer clic), orden de pantallas, contenido de ningún mensaje, paleta de colores. Cero funcionalidad nueva salvo el % de variación de §14 (solo lectura, sin lógica de negocio nueva), cero funcionalidad eliminada.
