import unicodedata
from typing import Dict, Any
from models import (
    ViviendaModel,
    ZonaClimatica,
    TipoVivienda,
    TipoVentana,
    SistemaCalefaccion
)

# Mapeo de capitales de provincia a su Zona Climática CTE oficial (Apéndice B)
CAPITALES_A_ZONA = {
    # Zona A (Cálida / Muy suave)
    "almeria": ZonaClimatica.A, "cadiz": ZonaClimatica.A, "malaga": ZonaClimatica.A,
    "palmas": ZonaClimatica.A, "santa cruz de tenerife": ZonaClimatica.A,
    # Zona B (Inviernos suaves)
    "sevilla": ZonaClimatica.B, "cordoba": ZonaClimatica.B, "huelva": ZonaClimatica.B,
    "valencia": ZonaClimatica.B, "alicante": ZonaClimatica.B, "castellon": ZonaClimatica.B,
    "murcia": ZonaClimatica.B, "palma": ZonaClimatica.B, "baleares": ZonaClimatica.B,
    # Zona C (Inviernos templados / costeros atlánticos)
    "barcelona": ZonaClimatica.C, "tarragona": ZonaClimatica.C, "girona": ZonaClimatica.C,
    "a coruna": ZonaClimatica.C, "coruna": ZonaClimatica.C, "pontevedra": ZonaClimatica.C,
    "vigo": ZonaClimatica.C, "lugo": ZonaClimatica.C, "ourense": ZonaClimatica.C,
    "bilbao": ZonaClimatica.C, "vizcaya": ZonaClimatica.C, "san sebastian": ZonaClimatica.C,
    "guipuzcoa": ZonaClimatica.C, "santander": ZonaClimatica.C, "cantabria": ZonaClimatica.C,
    "oviedo": ZonaClimatica.C, "gijon": ZonaClimatica.C, "asturias": ZonaClimatica.C,
    # Zona D (Inviernos fríos de meseta y valles interiores)
    "madrid": ZonaClimatica.D, "zaragoza": ZonaClimatica.D, "toledo": ZonaClimatica.D,
    "ciudad real": ZonaClimatica.D, "albacete": ZonaClimatica.D, "guadalajara": ZonaClimatica.D,
    "valladolid": ZonaClimatica.D, "salamanca": ZonaClimatica.D, "zamora": ZonaClimatica.D,
    "palencia": ZonaClimatica.D, "cuenca": ZonaClimatica.D, "caceres": ZonaClimatica.D,
    "badajoz": ZonaClimatica.D, "jaen": ZonaClimatica.D, "granada": ZonaClimatica.D,
    "logrono": ZonaClimatica.D, "la rioja": ZonaClimatica.D, "pamplona": ZonaClimatica.D,
    "navarra": ZonaClimatica.D, "vitoria": ZonaClimatica.D, "alava": ZonaClimatica.D,
    # Zona E (Inviernos extremos / alta meseta norte)
    "burgos": ZonaClimatica.E, "soria": ZonaClimatica.E, "avila": ZonaClimatica.E,
    "segovia": ZonaClimatica.E, "leon": ZonaClimatica.E
}

def normalizar_texto(texto: str) -> str:
    """Elimina tildes, caracteres especiales y pasa el texto a minusculas."""
    if not texto:
        return ""
    texto = texto.strip().lower()
    descompuesta = unicodedata.normalize('NFD', texto)
    return "".join(c for c in descompuesta if unicodedata.category(c) != 'Mn')

def inferir_zona_climatica(ubicacion: str) -> ZonaClimatica:
    """Deduce la zona climatica CTE buscando coincidencias con municipios o provincias."""
    ub_norm = normalizar_texto(ubicacion)
    for municipio, zona in CAPITALES_A_ZONA.items():
        if municipio in ub_norm:
            return zona
    # Por defecto ante municipios no reconocidos se toma Zona D (media peninsular)
    return ZonaClimatica.D

def inferir_por_antiguedad(año_construccion: int) -> Dict[str, Any]:
    """
    Deduce el aislamiento y las ventanas segun el marco normativo historico:
    - Pre-1980 (Sin normativa termica): Sin aislamiento y vidrio simple.
    - 1980-2006 (NBE-CT-79): Aislamiento insuficiente/nulo en fachada y vidrio doble basico.
    - Post-2006 (CTE 2006): Fachada con aislamiento continuo y ventanas con RPT/PVC.
    """
    if año_construccion < 1980:
        return {
            "aislamiento_fachada": False,
            "tipo_ventanas": TipoVentana.SIMPLE_METAL
        }
    elif año_construccion <= 2006:
        return {
            "aislamiento_fachada": False,
            "tipo_ventanas": TipoVentana.DOBLE_ALUMINIO
        }
    else:
        return {
            "aislamiento_fachada": True,
            "tipo_ventanas": TipoVentana.DOBLE_PVC
        }

def estimar_factura_anual(superficie_m2: float) -> float:
    """Estimacion base de gasto residencial: ~12 EUR/m2 al ano para calefaccion y ACS."""
    return round(superficie_m2 * 12.0, 2)

def sanear_y_crear_vivienda(datos_crudos: Dict[str, Any]) -> ViviendaModel:
    """
    Recibe un diccionario con datos brutos del usuario o del LLM,
    aplica las reglas de inferencia para completar huecos y genera
    la instancia validada de ViviendaModel con los 8 atributos obligatorios.
    """
    datos = datos_crudos.copy()

    # 1. Resolver Zona Climática (a partir de 'zona_climatica' o de 'ubicacion')
    if "zona_climatica" not in datos or not datos["zona_climatica"]:
        ubicacion = datos.get("ubicacion", "")
        datos["zona_climatica"] = inferir_zona_climatica(str(ubicacion))
    datos.pop("ubicacion", None)

    # 2. Inferir elementos constructivos si no los aporta el usuario
    if "año_construccion" not in datos and "ano_construccion" in datos:
        datos["año_construccion"] = datos.pop("ano_construccion")
    datos.pop("ano_construccion", None)
    año = int(datos.get("año_construccion", 1980))
    datos["año_construccion"] = año
    deducciones = inferir_por_antiguedad(año)

    if "aislamiento_fachada" not in datos or datos["aislamiento_fachada"] is None:
        datos["aislamiento_fachada"] = deducciones["aislamiento_fachada"]

    if "tipo_ventanas" not in datos or datos["tipo_ventanas"] is None:
        datos["tipo_ventanas"] = deducciones["tipo_ventanas"]

    # 3. Asignar sistema de calefacción estándar si no se especifica
    if "sistema_calefaccion" not in datos or datos["sistema_calefaccion"] is None:
        datos["sistema_calefaccion"] = SistemaCalefaccion.GAS_NATURAL

    # 4. Estimar factura si no se declara gasto anual
    if "factura_anual_estimada_eur" not in datos or datos["factura_anual_estimada_eur"] is None:
        superficie = float(datos.get("superficie_util_m2", 90.0))
        datos["factura_anual_estimada_eur"] = estimar_factura_anual(superficie)

    # 5. Instanciar y validar con Pydantic
    return ViviendaModel(**datos)
