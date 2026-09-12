"""Registro de adaptadores de impresora — a diferencia de los módulos
hermanos (que registran por `kind` de marca), acá se registra por
`PrintMethod`: las dos vías universales (driver del SO / ESC/POS crudo)
son la extensión real pedida, no una marca puntual. Un adaptador
específico de marca a futuro seguiría perteneciendo a una de estas dos
familias (ej. optimizaciones Epson-específicas dentro de `RAW_ESCPOS`) sin
necesitar una tercera vía."""

from __future__ import annotations

from pos.modules.printers.application.providers.base import PrinterProvider
from pos.modules.printers.application.providers.escpos_raw_provider import (
    EscPosRawPrinterProvider,
)
from pos.modules.printers.application.providers.system_driver_provider import (
    SystemDriverPrinterProvider,
)
from pos.modules.printers.domain.enums import PrinterType, PrintMethod

_PROVIDER_REGISTRY: dict[PrintMethod, type[PrinterProvider]] = {
    PrintMethod.SYSTEM_DRIVER: SystemDriverPrinterProvider,
    PrintMethod.RAW_ESCPOS: EscPosRawPrinterProvider,
}

PRINT_METHOD_LABELS: dict[PrintMethod, str] = {
    PrintMethod.SYSTEM_DRIVER: "Driver del sistema operativo (cualquier impresora instalada)",
    PrintMethod.RAW_ESCPOS: "ESC/POS directo por puerto (térmicas sin driver)",
}

PRINTER_TYPE_LABELS: dict[PrinterType, str] = {
    PrinterType.THERMAL_58: "Térmica 58 mm",
    PrinterType.THERMAL_80: "Térmica 80 mm",
    PrinterType.RECEIPT: "Impresora de recibos",
    PrinterType.POS: "Impresora POS",
    PrinterType.LASER: "Láser",
    PrinterType.INKJET: "Inyección de tinta",
    PrinterType.MATRIX: "Matricial",
    PrinterType.A4: "A4 / carta",
    PrinterType.LABEL: "Etiquetas",
    PrinterType.OTHER: "Otro",
}


def get_printer_adapter(print_method: PrintMethod) -> PrinterProvider:
    provider_class = _PROVIDER_REGISTRY[print_method]
    return provider_class()
