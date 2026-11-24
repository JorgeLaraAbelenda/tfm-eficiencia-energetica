from typing import Dict, Any, Optional
from preprocessing import sanear_y_crear_vivienda
from informe_auditoria import construir_informe, expediente_para_modelo
from thermal_engine import simular_rehabilitacion_rd853
from agent import consultar_subvenciones_rag, consultar_y_redactar
from rag_normativa import cargar_cuestionario

VENTANAS_CUESTIONARIO = {
    "simple": "simple_metal",
    "simple_metal": "simple_metal",
    "doble_estandar": "doble_aluminio",
    "doble_aluminio": "doble_aluminio",
    "doble_bajo_emisivo": "doble_pvc",
    "doble_pvc": "doble_pvc",
    "triple_bajo_emisivo": "triple_bajo_emisivo",
}

TIPOLOGIA_CUESTIONARIO = {
    "piso_intermedio": "piso_intermedio",
    "atico": "atico",
    "bajo": "bajo",
    "unifamiliar": "unifamiliar_adosada",
    "unifamiliar_adosada": "unifamiliar_adosada",
    "unifamiliar_aislada": "unifamiliar_aislada",
}

def construir_datos_tecnicos(vivienda, simulacion: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "resumen_inmueble": {
            "superficie_util_m2": vivienda.superficie_util_m2,
            "año_construccion": vivienda.año_construccion,
            "zona_climatica": vivienda.zona_climatica.value,
            "tipo_vivienda": vivienda.tipo_vivienda.value,
            "aislamiento_fachada": vivienda.aislamiento_fachada,
            "tipo_ventanas": vivienda.tipo_ventanas.value,
            "sistema_calefaccion": vivienda.sistema_calefaccion.value,
            "factura_base_eur": vivienda.factura_anual_estimada_eur
        },
        "balance_energetico": {
            "demanda_inicial_kwh_m2": simulacion["inicial"]["demanda_especifica_kwh_m2"],
            "consumo_inicial_ep_nren_kwh_m2": simulacion["inicial"]["energia_primaria_nren_kwh_m2"],
            "consumo_propuesto_ep_nren_kwh_m2": simulacion["propuesto"]["energia_primaria_nren_kwh_m2"],
            "porcentaje_reduccion_consumo": simulacion["porcentaje_ahorro_ep"]
        },
        "dictamen_ayudas_rd853": {
            "cumple_requisito_minimo": simulacion["porcentaje_ahorro_ep"] >= 30.0,
            "tramo_subvencion_concedido_pct": simulacion["subvencion_rd853_porcentaje"],
            "cuantia_maxima_subvencion_eur": simulacion["ayuda_maxima_eur"],
            "ahorro_factura_estimado_eur_año": simulacion["ahorro_factura_anual_eur"]
        }
    }

def _como_bool(valor: Any) -> Optional[bool]:
    if isinstance(valor, bool):
        return valor
    texto = str(valor).strip().lower()
    if texto in {"si", "sí", "true", "1"}:
        return True
    if texto in {"no", "false", "0"}:
        return False
    return None

