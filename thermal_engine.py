from typing import Dict, Any
from models import ViviendaModel, TipoVivienda, ZonaClimatica, TipoVentana, SistemaCalefaccion

# Grados-día base 20 °C anuales aproximados según severidad CTE (Apéndice B)
GRADOS_DIA_ZONA = {
    ZonaClimatica.A: 600,
    ZonaClimatica.B: 950,
    ZonaClimatica.C: 1450,
    ZonaClimatica.D: 2100,
    ZonaClimatica.E: 2750
}

# Transmitancia límite de muros y cubiertas según CTE DB-HE1 (Tabla 3.1.1.a, RD 732/2019).
# Es el objetivo del SATE propuesto, no la transmitancia del estado actual.
U_LIMITE_MURO = {
    ZonaClimatica.A: 0.70,
    ZonaClimatica.B: 0.56,
    ZonaClimatica.C: 0.49,
    ZonaClimatica.D: 0.41,
    ZonaClimatica.E: 0.37,
}
U_LIMITE_CUBIERTA = {
    ZonaClimatica.A: 0.50,
    ZonaClimatica.B: 0.44,
    ZonaClimatica.C: 0.40,
    ZonaClimatica.D: 0.35,
    ZonaClimatica.E: 0.33,
}
U_VENTANA_REFORMA = 1.3
SCOP_AEROTERMIA_REFORMA = 3.8
FACTOR_PUENTES = 1.15
RENOVACIONES_HORA = 0.63
ALTURA_LIBRE_M = 2.5
CAPACIDAD_AIRE = 0.34
VERSION_MOTOR = "gd20-htr-1.2"

# Transmitancias térmicas típicas Uw (W/m²K) de huecos
U_VENTANAS = {
    TipoVentana.SIMPLE_METAL: 5.7,
    TipoVentana.DOBLE_ALUMINIO: 3.2,
    TipoVentana.DOBLE_PVC: 1.4,
    TipoVentana.TRIPLE_BAJO_EMISIVO: 0.9
}

# Rendimiento estacional y factor de paso a energía primaria no renovable (Cep,nren)
# Factores de paso según documento reconocido IDAE (Electricidad red peninsular: 1.954, Gas natural: 1.195)
SISTEMAS_INFO = {
    SistemaCalefaccion.GAS_NATURAL: {"rendimiento": 0.85, "factor_paso": 1.195, "emisiones_kgco2_kwh": 0.252},
    SistemaCalefaccion.GASOLEO: {"rendimiento": 0.78, "factor_paso": 1.179, "emisiones_kgco2_kwh": 0.311},
    SistemaCalefaccion.ELECTRICO_EFECTO_JOULE: {"rendimiento": 1.00, "factor_paso": 1.954, "emisiones_kgco2_kwh": 0.331},
    SistemaCalefaccion.BOMBA_CALOR_AEROTERMIA: {"rendimiento": 3.20, "factor_paso": 1.954, "emisiones_kgco2_kwh": 0.331},
    SistemaCalefaccion.BIOMASA: {"rendimiento": 0.80, "factor_paso": 0.085, "emisiones_kgco2_kwh": 0.018}
}

def estimar_superficies_envolvente(v: ViviendaModel) -> Dict[str, float]:
    """Estima las superficies expuestas al exterior (m2) según la tipología del inmueble."""
    sup = v.superficie_util_m2
    ventanas = sup * 0.15  # Ratio habitual de huecos respecto a planta: ~15%
    
    if v.tipo_vivienda == TipoVivienda.PISO_INTERMEDIO:
        fachada_opaca = (sup * 0.8) - ventanas
        cubierta = 0.0
    elif v.tipo_vivienda == TipoVivienda.ATICO:
        fachada_opaca = (sup * 0.8) - ventanas
        cubierta = sup
    elif v.tipo_vivienda == TipoVivienda.BAJO:
        fachada_opaca = (sup * 0.8) - ventanas
        cubierta = 0.0
    else:  # UNIFAMILIAR_AISLADA o UNIFAMILIAR_ADOSADA
        fachada_opaca = (sup * 1.5) - ventanas
        cubierta = sup

    return {
        "fachada_opaca_m2": max(fachada_opaca, 10.0),
        "ventanas_m2": ventanas,
        "cubierta_m2": cubierta
    }

