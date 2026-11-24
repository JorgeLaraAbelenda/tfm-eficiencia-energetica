import os
import json
from typing import Any, Dict, List
from dotenv import load_dotenv
from google import genai
from google.genai import types

from rag_normativa import asegurar_indice, fragmentos_a_contexto, recuperar

# Carga automática de variables definidas en el archivo .env
load_dotenv()
MODELO = "gemini-3.5-flash-lite"

PROMPT_SUBVENCIONES = """Eres un asesor de ayudas públicas a la rehabilitación energética de viviendas en España.
Tu única fuente son los fragmentos normativos recuperados de la base vectorial y los datos del cuestionario.
Pautas obligatorias:
1. Indica solo subvenciones, deducciones o programas de ayuda que estén respaldados por esos fragmentos.
2. Explica, para cada ayuda, qué dato del cuestionario encaja con el requisito y cuál no consta.
3. No inventes porcentajes, importes, plazos, territorios ni órganos convocantes. Si el fragmento no los da, dilo.
4. Si citas una norma del BOE, usa solo el identificador, por ejemplo BOE-A-2021-16233. No escribas nombres de archivo ni números de página.
5. Si los fragmentos no permiten afirmar que el caso cumple, dilo con claridad en lugar de suponerlo.
"""

def _cliente() -> genai.Client:
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("No se ha configurado la variable de entorno GOOGLE_API_KEY en el archivo .env ni en el sistema.")
    return genai.Client(api_key=api_key)


def _consulta_normativa():
    """Devuelve la herramienta con la que el modelo consulta la base normativa."""
    fragmentos: List[Dict[str, Any]] = []
    vistos = set()

    def consultar_normativa(consulta: str) -> str:
        """Busca en la base normativa los fragmentos más próximos a la consulta.

        Args:
            consulta: Pregunta sobre ayudas, deducciones o requisitos de la vivienda.
        """
        asegurar_indice()
        encontrados = recuperar(consulta, k=6)
        nuevos = []
        for fragmento in encontrados:
            clave = (fragmento["fuente"], fragmento["pagina"], fragmento["texto"][:80])
            if clave in vistos:
                continue
            vistos.add(clave)
            fragmentos.append(fragmento)
            nuevos.append(fragmento)
        return fragmentos_a_contexto(nuevos) or "La consulta no ha devuelto fragmentos."

    return consultar_normativa, fragmentos


