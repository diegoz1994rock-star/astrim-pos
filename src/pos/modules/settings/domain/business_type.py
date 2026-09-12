"""Tipo de negocio configurado para toda la empresa (PROJECT_SPEC.md,
"CONFIGURACIÓN"): determina qué módulos verticales (Restaurante, Cocina,
y los que se agreguen a futuro) aparecen en el menú principal, sin
importar el cargo del usuario — ver `main.py::NavPanel.business_types` y
`_panel_visible`.

Se guarda como un único valor de texto en `business_settings` bajo
`BUSINESS_TYPE_SETTING_KEY`, igual que `business_name`: agregar un tipo de
negocio nuevo a futuro es agregar un miembro a este enum, sin migración
de esquema.

El orden de declaración es alfabético (por el nombre visible en
`BUSINESS_TYPE_LABELS`, sin tener en cuenta tildes) con "Otro" al final a
propósito — el combo de `first_run_setup_view.py` (el único que lista
`BusinessType`; se fija una única vez al configurar la aplicación por
primera vez) simplemente itera el enum en este orden, sin tener que
ordenar nada él mismo."""

from __future__ import annotations

import enum

from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.modules.settings.infrastructure.models import SettingValueType

BUSINESS_TYPE_SETTING_KEY = "business_type"


class BusinessType(enum.Enum):
    AGENCIA_DE_VIAJES = "agencia_de_viajes"
    ALMACEN_DE_ELECTRODOMESTICOS = "almacen_de_electrodomesticos"
    ASADERO_DE_CARNES = "asadero_de_carnes"
    ASADERO_DE_POLLO = "asadero_de_pollo"
    BAR = "bar"
    BARBERIA = "barberia"
    BILLARES = "billares"
    BOUTIQUE_DE_ROPA = "boutique_de_ropa"
    CAFETERIA = "cafeteria"
    CARNICERIA = "carniceria"
    CENTRO_DE_COPIADO_E_IMPRESION = "centro_de_copiado_e_impresion"
    CIBER_O_INTERNET_CAFE = "ciber_o_internet_cafe"
    CIGARRERIA = "cigarreria"
    CLINICA_ODONTOLOGICA = "clinica_odontologica"
    COMIDAS_RAPIDAS = "comidas_rapidas"
    COMIDAS_TIPICAS = "comidas_tipicas"
    CONSULTORIO_MEDICO = "consultorio_medico"
    CONSULTORIO_VETERINARIO = "consultorio_veterinario"
    DISCOTECA = "discoteca"
    DISTRIBUIDORA = "distribuidora"
    FARMACIA = "farmacia"
    FERRETERIA = "ferreteria"
    FLORISTERIA = "floristeria"
    FRUVER = "fruver"
    GIMNASIO = "gimnasio"
    HELADERIA = "heladeria"
    HOSTAL = "hostal"
    HOTEL = "hotel"
    JOYERIA = "joyeria"
    LAVADERO_DE_VEHICULOS = "lavadero_de_vehiculos"
    LAVANDERIA = "lavanderia"
    LIBRERIA = "libreria"
    LICORERA = "licorera"
    MAYORISTA = "mayorista"
    MINIMERCADO = "minimercado"
    MUEBLERIA = "muebleria"
    OPTICA = "optica"
    PANADERIA = "panaderia"
    PAPELERIA = "papeleria"
    PASTELERIA = "pasteleria"
    PELUQUERIA = "peluqueria"
    PESCADERIA = "pescaderia"
    PIZZERIA = "pizzeria"
    REPOSTERIA = "reposteria"
    REPUESTOS_PARA_MOTOS = "repuestos_para_motos"
    RESTAURANTE = "restaurante"
    SALON_DE_BELLEZA = "salon_de_belleza"
    SPA = "spa"
    SUPERMERCADO = "supermercado"
    SUSHI_BAR = "sushi_bar"
    TALLER_AUTOMOTRIZ = "taller_automotriz"
    TALLER_DE_MOTOS = "taller_de_motos"
    TIENDA_DE_BARRIO = "tienda_de_barrio"
    TIENDA_DE_CELULARES = "tienda_de_celulares"
    TIENDA_DE_MASCOTAS = "tienda_de_mascotas"
    TIENDA_DE_PINTURAS = "tienda_de_pinturas"
    TIENDA_DE_REPUESTOS = "tienda_de_repuestos"
    TIENDA_DE_TECNOLOGIA = "tienda_de_tecnologia"
    VETERINARIA = "veterinaria"
    ZAPATERIA = "zapateria"
    OTRO = "otro"


DEFAULT_BUSINESS_TYPE = BusinessType.OTRO