def calcular_balance_energetico(
    v: ViviendaModel,
    aislamiento_cubierta: bool = None,
    u_muro: float = None,
    u_cubierta: float = None,
    u_ventanas: float = None,
    rendimiento: float = None,
    factor_paso: float = None,
    emisiones_kgco2_kwh: float = None,
) -> Dict[str, Any]:
    """Demanda por grados-día con transmisión corregida por puentes y ventilación."""
    env = estimar_superficies_envolvente(v)
    grados_dia = GRADOS_DIA_ZONA[v.zona_climatica]
    if aislamiento_cubierta is None:
        aislamiento_cubierta = v.aislamiento_fachada
    if u_muro is None:
        u_muro = 0.35 if v.aislamiento_fachada else 1.80
    if u_cubierta is None:
        u_cubierta = 0.40 if aislamiento_cubierta else 1.50
    if u_ventanas is None:
        u_ventanas = U_VENTANAS[v.tipo_ventanas]

    datos_sis = SISTEMAS_INFO[v.sistema_calefaccion]
    if rendimiento is None:
        rendimiento = datos_sis["rendimiento"]
    if factor_paso is None:
        factor_paso = datos_sis["factor_paso"]
    if emisiones_kgco2_kwh is None:
        emisiones_kgco2_kwh = datos_sis["emisiones_kgco2_kwh"]

    h_opaco = (
        env["fachada_opaca_m2"] * u_muro
        + env["ventanas_m2"] * u_ventanas
        + env["cubierta_m2"] * u_cubierta
    )
    h_tr = FACTOR_PUENTES * h_opaco
    volumen = v.superficie_util_m2 * ALTURA_LIBRE_M
    h_ve = CAPACIDAD_AIRE * RENOVACIONES_HORA * volumen

    def perdidas(coeficiente: float) -> float:
        return (coeficiente * grados_dia * 24) / 1000.0

    perdidas_muro = perdidas(FACTOR_PUENTES * env["fachada_opaca_m2"] * u_muro)
    perdidas_ventanas = perdidas(FACTOR_PUENTES * env["ventanas_m2"] * u_ventanas)
    perdidas_cubierta = perdidas(FACTOR_PUENTES * env["cubierta_m2"] * u_cubierta)
    perdidas_ventilacion = perdidas(h_ve)
    demanda_calefaccion_kwh = perdidas_muro + perdidas_ventanas + perdidas_cubierta + perdidas_ventilacion
    demanda_especifica_kwh_m2 = demanda_calefaccion_kwh / v.superficie_util_m2
    energia_final_kwh = demanda_calefaccion_kwh / rendimiento
    energia_primaria_nren_kwh = energia_final_kwh * factor_paso
    energia_primaria_especifica = energia_primaria_nren_kwh / v.superficie_util_m2
    emisiones_co2_kg = energia_final_kwh * emisiones_kgco2_kwh

    return {
        "demanda_calefaccion_kwh": round(demanda_calefaccion_kwh, 2),
        "demanda_especifica_kwh_m2": round(demanda_especifica_kwh_m2, 2),
        "energia_final_kwh": round(energia_final_kwh, 2),
        "energia_primaria_nren_kwh_m2": round(energia_primaria_especifica, 2),
        "emisiones_co2_kg_año": round(emisiones_co2_kg, 2),
        "grados_dia": grados_dia,
        "fachada_opaca_m2": round(env["fachada_opaca_m2"], 2),
        "ventanas_m2": round(env["ventanas_m2"], 2),
        "cubierta_m2": round(env["cubierta_m2"], 2),
        "u_muro": round(u_muro, 2),
        "u_ventanas": round(u_ventanas, 2),
        "u_cubierta": round(u_cubierta, 2),
        "h_tr": round(h_tr, 2),
        "h_ve": round(h_ve, 2),
        "volumen_m3": round(volumen, 2),
        "renovaciones_hora": RENOVACIONES_HORA,
        "factor_puentes": FACTOR_PUENTES,
        "altura_libre_m": ALTURA_LIBRE_M,
        "rendimiento": rendimiento,
        "factor_paso": factor_paso,
        "perdidas_fachada_kwh": round(perdidas_muro, 2),
        "perdidas_huecos_kwh": round(perdidas_ventanas, 2),
        "perdidas_cubierta_kwh": round(perdidas_cubierta, 2),
        "perdidas_ventilacion_kwh": round(perdidas_ventilacion, 2),
    }

