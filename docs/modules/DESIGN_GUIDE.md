# Guía de diseño por módulo

Documenta decisiones visuales ya implementadas y aprobadas, módulo por
módulo — no es un backlog de ideas futuras. Para el sistema de diseño
global (colores, tipografía, espaciado, elevación) ver `DESIGN_SYSTEM.md`
en la raíz del repositorio; este archivo documenta cómo se aplica en
pantallas específicas con requisitos propios.

## Login (`pos/modules/auth/presentation/login_view.py`)

### Identidad de marca

La pantalla usa las imágenes oficiales de `docs/branding/` directamente —
ninguna se reemplaza por texto:

| Elemento | Archivo | Notas |
|---|---|---|
| Logo | `logo.png` | Escalado a 260px de alto — el elemento principal de la pantalla, el más grande con diferencia. |
| Nombre de la empresa | `astrim.png` | Escalado a 280px de ancho. |
| Eslogan | `frase1.png` | Escalado a 320px de ancho. |
| Pie de página (versión) | `version.png` | Escalado a 130px de ancho — pie de página discreto, no compite con el logo. |

Todas se cargan vía `shared_ui/branding.py::load_brand_pixmap` (resuelve
`docs/branding/` tanto en desarrollo como en la app empaquetada,
`installer/pos.spec`) y se escalan preservando su proporción original
(`Qt.AspectRatioMode.KeepAspectRatio` — nunca se deforman). Si un archivo
de marca faltara, la etiqueta correspondiente se oculta en vez de mostrar
un ícono de imagen rota, para que la pantalla siga siendo usable.

**Recorte al contenido visible** (`login_view.py::_trim_transparent_margin`):
los PNG de marca traen una sombra/brillo suave que se desvanece hasta
alfa≈0 en casi todo el lienzo (no un margen transparente simple) — un
recorte "cualquier píxel no-cero" apenas quita nada, porque esa cola de
sombra casi cubre el lienzo completo. Antes de escalar cada imagen, se
recorta al recuadro cuyo alfa supera un umbral (40/255), calculado sobre
una copia reducida (128px, rápido, sin diferencia visible) y aplicado
sobre la imagen a resolución completa — nunca se modifica el archivo
original en `docs/branding/`. Sin este paso, logo/nombre/eslogan se veían
separados por espacios enormes sin importar el espaciado real del layout,
porque cada imagen ya traía su propio margen vacío incluido.

El encabezado de texto anterior ("Sistema POS") se eliminó por completo —
la identidad visual ahora la llevan exclusivamente estas imágenes.

### Orden vertical (fijo)

1. Logo
2. Nombre (ASTRIM)
3. Eslogan
4. Formulario (Usuario, Contraseña, botón "Iniciar sesión")
5. Pie de página (versión)

### Formulario

Misma lógica y componentes de siempre (`LoginViewModel`, validaciones,
señales `authenticated`/`login_failed`/`login_succeeded` sin cambios) —
solo se modernizó la apariencia: tarjeta `QFrame#surface` con esquinas
redondeadas, sombra con brillo de color (`apply_shadow(card, "lg",
glow_color=primary)`, mismo mecanismo que el resto del sistema — ver
DESIGN_SYSTEM.md §14) y espaciado generoso (`SPACING_LG`/`SPACING_MD`).

### Distribución y responsividad

Logo, nombre y eslogan se separan por apenas 10px (`_BRAND_STACK_SPACING_PX`,
dentro del rango 8-12px pedido) para que se lean como un único bloque de
marca, no como elementos sueltos. El bloque de marca y la tarjeta del
formulario quedan centrados en el espacio disponible por encima del pie de
página (`addStretch()` arriba del bloque); antes del pie de página hay un
espacio fijo garantizado (`SPACING_XL`, no solo un `addStretch`) — con un
`addStretch` únicamente, cuando el contenido ya casi llena la ventana el
espacio "extra" a repartir puede ser ~0px, y la versión terminaba pegada al
borde inferior de la tarjeta.

Toda la pantalla vive dentro de `shared_ui/widgets/scrollable_page.py::
build_scrollable_page` — el mismo contenedor de scroll de página completa
que usa el resto de la app (barra vertical siempre visible, del mismo
estilo delgado y moderno del resto del sistema). En la resolución de
ventana por defecto (1280×800) el contenido cabe casi completo; puede
requerir un desplazamiento pequeño (~40px) para revelar el pie de página
por completo, dado el tamaño del logo y el espacio garantizado antes de la
versión — es el comportamiento de scroll pedido explícitamente, no una
pantalla rota: ningún elemento queda oculto, todo es alcanzable con la
barra de desplazamiento. En ventanas más chicas el scroll crece en
consecuencia, sin ocultar nada.

Ninguna imagen se deforma (tamaños fijos, escalados una sola vez
preservando proporción — el layout centra y hace scroll, no reescala las
imágenes en cada resize).
