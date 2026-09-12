"""Escala oficial de espaciado (ver DESIGN_SYSTEM.md §3) — base de 4px.

No vive en `ThemeTokens` a propósito: a diferencia del color/tipografía/
radio, el espaciado no cambia entre temas claro/oscuro, y se usa
directamente en código de layout (`layout.setSpacing(SPACING_MD)`), nunca
interpolado dentro de una plantilla QSS. Antes de esta escala, cada
pantalla elegía sus propios valores de `setSpacing`/`setContentsMargins`
sin ningún patrón (ver auditoría en DESIGN_SYSTEM.md §3)."""

from __future__ import annotations

SPACING_XS = 4
"""Separación mínima entre elementos muy relacionados (ícono + texto)."""
SPACING_SM = 8
"""Separación entre controles de una misma fila."""
SPACING_MD = 16
"""Separación entre grupos de controles, márgenes internos de tarjeta."""
SPACING_LG = 24
"""Margen de página, separación entre secciones."""
SPACING_XL = 32
"""Separación entre bloques mayores (ej. fila de KPIs vs. contenido)."""