def simular_rehabilitacion_rd853(v: ViviendaModel, aislamiento_cubierta: bool = None) -> Dict[str, Any]:
    """
    Simula la mejora integral recomendada (SATE a límite DB-HE1, huecos Uw 1,3
    y aerotermia SCOP 3,8) y evalúa la reducción de energía primaria.
    """
    estado_inicial = calcular_balance_energetico(v, aislamiento_cubierta=aislamiento_cubierta)
    electricidad = SISTEMAS_INFO[SistemaCalefaccion.BOMBA_CALOR_AEROTERMIA]
    estado_final = calcular_balance_energetico(
        v,
        aislamiento_cubierta=True,
        u_muro=min(estado_inicial["u_muro"], U_LIMITE_MURO[v.zona_climatica]),
        u_cubierta=min(estado_inicial["u_cubierta"], U_LIMITE_CUBIERTA[v.zona_climatica]),
        u_ventanas=min(estado_inicial["u_ventanas"], U_VENTANA_REFORMA),
        rendimiento=max(estado_inicial["rendimiento"], SCOP_AEROTERMIA_REFORMA),
        factor_paso=electricidad["factor_paso"],
        emisiones_kgco2_kwh=electricidad["emisiones_kgco2_kwh"],
    )

    # Cálculo del porcentaje de ahorro de energía primaria no renovable
    ep_inicial = estado_inicial["energia_primaria_nren_kwh_m2"]
    ep_final = estado_final["energia_primaria_nren_kwh_m2"]
    porcentaje_ahorro = ((ep_inicial - ep_final) / ep_inicial) * 100.0 if ep_inicial > 0 else 0.0

    # Determinar subvención RD 853/2021 (Programa 3/4)
    # Tramos RD 853/2021:
    # >= 30%: 40% de subvención (hasta 6.300 EUR por vivienda)
    # >= 45%: 65% de subvención (hasta 11.600 EUR por vivienda)
    # >= 60%: 80% de subvención (hasta 18.800 EUR por vivienda)
    if porcentaje_ahorro >= 60.0:
        subvencion_porcentaje = 80
        ayuda_maxima_eur = 18800.0
    elif porcentaje_ahorro >= 45.0:
        subvencion_porcentaje = 65
        ayuda_maxima_eur = 11600.0
    elif porcentaje_ahorro >= 30.0:
        subvencion_porcentaje = 40
        ayuda_maxima_eur = 6300.0
    else:
        subvencion_porcentaje = 0
        ayuda_maxima_eur = 0.0

    ahorro_economico_anual = (porcentaje_ahorro / 100.0) * v.factura_anual_estimada_eur

    return {
        "inicial": estado_inicial,
        "propuesto": estado_final,
        "porcentaje_ahorro_ep": round(porcentaje_ahorro, 2),
        "subvencion_rd853_porcentaje": subvencion_porcentaje,
        "ayuda_maxima_eur": ayuda_maxima_eur,
        "ahorro_factura_anual_eur": round(ahorro_economico_anual, 2)
    }