def _pedir(contenido: str, herramienta, instruccion: str):
    """Envía el expediente y ejecuta las consultas que pide el modelo."""
    cliente = _cliente()
    config = types.GenerateContentConfig(
        system_instruction=instruccion,
        tools=[herramienta],
        temperature=0.2,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    contenidos = [contenido]
    respuesta = cliente.models.generate_content(model=MODELO, contents=contenidos, config=config)
    for _ in range(4):
        llamadas = list(respuesta.function_calls or [])
        if not llamadas:
            break
        contenidos.append(respuesta.candidates[0].content)
        partes = []
        for llamada in llamadas:
            argumentos = dict(llamada.args or {})
            resultado = herramienta(**argumentos)
            partes.append(types.Part.from_function_response(
                name=llamada.name,
                response={"resultado": resultado},
            ))
        contenidos.append(types.Content(role="user", parts=partes))
        respuesta = cliente.models.generate_content(model=MODELO, contents=contenidos, config=config)
    return respuesta


def _leer_json(texto: str) -> Dict[str, str]:
    limpio = (texto or "").strip()
    if limpio.startswith("```"):
        limpio = limpio.strip("`")
        limpio = limpio.split("\n", 1)[-1]
    inicio = limpio.find("{")
    fin = limpio.rfind("}")
    if inicio < 0 or fin <= inicio:
        return {}
    datos = json.loads(limpio[inicio:fin + 1])
    return {
        "diagnostico": str(datos.get("diagnostico", "")),
        "ayudas_complementarias": str(datos.get("ayudas_complementarias", "")),
        "hoja_de_ruta": str(datos.get("hoja_de_ruta", "")),
    }


def consultar_subvenciones_rag(ficha: Dict[str, Any]) -> str:
    """El modelo consulta la base normativa y responde qué ayudas encajan con la vivienda."""
    herramienta, fragmentos = _consulta_normativa()
    prompt = f"""Estos son los valores del diccionario generado por el cuestionario de la vivienda.
Cada clave es el número de pregunta y cada valor es la contestación:

{json.dumps(ficha.get("diccionario", {}), indent=2, ensure_ascii=False)}

Detalle técnico asociado a esas contestaciones:
{json.dumps(ficha.get("detalle", []), indent=2, ensure_ascii=False)}

Antes de responder, llama a consultar_normativa con las preguntas que necesites sobre ayudas, deducciones y requisitos. Usa solo los fragmentos que devuelva la herramienta. Ordena la respuesta así:
1. Ayudas a las que el caso puede optar, con el requisito que cumple y la cita del documento
2. Ayudas mencionadas en los fragmentos que no se pueden confirmar con estos datos
3. Datos del cuestionario que faltan para cerrar la elegibilidad
"""
    respuesta = _pedir(prompt, herramienta, PROMPT_SUBVENCIONES)
    if not fragmentos:
        respuesta = _pedir(
            prompt + "\n\nAún no has consultado la base normativa. Llama a consultar_normativa antes de responder.",
            herramienta,
            PROMPT_SUBVENCIONES,
        )
    return respuesta.text or ""


def consultar_y_redactar(expediente: Dict[str, Any]) -> Dict[str, Any]:
    """El modelo consulta la normativa con los datos recibidos y redacta los tres textos."""
    herramienta, fragmentos = _consulta_normativa()
    comunidad = expediente.get("comunidad", "su comunidad autónoma")
    prompt = f"""Tienes el cuestionario y el cálculo de la vivienda. Primero llama a consultar_normativa
con las consultas que necesites sobre rehabilitación, deducciones y requisitos de ayuda.
Después redacta, usando solo esas respuestas y las cifras del expediente.

Si usas una sigla, explícala en la misma frase. PREE 5000 es la ayuda de rehabilitación energética para municipios de hasta 5.000 habitantes.
No cambies ninguna cifra. No añadas importes, porcentajes ni plazos que no estén en el expediente o en los fragmentos.
Si un incentivo no está respaldado por los fragmentos, dilo.
La vivienda está en {comunidad}. El único órgano de vivienda que puedes nombrar es el de {comunidad}.
No menciones ninguna otra comunidad autónoma, aunque salga en los fragmentos.
No escribas nombres de archivo, ni .pdf, ni números de página. Si citas una norma del BOE, usa solo el identificador, por ejemplo BOE-A-2021-16233.
No menciones el PREE 5000 si el municipio no tiene 5.000 habitantes o menos. No menciones las placas solares si el expediente no las pide.

Expediente:
{json.dumps(expediente, indent=2, ensure_ascii=False)}

Cuando ya hayas consultado la base, responde únicamente con un JSON de tres claves:
- diagnostico: por dónde pierde más calor la vivienda y qué implica, en lenguaje cotidiano, usando las pérdidas del expediente
- ayudas_complementarias: deducción en la renta, certificados de ahorro, IBI, ICIO, PREE 5000 y fotovoltaica, solo si el expediente y los fragmentos lo permiten
- hoja_de_ruta: pasos administrativos de este caso ante el órgano de vivienda de {comunidad}
"""
    instruccion = (
        "Consultas la base normativa con la herramienta antes de redactar. "
        "No inventes normas ni cifras. El diagnóstico sale de las pérdidas del expediente."
    )
    respuesta = _pedir(prompt, herramienta, instruccion)
    if not fragmentos:
        respuesta = _pedir(
            prompt + "\n\nAún no has llamado a consultar_normativa. Hazlo ahora y después entrega el JSON.",
            herramienta,
            instruccion,
        )
    try:
        relatos = _leer_json(respuesta.text or "")
    except (json.JSONDecodeError, TypeError, ValueError):
        relatos = {}
    fragmentos.sort(key=lambda item: item.get("distancia", 1))
    return {"relatos": relatos, "fragmentos": fragmentos[:12]}