def datos_desde_detalle(detalle: list) -> Dict[str, Any]:
    """Traduce los valores del cuestionario al esquema del motor térmico."""
    por_variable = {fila.get("variable"): fila for fila in detalle}
    if "año_construccion" not in por_variable and "ano_construccion" in por_variable:
        por_variable["año_construccion"] = por_variable["ano_construccion"]
    obligatorias = (
        "ubicacion", "superficie_util_m2", "tipo_vivienda", "año_construccion",
        "aislamiento_fachada", "tipo_ventanas", "sistema_calefaccion", "factura_anual_estimada_eur",
    )
    if any(nombre not in por_variable for nombre in obligatorias):
        raise ValueError("El cuestionario no tiene las 9 respuestas necesarias.")

    def valor(nombre: str) -> Any:
        return por_variable[nombre].get("valor_asignado")

    datos: Dict[str, Any] = {
        "superficie_util_m2": float(valor("superficie_util_m2")),
        "año_construccion": int(float(valor("año_construccion"))),
        "tipo_vivienda": TIPOLOGIA_CUESTIONARIO.get(str(valor("tipo_vivienda")), "piso_intermedio"),
        "sistema_calefaccion": str(valor("sistema_calefaccion")),
        "factura_anual_estimada_eur": float(valor("factura_anual_estimada_eur")),
    }
    provincia = str(por_variable["ubicacion"].get("contestacion", ""))
    if provincia and provincia != "Lo desconozco":
        datos["ubicacion"] = provincia
    zona = str(valor("ubicacion"))
    if zona in {"A", "B", "C", "D", "E"}:
        datos["zona_climatica"] = zona
    aislamiento = _como_bool(valor("aislamiento_fachada"))
    if aislamiento is not None:
        datos["aislamiento_fachada"] = aislamiento
    ventanas = VENTANAS_CUESTIONARIO.get(str(valor("tipo_ventanas")))
    if ventanas:
        datos["tipo_ventanas"] = ventanas
    return datos

def ficha_desde_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    filas = payload.get("filas") or []
    detalle = []
    for fila in filas:
        if not isinstance(fila, dict) or "pregunta" not in fila:
            continue
        detalle.append({
            "pregunta": int(fila["pregunta"]),
            "contestacion": fila.get("contestacion", ""),
            "variable": fila.get("variable", ""),
            "valor_asignado": fila.get("valor_asignado"),
            "presumido": bool(fila.get("presumido")),
            "nota": fila.get("nota", ""),
        })
    diccionario_bruto = payload.get("diccionario") or {}
    diccionario = {int(clave): valor for clave, valor in diccionario_bruto.items()}
    if len(detalle) < 9 or len(diccionario) < 9:
        raise ValueError("Faltan respuestas del cuestionario.")
    return {"diccionario": diccionario, "detalle": detalle}

def _aislamiento_cubierta(detalle: list):
    for fila in detalle:
        if fila.get("variable") == "aislamiento_cubierta":
            return _como_bool(fila.get("valor_asignado"))
    return None

def _simular_desde_ficha(payload: Dict[str, Any]):
    ficha = ficha_desde_payload(payload)
    datos = datos_desde_detalle(ficha["detalle"])
    vivienda = sanear_y_crear_vivienda(datos)
    simulacion = simular_rehabilitacion_rd853(
        vivienda,
        aislamiento_cubierta=_aislamiento_cubierta(ficha["detalle"]),
    )
    return ficha, vivienda, simulacion

def procesar_resultado_cuestionario(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Calcula el balance térmico. El informe largo se pide aparte, con el botón del cuestionario."""
    _ficha, vivienda, simulacion = _simular_desde_ficha(payload)
    return {"ok": True, "termico": construir_datos_tecnicos(vivienda, simulacion)}

def generar_informe_cuestionario(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Pasa la ficha y el cálculo al modelo, que consulta la normativa, y compone el informe."""
    import base64
    from informe_auditoria import html_a_pdf

    ficha, vivienda, simulacion = _simular_desde_ficha(payload)
    try:
        paquete = consultar_y_redactar(expediente_para_modelo(ficha, vivienda, simulacion))
    except Exception:
        paquete = {"relatos": {}, "fragmentos": []}
    documento = construir_informe(
        ficha,
        vivienda,
        simulacion,
        relatos=paquete.get("relatos"),
        fragmentos=paquete.get("fragmentos"),
    )
    pdf = base64.b64encode(html_a_pdf(documento)).decode("ascii")
    return {"ok": True, "html": documento, "pdf": pdf}

def consultar_ayudas_desde_cuestionario() -> str:
    """El modelo consulta la normativa a partir de las respuestas ya guardadas."""
    ficha = cargar_cuestionario()
    return consultar_subvenciones_rag(ficha)

if __name__ == "__main__":
    print("=== CONSULTA DE SUBVENCIONES CON RAG (main.py) ===")
    print(consultar_ayudas_desde_cuestionario())