BUSINESS_TYPE_LABELS: dict[BusinessType, str] = {
    BusinessType.AGENCIA_DE_VIAJES: "Agencia de viajes",
    BusinessType.ALMACEN_DE_ELECTRODOMESTICOS: "Almacén de electrodomésticos",
    BusinessType.ASADERO_DE_CARNES: "Asadero de carnes",
    BusinessType.ASADERO_DE_POLLO: "Asadero de pollo",
    BusinessType.BAR: "Bar",
    BusinessType.BARBERIA: "Barbería",
    BusinessType.BILLARES: "Billares",
    BusinessType.BOUTIQUE_DE_ROPA: "Boutique de ropa",
    BusinessType.CAFETERIA: "Cafetería",
    BusinessType.CARNICERIA: "Carnicería",
    BusinessType.CENTRO_DE_COPIADO_E_IMPRESION: "Centro de copiado e impresión",
    BusinessType.CIBER_O_INTERNET_CAFE: "Ciber o Internet Café",
    BusinessType.CIGARRERIA: "Cigarrería",
    BusinessType.CLINICA_ODONTOLOGICA: "Clínica odontológica",
    BusinessType.COMIDAS_RAPIDAS: "Comidas rápidas",
    BusinessType.COMIDAS_TIPICAS: "Comidas típicas",
    BusinessType.CONSULTORIO_MEDICO: "Consultorio médico",
    BusinessType.CONSULTORIO_VETERINARIO: "Consultorio veterinario",
    BusinessType.DISCOTECA: "Discoteca",
    BusinessType.DISTRIBUIDORA: "Distribuidora",
    BusinessType.FARMACIA: "Farmacia",
    BusinessType.FERRETERIA: "Ferretería",
    BusinessType.FLORISTERIA: "Floristería",
    BusinessType.FRUVER: "Fruver (frutas y verduras)",
    BusinessType.GIMNASIO: "Gimnasio",
    BusinessType.HELADERIA: "Heladería",
    BusinessType.HOSTAL: "Hostal",
    BusinessType.HOTEL: "Hotel",
    BusinessType.JOYERIA: "Joyería",
    BusinessType.LAVADERO_DE_VEHICULOS: "Lavadero de vehículos",
    BusinessType.LAVANDERIA: "Lavandería",
    BusinessType.LIBRERIA: "Librería",
    BusinessType.LICORERA: "Licorera",
    BusinessType.MAYORISTA: "Mayorista",
    BusinessType.MINIMERCADO: "Minimercado",
    BusinessType.MUEBLERIA: "Mueblería",
    BusinessType.OPTICA: "Óptica",
    BusinessType.PANADERIA: "Panadería",
    BusinessType.PAPELERIA: "Papelería",
    BusinessType.PASTELERIA: "Pastelería",
    BusinessType.PELUQUERIA: "Peluquería",
    BusinessType.PESCADERIA: "Pescadería",
    BusinessType.PIZZERIA: "Pizzería",
    BusinessType.REPOSTERIA: "Repostería",
    BusinessType.REPUESTOS_PARA_MOTOS: "Repuestos para motos",
    BusinessType.RESTAURANTE: "Restaurante",
    BusinessType.SALON_DE_BELLEZA: "Salón de belleza",
    BusinessType.SPA: "Spa",
    BusinessType.SUPERMERCADO: "Supermercado",
    BusinessType.SUSHI_BAR: "Sushi Bar",
    BusinessType.TALLER_AUTOMOTRIZ: "Taller automotriz",
    BusinessType.TALLER_DE_MOTOS: "Taller de motos",
    BusinessType.TIENDA_DE_BARRIO: "Tienda de barrio",
    BusinessType.TIENDA_DE_CELULARES: "Tienda de celulares",
    BusinessType.TIENDA_DE_MASCOTAS: "Tienda de mascotas",
    BusinessType.TIENDA_DE_PINTURAS: "Tienda de pinturas",
    BusinessType.TIENDA_DE_REPUESTOS: "Tienda de repuestos",
    BusinessType.TIENDA_DE_TECNOLOGIA: "Tienda de tecnología",
    BusinessType.VETERINARIA: "Veterinaria",
    BusinessType.ZAPATERIA: "Zapatería",
    BusinessType.OTRO: "Otro",
}


def get_business_type(settings_service: BusinessSettingsService) -> BusinessType:
    """Lee el tipo de negocio configurado; `OTRO` si nunca se configuró o
    si el valor guardado ya no corresponde a un miembro del enum (ej.
    tras quitar un tipo en una versión futura — incluye el caso real de
    haber reemplazado la lista anterior por esta)."""
    raw = settings_service.get_str(BUSINESS_TYPE_SETTING_KEY)
    if raw is None:
        return DEFAULT_BUSINESS_TYPE
    try:
        return BusinessType(raw)
    except ValueError:
        return DEFAULT_BUSINESS_TYPE


def set_business_type(
    settings_service: BusinessSettingsService, business_type: BusinessType
) -> None:
    settings_service.set_value(
        BUSINESS_TYPE_SETTING_KEY, business_type.value, SettingValueType.STRING
    )
