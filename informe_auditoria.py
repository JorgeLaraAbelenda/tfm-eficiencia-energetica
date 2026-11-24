"""Informe preliminar de auditoría a partir de la ficha, el motor y los textos del modelo."""

import html
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

PRECIO_SATE_EUR_M2 = 95.0
PRECIO_CUBIERTA_EUR_M2 = 70.0
PRECIO_VENTANA_EUR_M2 = 450.0
PRECIO_AEROTERMIA_FIJO_EUR = 7500.0
PRECIO_AEROTERMIA_EUR_M2 = 35.0

COMUNIDAD = {
    "Almería": "Andalucía", "Cádiz": "Andalucía", "Córdoba": "Andalucía", "Granada": "Andalucía",
    "Huelva": "Andalucía", "Jaén": "Andalucía", "Málaga": "Andalucía", "Sevilla": "Andalucía",
    "Huesca": "Aragón", "Teruel": "Aragón", "Zaragoza": "Aragón",
    "Asturias": "Principado de Asturias",
    "Illes Balears": "Illes Balears",
    "Las Palmas": "Canarias", "Santa Cruz de Tenerife": "Canarias",
    "Cantabria": "Cantabria",
    "Albacete": "Castilla-La Mancha", "Ciudad Real": "Castilla-La Mancha", "Cuenca": "Castilla-La Mancha",
    "Guadalajara": "Castilla-La Mancha", "Toledo": "Castilla-La Mancha",
    "Ávila": "Castilla y León", "Burgos": "Castilla y León", "León": "Castilla y León",
    "Palencia": "Castilla y León", "Salamanca": "Castilla y León", "Segovia": "Castilla y León",
    "Soria": "Castilla y León", "Valladolid": "Castilla y León", "Zamora": "Castilla y León",
    "Barcelona": "Cataluña", "Girona": "Cataluña", "Lleida": "Cataluña", "Tarragona": "Cataluña",
    "Alicante": "Comunitat Valenciana", "Castellón": "Comunitat Valenciana", "Valencia": "Comunitat Valenciana",
    "Badajoz": "Extremadura", "Cáceres": "Extremadura",
    "A Coruña": "Galicia", "Lugo": "Galicia", "Ourense": "Galicia", "Pontevedra": "Galicia",
    "Madrid": "Comunidad de Madrid",
    "Murcia": "Región de Murcia",
    "Navarra": "Comunidad Foral de Navarra",
    "Álava": "País Vasco", "Bizkaia": "País Vasco", "Gipuzkoa": "País Vasco",
    "La Rioja": "La Rioja",
    "Ceuta": "Ciudad de Ceuta", "Melilla": "Ciudad de Melilla",
}

ETIQUETA_TIPO = {
    "piso_intermedio": "Piso intermedio",
    "atico": "Último piso / ático",
    "bajo": "Piso bajo",
    "unifamiliar": "Vivienda unifamiliar",
    "unifamiliar_adosada": "Vivienda unifamiliar",
    "unifamiliar_aislada": "Vivienda unifamiliar",
}
ETIQUETA_VENTANA = {
    "simple": "Vidrio simple",
    "simple_metal": "Vidrio simple y marco metálico",
    "doble_estandar": "Doble acristalamiento estándar",
    "doble_aluminio": "Doble acristalamiento estándar",
    "doble_bajo_emisivo": "Doble acristalamiento bajo emisivo",
    "doble_pvc": "Doble acristalamiento con marco de PVC",
    "triple_bajo_emisivo": "Triple acristalamiento bajo emisivo",
}
TITULO_NORMA = {
    "BOE-A-2004-4214-consolidado.pdf": "Real Decreto Legislativo 2/2004, por el que se aprueba el texto refundido de la Ley Reguladora de las Haciendas Locales (BOE-A-2004-4214)",
    "BOE-A-2021-10824-consolidado.pdf": "Real Decreto 477/2021, de ayudas al autoconsumo, el almacenamiento y los sistemas térmicos renovables (BOE-A-2021-10824)",
    "BOE-A-2021-13267.pdf": "Real Decreto 690/2021, por el que se regula el Fondo de Restauración Ecológica y Resiliencia (BOE-A-2021-13267)",
    "BOE-A-2021-16230-consolidado.pdf": "Real Decreto-ley 19/2021, de medidas urgentes para impulsar la rehabilitación edificatoria (BOE-A-2021-16230)",
    "BOE-A-2021-16233-consolidado.pdf": "Real Decreto 853/2021, de programas de ayuda a la rehabilitación residencial y la vivienda social (BOE-A-2021-16233)",
    "BOE-A-2022-802-consolidado.pdf": "Real Decreto 42/2022, del Bono Alquiler Joven y el Plan Estatal de vivienda 2022-2025 (BOE-A-2022-802)",
    "BOE-A-2022-9838.pdf": "Ley 10/2022, de medidas urgentes para impulsar la rehabilitación edificatoria (BOE-A-2022-9838)",
    "BOE-A-2023-2045.pdf": "Resolución de 19 de enero de 2023, de la Subsecretaría del Ministerio de Sanidad (BOE-A-2023-2045)",
    "DBHE.pdf": "Documento Básico HE Ahorro de energía del Código Técnico de la Edificación",
}

OTRAS_COMUNIDADES = (
    "Andalucía", "Aragón", "Principado de Asturias", "Asturias", "Illes Balears", "Islas Baleares",
    "Canarias", "Cantabria", "Castilla-La Mancha", "Castilla y León", "Cataluña", "Catalunya",
    "Comunitat Valenciana", "Comunidad Valenciana", "Extremadura", "Galicia", "Comunidad de Madrid",
    "Región de Murcia", "Murcia", "Comunidad Foral de Navarra", "Navarra", "País Vasco", "Euskadi",
    "La Rioja", "Ciudad de Ceuta", "Ceuta", "Ciudad de Melilla", "Melilla",
)

ETIQUETA_CALEFACCION = {
    "gas_natural": "Caldera de gas natural",
    "gasoleo": "Caldera de gasóleo",
    "electrico_efecto_joule": "Radiadores eléctricos o acumuladores",
    "bomba_calor_aerotermia": "Bomba de calor / aerotermia",
    "biomasa": "Biomasa",
}


def _fila(detalle: List[Dict[str, Any]], variable: str) -> Dict[str, Any]:
    for fila in detalle:
        if fila.get("variable") == variable:
            return fila
    return {}


def _num(valor: Any, decimales: int = 2) -> str:
    return f"{float(valor):,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _eur(valor: Any) -> str:
    return _num(valor) + " €"


def _si_no(valor: Any) -> str:
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    texto = str(valor).strip().lower()
    if texto in {"si", "sí", "true"}:
        return "Sí"
    if texto in {"no", "false"}:
        return "No"
    return str(valor)


def _esc(valor: Any) -> str:
    return html.escape(str(valor if valor is not None else "—"))


def _parrafos(texto: str) -> str:
    bloques = [bloque.strip() for bloque in str(texto).split("\n") if bloque.strip()]
    if not bloques:
        return "<p>—</p>"
    return "".join(f"<p>{_esc(bloque)}</p>" for bloque in bloques)


def calcular_economia(simulacion: Dict[str, Any], superficie: float, ambito_edificio: bool, habitual: bool) -> Dict[str, Any]:
    inicial = simulacion["inicial"]
    propuesto = simulacion["propuesto"]
    partidas = []

    def anadir(concepto: str, medicion: float, precio: float, unidad: str, aplica: bool) -> None:
        importe = round(medicion * precio, 2) if aplica else 0.0
        partidas.append({
            "concepto": concepto,
            "medicion": round(medicion, 2),
            "unidad": unidad,
            "precio": precio,
            "importe": importe,
            "aplica": aplica,
        })

    anadir(
        "Aislamiento por el exterior de la fachada (SATE)",
        inicial["fachada_opaca_m2"], PRECIO_SATE_EUR_M2, "m²",
        propuesto["u_muro"] < inicial["u_muro"] - 0.01,
    )
    anadir(
        "Aislamiento de la cubierta",
        inicial["cubierta_m2"], PRECIO_CUBIERTA_EUR_M2, "m²",
        inicial["cubierta_m2"] > 0 and propuesto["u_cubierta"] < inicial["u_cubierta"] - 0.01,
    )
    anadir(
        "Ventanas nuevas de PVC con doble cristal (Uw 1,3)",
        inicial["ventanas_m2"], PRECIO_VENTANA_EUR_M2, "m²",
        propuesto["u_ventanas"] < inicial["u_ventanas"] - 0.01,
    )
    anadir(
        "Bomba de calor aerotérmica (SCOP 3,8)",
        superficie, PRECIO_AEROTERMIA_EUR_M2, "m² útiles",
        propuesto["rendimiento"] > inicial["rendimiento"] + 0.05,
    )
    if partidas[-1]["aplica"]:
        partidas[-1]["importe"] = round(partidas[-1]["importe"] + PRECIO_AEROTERMIA_FIJO_EUR, 2)

    capex = round(sum(partida["importe"] for partida in partidas), 2)
    tramo = simulacion["subvencion_rd853_porcentaje"]
    subvencion = round(min(simulacion["ayuda_maxima_eur"], capex * tramo / 100.0), 2) if tramo else 0.0
    base_antes_fiscal = max(capex - subvencion, 0.0)

    reduccion_demanda = 0.0
    if inicial["demanda_especifica_kwh_m2"] > 0:
        reduccion_demanda = (
            (inicial["demanda_especifica_kwh_m2"] - propuesto["demanda_especifica_kwh_m2"])
            / inicial["demanda_especifica_kwh_m2"]
        ) * 100.0

    if not habitual:
        tramo_irpf, base_maxima, motivo_irpf = 0, 0.0, "No consta que sea la vivienda habitual, requisito de la deducción."
    elif ambito_edificio and simulacion["porcentaje_ahorro_ep"] >= 30:
        tramo_irpf, base_maxima = 60, 15000.0
        motivo_irpf = "Actuación de edificio con reducción de energía primaria no renovable de al menos el 30 %."
    elif simulacion["porcentaje_ahorro_ep"] >= 30:
        tramo_irpf, base_maxima = 40, 7500.0
        motivo_irpf = "Actuación en la vivienda con reducción de energía primaria no renovable de al menos el 30 %."
    elif reduccion_demanda >= 7:
        tramo_irpf, base_maxima = 20, 5000.0
        motivo_irpf = "La demanda de calefacción baja al menos un 7 %, sin alcanzar el 30 % de energía primaria."
    else:
        tramo_irpf, base_maxima, motivo_irpf = 0, 0.0, "La simulación no alcanza los umbrales de la deducción."

    deduccion = round(tramo_irpf / 100.0 * min(base_antes_fiscal, base_maxima), 2)
    capex_neto = round(base_antes_fiscal - deduccion, 2)
    ahorro = simulacion["ahorro_factura_anual_eur"]
    payback = round(capex_neto / ahorro, 1) if ahorro > 0 and capex_neto > 0 else None
    return {
        "partidas": partidas,
        "capex": capex,
        "subvencion_estimada": subvencion,
        "base_antes_fiscal": round(base_antes_fiscal, 2),
        "reduccion_demanda": round(reduccion_demanda, 2),
        "tramo_irpf": tramo_irpf,
        "base_maxima_irpf": base_maxima,
        "motivo_irpf": motivo_irpf,
        "deduccion_irpf": deduccion,
        "capex_neto": capex_neto,
        "gasto_rehabilitado": round(max(0.0, superficie and simulacion["ahorro_factura_anual_eur"]), 2),
        "payback": payback,
    }


def _diagnostico_base(inicial: Dict[str, Any]) -> str:
    componentes = {
        "los muros de fachada": inicial["perdidas_fachada_kwh"],
        "las ventanas": inicial["perdidas_huecos_kwh"],
        "la cubierta": inicial["perdidas_cubierta_kwh"],
        "el aire que se renueva": inicial["perdidas_ventilacion_kwh"],
    }
    mayor = max(componentes, key=componentes.get)
    return (
        f"Por donde más calor se escapa ahora es por {mayor}: "
        f"unos {_num(componentes[mayor], 0)} kWh al año. "
        f"En conjunto, la casa pierde {_num(inicial['h_tr'], 1)} vatios por cada grado de diferencia "
        f"con la calle a través de muros, ventanas y cubierta, y otros {_num(inicial['h_ve'], 1)} vatios "
        "por cada grado con el aire que entra y sale."
    )


def _hoja_base(comunidad: str, tiene_cee: bool) -> str:
    certificado = (
        "Ya hay un certificado vigente. Conviene renovarlo antes de la obra y volver a hacerlo al terminarla."
        if tiene_cee else
        "El primer paso es encargar a un arquitecto o a un ingeniero el certificado de eficiencia energética y registrarlo."
    )
    return (
        f"{certificado} Después se piden presupuestos a empresas de reformas o a un agente rehabilitador. "
        f"La solicitud de ayuda se presenta ante el órgano de vivienda de {comunidad}, "
        "en el momento que marque esa convocatoria. Al acabar la obra se registra el certificado final: "
        "es el documento que demuestra el ahorro y permite cobrar la subvención y aplicar la deducción."
    )


def _narracion_de_esta_comunidad(texto: str, comunidad: str) -> str:
    """Descarta un texto del modelo si nombra la administración de otra comunidad."""
    limpio = str(texto or "").strip()
    if not limpio:
        return ""
    propia = comunidad.casefold()
    for nombre in OTRAS_COMUNIDADES:
        if nombre.casefold() in propia:
            continue
        if re.search(rf"\b{re.escape(nombre)}\b", limpio, flags=re.IGNORECASE):
            return ""
    return limpio


def _apartado(texto: str) -> str:
    patrones = (
        r"Artículo\s+\d+",
        r"Disposición\s+(?:adicional|transitoria|final|derogatoria)(?:\s+\w+)?",
        r"Capítulo\s+[IVXLC\d]+",
        r"\bHE\s*[0-6]\b",
        r"Anexo\s+[IVXLC\d]+",
    )
    for patron in patrones:
        hallado = re.search(patron, texto, flags=re.IGNORECASE)
        if hallado:
            return hallado.group(0).strip()
    return ""


def _texto_legible(texto: str, limite: int = 700) -> str:
    """Empieza y termina en una frase, para no citar un fragmento a medias."""
    limpio = re.sub(r"\s+", " ", str(texto or "")).strip()
    if not limpio:
        return ""
    if not re.match(r"^[A-ZÁÉÍÓÚÑÜ¿«\"(0-9]", limpio):
        hallado = re.search(r"[.!?][)\]]?\s+([A-ZÁÉÍÓÚÑÜ¿«\"(])", limpio)
        if not hallado:
            return ""
        limpio = limpio[hallado.start(1):]
    recorte = limpio[:limite]
    finales = list(re.finditer(r"[.!?][)\]]?", recorte))
    if not finales:
        return ""
    return recorte[: finales[-1].end()].strip()


def _limpiar_referencias(texto: str) -> str:
    """Sustituye el nombre de archivo y las páginas por el identificador del BOE."""
    limpio = re.sub(
        r"BOE-A-(\d{4})-(\d+)(?:-consolidado)?(?:\.pdf)?(?:\s*\([^)]*\))?",
        r"BOE-A-\1-\2",
        str(texto or ""),
        flags=re.IGNORECASE,
    )
    limpio = re.sub(r"\b[\w.-]+\.pdf\b", "", limpio, flags=re.IGNORECASE)
    limpio = re.sub(r"\(\s*\)", "", limpio)
    limpio = re.sub(r"\s{2,}", " ", limpio)
    limpio = re.sub(r"\s+([,.;:])", r"\1", limpio)
    return limpio.strip()


def _cita(fragmento: Dict[str, Any]) -> str:
    cuerpo = _texto_legible(fragmento.get("texto", ""))
    if not cuerpo:
        return ""
    titulo = TITULO_NORMA.get(fragmento.get("fuente", ""), "la norma recuperada")
    apartado = _apartado(cuerpo)
    if apartado:
        intro = f"Según el {titulo}, en el apartado {apartado}, se presenta lo siguiente:"
    else:
        intro = f"Según el {titulo}, se presenta lo siguiente:"
    return (
        f"<blockquote><p><strong>{_esc(intro)}</strong></p>"
        f"<p>{_esc(cuerpo)}</p></blockquote>"
    )


def html_a_pdf(documento: str) -> bytes:
    """Convierte el mismo HTML del informe a PDF con el navegador del equipo."""
    candidatos = (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    )
    navegador = next((ruta for ruta in candidatos if ruta.exists()), None)
    if navegador is None:
        raise RuntimeError("No se ha encontrado Edge ni Chrome para generar el PDF.")
    with tempfile.TemporaryDirectory() as carpeta:
        base = Path(carpeta)
        html_path = base / "informe.html"
        pdf_path = base / "informe.pdf"
        html_path.write_text(documento, encoding="utf-8")
        proceso = subprocess.run(
            [
                str(navegador),
                "--headless=new",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--user-data-dir={base / 'perfil'}",
                f"--print-to-pdf={pdf_path}",
                html_path.resolve().as_uri(),
            ],
            check=False,
            capture_output=True,
            timeout=90,
        )
        if proceso.returncode != 0 or not pdf_path.exists() or pdf_path.stat().st_size < 1000:
            detalle = (proceso.stderr or proceso.stdout or b"").decode("utf-8", errors="replace")[-400:]
            raise RuntimeError("No se ha podido generar el PDF. " + detalle)
        return pdf_path.read_bytes()


def expediente_para_modelo(ficha: Dict[str, Any], vivienda, simulacion: Dict[str, Any]) -> Dict[str, Any]:
    """Reúne el cuestionario y el cálculo para que el modelo consulte la normativa y redacte."""
    detalle = ficha.get("detalle", [])
    ubicacion = _fila(detalle, "ubicacion")
    provincia = ubicacion.get("contestacion") or "—"
    if provincia == "Lo desconozco":
        provincia = "No indicada"
    inicial = simulacion["inicial"]
    propuesto = simulacion["propuesto"]
    ambito = str(_fila(detalle, "ambito_actuacion").get("valor_asignado") or "vivienda")
    ambito_edificio = ambito == "edificio"
    habitual = str(_fila(detalle, "vivienda_habitual").get("valor_asignado") or "si") in {"si", "sí", "true", "True"}
    economia = calcular_economia(simulacion, vivienda.superficie_util_m2, ambito_edificio, habitual)
    return {
        "provincia": provincia,
        "comunidad": COMUNIDAD.get(provincia, "la comunidad autónoma correspondiente"),
        "zona": vivienda.zona_climatica.value,
        "grados_dia": inicial["grados_dia"],
        "porcentaje_ahorro_ep": simulacion["porcentaje_ahorro_ep"],
        "reduccion_demanda": economia["reduccion_demanda"],
        "tramo_rd853": simulacion["subvencion_rd853_porcentaje"],
        "programa": "Programa 3, rehabilitación de edificio" if ambito_edificio else "Programa 4, rehabilitación de vivienda",
        "tramo_irpf": economia["tramo_irpf"],
        "municipio_pequeno": _fila(detalle, "municipio_pequeno").get("contestacion", ""),
        "fotovoltaica": _fila(detalle, "fotovoltaica").get("contestacion", ""),
        "vivienda_habitual": habitual,
        "estado_obras": _fila(detalle, "estado_obras").get("contestacion", ""),
        "regimen": _fila(detalle, "regimen_tenencia").get("contestacion", ""),
        "cuestionario": [
            {
                "pregunta": fila.get("pregunta"),
                "contestacion": fila.get("contestacion", ""),
                "valor": fila.get("valor_asignado"),
            }
            for fila in detalle
        ],
        "perdidas_kwh": {
            "fachada": inicial["perdidas_fachada_kwh"],
            "ventanas": inicial["perdidas_huecos_kwh"],
            "cubierta": inicial["perdidas_cubierta_kwh"],
            "ventilacion": inicial["perdidas_ventilacion_kwh"],
        },
        "demanda_actual_kwh_m2": inicial["demanda_especifica_kwh_m2"],
        "demanda_rehabilitada_kwh_m2": propuesto["demanda_especifica_kwh_m2"],
        "energia_primaria_actual_kwh_m2": inicial["energia_primaria_nren_kwh_m2"],
        "energia_primaria_rehabilitada_kwh_m2": propuesto["energia_primaria_nren_kwh_m2"],
    }


def construir_informe(
    ficha: Dict[str, Any],
    vivienda,
    simulacion: Dict[str, Any],
    relatos: Dict[str, str] = None,
    fragmentos: List[Dict[str, Any]] = None,
) -> str:
    detalle = ficha.get("detalle", [])
    ahora = datetime.now(ZoneInfo("Europe/Madrid"))
    ubicacion = _fila(detalle, "ubicacion")
    provincia = ubicacion.get("contestacion") or "—"
    if provincia == "Lo desconozco":
        provincia = "No indicada"
    comunidad = COMUNIDAD.get(provincia, "la comunidad autónoma correspondiente")
    zona = vivienda.zona_climatica.value
    inicial = simulacion["inicial"]
    propuesto = simulacion["propuesto"]
    ambito = str(_fila(detalle, "ambito_actuacion").get("valor_asignado") or "vivienda")
    ambito_edificio = ambito == "edificio"
    habitual = str(_fila(detalle, "vivienda_habitual").get("valor_asignado") or "si") in {"si", "sí", "true", "True"}
    economia = calcular_economia(simulacion, vivienda.superficie_util_m2, ambito_edificio, habitual)
    economia["gasto_rehabilitado"] = round(
        max(0.0, vivienda.factura_anual_estimada_eur - simulacion["ahorro_factura_anual_eur"]), 2
    )
    programa = "Programa 3, rehabilitación de edificio" if ambito_edificio else "Programa 4, rehabilitación de vivienda"
    municipio = _fila(detalle, "municipio")
    pequeno = _fila(detalle, "municipio_pequeno")
    fotovoltaica = _fila(detalle, "fotovoltaica")
    cee = _fila(detalle, "certificado_cee")
    obras = _fila(detalle, "estado_obras")
    regimen = _fila(detalle, "regimen_tenencia")
    relatos = relatos or {}
    fragmentos = list(fragmentos or [])

    diagnostico = _limpiar_referencias(
        _narracion_de_esta_comunidad(relatos.get("diagnostico", ""), comunidad)
    ) or _diagnostico_base(inicial)
    ayudas_texto = _limpiar_referencias(
        _narracion_de_esta_comunidad(relatos.get("ayudas_complementarias", ""), comunidad)
    ) or (
        "La deducción en la renta, la venta del ahorro energético y las bonificaciones del ayuntamiento "
        "dependen de la norma citada más abajo y de la ordenanza de tu municipio. "
        "Este informe orienta; no concede la ayuda."
    )
    hoja = _limpiar_referencias(
        _narracion_de_esta_comunidad(relatos.get("hoja_de_ruta", ""), comunidad)
    ) or _hoja_base(
        comunidad, str(cee.get("valor_asignado")) in {"si", "sí"}
    )

    def variacion(antes: float, despues: float) -> str:
        if antes == 0:
            return "—"
        return _num((antes - despues) / antes * 100.0, 1) + " %"

    filas_ficha = "".join(
        "<tr><td>{n}</td><td>{cont}</td></tr>".format(
            n=fila.get("pregunta", ""),
            cont=_esc(fila.get("contestacion", "")),
        )
        for fila in detalle
    )
    presunciones = [fila for fila in detalle if fila.get("presumido")]
    lista_presunciones = "".join(
        f"<li>{_esc(fila.get('nota'))}</li>"
        for fila in presunciones
        if fila.get("nota")
    ) or "<li>No se ha tenido que suponer ningún dato: todas las respuestas las ha dado el usuario.</li>"

    explicacion_obra = {
        "Aislamiento por el exterior de la fachada (SATE)": "Colocar paneles aislantes por fuera de los muros, para que la fachada deje escapar menos calor.",
        "Aislamiento de la cubierta": "Añadir aislamiento en la cubierta o el tejado, que es por donde el calor sube y se pierde hacia el exterior.",
        "Ventanas nuevas de PVC con doble cristal (Uw 1,3)": "Cambiar las ventanas actuales por otras de PVC con doble cristal de baja emisividad, que dejan pasar mucho menos calor que un cristal sencillo.",
        "Bomba de calor aerotérmica (SCOP 3,8)": "Sustituir el equipo de calefacción por una bomba de calor, que toma calor del aire de la calle. Por cada unidad de electricidad puede entregar unas 3,8 unidades de calor.",
    }
    propuestas = [
        partida for partida in economia["partidas"] if partida["aplica"]
    ]
    lista_propuestas = "".join(
        f"<li><strong>{_esc(partida['concepto'])}.</strong> {_esc(explicacion_obra.get(partida['concepto'], ''))}</li>"
        for partida in propuestas
    ) or "<li>Con el estado actual no hace falta ninguna de las obras simuladas.</li>"
    filas_capex = "".join(
        "<tr><td>{c}</td><td>{m}</td><td>{p}</td><td>{i}</td></tr>".format(
            c=_esc(partida["concepto"]),
            m=_esc(_num(partida["medicion"], 1) + " " + partida["unidad"]),
            p=_eur(partida["precio"]),
            i=_eur(partida["importe"]),
        )
        for partida in propuestas
    )
    citas = "".join(_cita(fragmento) for fragmento in fragmentos[:6]) or (
        "<p>No se han recuperado fragmentos de la base normativa.</p>"
    )
    payback = "No estimable con el ahorro calculado" if economia["payback"] is None else f"{_num(economia['payback'], 1)} años"
    nombre_municipio = municipio.get("contestacion") or "No indicado"
    if nombre_municipio == "Lo desconozco":
        nombre_municipio = "No indicado"
    municipio_txt = nombre_municipio
    if pequeno and not pequeno.get("presumido") and pequeno.get("nota"):
        municipio_txt = f"{nombre_municipio}. {pequeno.get('nota')}"

    ayudas = []
    if simulacion["subvencion_rd853_porcentaje"]:
        ayudas.append(
            f"<li><strong>Ayuda a la rehabilitación del Real Decreto 853/2021.</strong> "
            f"La energía primaria no renovable bajaría un {_num(simulacion['porcentaje_ahorro_ep'], 1)} %, "
            f"por encima del mínimo del 30 % que exige esta ayuda. Corresponde al {_esc(programa)}. "
            f"El porcentaje de este tramo es el {simulacion['subvencion_rd853_porcentaje']} % "
            f"y el tope orientativo es {_eur(simulacion['ayuda_maxima_eur'])} por vivienda. "
            f"Sobre el presupuesto estimado, la subvención sería de {_eur(economia['subvencion_estimada'])}. "
            f"Hay que confirmarlo con el certificado oficial y con la convocatoria de {_esc(comunidad)}.</li>"
        )
    if economia["tramo_irpf"]:
        ayudas.append(
            f"<li><strong>Deducción en la declaración de la renta.</strong> "
            f"Se podría deducir el {economia['tramo_irpf']} % de lo que se pague después de restar la subvención, "
            f"con un máximo de {_eur(economia['base_maxima_irpf'])}. {_esc(economia['motivo_irpf'])} "
            f"La deducción estimada es {_eur(economia['deduccion_irpf'])}. "
            f"Si el porcentaje es el 60 %, Hacienda pone un límite cada año y puede que no se recupere todo de una vez.</li>"
        )
    if str(pequeno.get("valor_asignado")) == "si":
        ayudas.append(
            "<li><strong>PREE 5000, ayuda para municipios pequeños.</strong> "
            "El padrón indica 5.000 habitantes o menos, así que la vivienda puede estudiar esta ayuda "
            "para obras de rehabilitación energética. La gestiona el Instituto para la Diversificación y Ahorro de la Energía "
            "y es distinta de la del Real Decreto 853/2021. Hay que comprobar si la convocatoria está abierta.</li>"
        )
    if str(fotovoltaica.get("valor_asignado")) == "si":
        ayudas.append(
            "<li><strong>Ayuda a las placas solares.</strong> "
            "Como se quiere valorar una instalación fotovoltaica, puede estudiarse el Real Decreto 477/2021, "
            "la línea de ayudas a las energías renovables en la vivienda. Es independiente de la rehabilitación de muros y calefacción.</li>"
        )
    if simulacion["ahorro_factura_anual_eur"] > 0:
        ayudas.append(
            "<li><strong>Venta del ahorro energético.</strong> "
            "Los kilovatios hora que deje de consumir la vivienda pueden convertirse en certificados de ahorro "
            "y venderse a una empresa autorizada. La norma no fija un precio, así que aquí no se traducen a euros. "
            "Es un ingreso posible, además de la subvención.</li>"
        )
    if nombre_municipio != "No indicado":
        ayudas.append(
            f"<li><strong>Rebaja de impuestos municipales, con potencial.</strong> "
            f"El ayuntamiento de {_esc(nombre_municipio)} puede rebajar hasta el 50 % del recibo de la vivienda "
            f"y hasta el 95 % del impuesto de la obra, solo si lo ha aprobado en su ordenanza. "
            f"Hay que consultarla; este informe no puede confirmar que exista.</li>"
        )
    lista_ayudas = "".join(ayudas) or "<li>Con estos datos no aparece una ayuda a la que la vivienda pueda acogerse.</li>"

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Informe preliminar de auditoría energética</title>
  <style>
    @page {{ margin: 16mm; }}
    body {{ margin: 0; color: #1c2420; background: #f4f1ea; font-family: "Segoe UI", sans-serif; line-height: 1.5; }}
    main {{ max-width: 920px; margin: 0 auto; padding: 32px 22px 64px; }}
    header {{ border-bottom: 3px solid #0e5c45; padding-bottom: 16px; margin-bottom: 22px; }}
    h1 {{ font-family: Georgia, serif; font-size: 30px; line-height: 1.2; margin: 0 0 8px; }}
    h2 {{ font-family: Georgia, serif; font-size: 22px; margin: 28px 0 8px; color: #0e5c45; }}
    .meta {{ color: #5c6b64; font-size: 14px; }}
    .aviso {{ background: #efe6d4; border-radius: 12px; padding: 12px 14px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 10px 0 16px; background: white; }}
    th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #d5ddd6; vertical-align: top; font-size: 14px; }}
    th {{ background: #e5f2ec; }}
    blockquote {{ margin: 10px 0; padding: 10px 12px; background: white; border-left: 3px solid #0e5c45; font-size: 14px; }}
    ol li {{ margin: 8px 0; }}
  </style>
</head>
<body>
<main>
  <header>
    <h1>Informe preliminar de auditoría energética y viabilidad de rehabilitación residencial</h1>
    <p class="meta">Emitido el {_esc(ahora.strftime("%d/%m/%Y a las %H:%M"))} (hora peninsular).</p>
  </header>
  <p class="aviso">Este informe es una estimación previa, no el certificado oficial de eficiencia energética ni la concesión de una ayuda. Sirve para valorar si las obras propuestas compensan económicamente y si merece la pena encargar el certificado y los presupuestos.</p>
  <h2>Cómo leer las palabras de este informe</h2>
  <ul>
    <li><strong>kWh</strong> (kilovatio hora): la unidad de energía de la factura. Cuantos más kWh, más consumo.</li>
    <li><strong>m²</strong>: metro cuadrado. <strong>m³</strong>: metro cúbico, el volumen de aire de la vivienda.</li>
    <li><strong>Grados-día</strong>: miden lo frío que es el invierno. Cuantos más hay, más hay que calentar para tener la casa a unos 20 °C.</li>
    <li><strong>Zona climática</strong>: letra de la A a la E que el Código Técnico asigna a cada provincia. La A es la más suave y la E la más fría.</li>
    <li><strong>Código Técnico de la Edificación (CTE)</strong>: la norma que dice cómo debe construirse y rehabilitarse un edificio. Su documento de ahorro de energía es el <strong>DB-HE</strong>. El apartado <strong>DB-HE1</strong> fija cuánto puede dejar pasar el calor la fachada, la cubierta y las ventanas.</li>
    <li><strong>U</strong>: cuánto calor deja pasar un metro cuadrado de muro o cubierta cuando fuera hay un grado menos que dentro. Se mide en <strong>W/m²K</strong> (vatios por metro cuadrado y grado). Un número alto significa que aísla mal.</li>
    <li><strong>Uw</strong>: la misma medida, aplicada a la ventana completa, marco y cristal juntos.</li>
    <li><strong>Htr</strong>: el calor que se escapa por muros, ventanas y cubierta. <strong>Hve</strong>: el que se escapa con el aire que entra y sale. Se miden en <strong>W/K</strong> (vatios por cada grado de diferencia con el exterior).</li>
    <li><strong>Puente térmico</strong>: un punto donde el aislamiento se corta, como una esquina, el canto de un forjado o el perímetro de una ventana.</li>
    <li><strong>SATE</strong>: sistema de aislamiento por el exterior. Son paneles aislantes colocados por fuera del muro.</li>
    <li><strong>PVC</strong>: el plástico rígido con el que se fabrican muchas ventanas nuevas.</li>
    <li><strong>Rendimiento</strong>: el calor útil que da el equipo por cada unidad de energía que se paga. En una bomba de calor, el rendimiento medio del invierno se llama <strong>SCOP</strong>. Un SCOP de 3,8 significa unos 3,8 kWh de calor por cada kWh de electricidad.</li>
    <li><strong>Bomba de calor o aerotermia</strong>: un equipo que toma calor del aire exterior para calentar la casa, en lugar de quemar gas o gasóleo.</li>
    <li><strong>Energía final</strong>: la energía que consume el equipo, la que se acerca a lo que marca el contador. <strong>Energía primaria no renovable</strong>: la energía de origen no renovable que hay que producir en origen para cubrir ese consumo. Es la cifra que mira la administración para conceder la ayuda.</li>
    <li><strong>Certificado de eficiencia energética (CEE)</strong>: el documento oficial, firmado por un técnico y registrado, que etiqueta el consumo de la vivienda.</li>
    <li><strong>Real Decreto 853/2021</strong>: la norma de las ayudas europeas a la rehabilitación. El <strong>Programa 3</strong> es para un edificio completo y el <strong>Programa 4</strong> para una vivienda.</li>
    <li><strong>IRPF</strong>: el impuesto sobre la renta, el de la declaración anual. Una deducción reduce lo que se paga a Hacienda.</li>
    <li><strong>IBI</strong>: el impuesto de bienes inmuebles, el recibo anual de la vivienda. <strong>ICIO</strong>: el impuesto municipal sobre la obra.</li>
    <li><strong>CAE</strong> (certificado de ahorro energético): un título por los kWh que se dejan de consumir. Se puede vender a una empresa autorizada, llamada sujeto delegado. Lo regula el Real Decreto 36/2023.</li>
    <li><strong>Real Decreto 390/2021</strong>: la norma que regula cómo se hace y se registra el certificado de eficiencia energética.</li>
    <li><strong>BOE</strong>: el Boletín Oficial del Estado. Un código como BOE-A-2021-16233 identifica la publicación; no es el nombre de un archivo.</li>
  </ul>

  <h2>1. Caracterización del inmueble y trazabilidad</h2>
  <table>
    <tr><th>Dato</th><th>Detalle</th></tr>
    <tr><td>Provincia y clima</td><td>{_esc(provincia)} · zona {_esc(zona)} · {_esc(inicial["grados_dia"])} grados-día. La zona climática (de la A, la más suave, a la E, la más fría) resume el invierno de la provincia. Los grados-día cuentan cuántos grados y durante cuántos días hay que calentar para mantener la casa a 20 °C.</td></tr>
    <tr><td>Municipio</td><td>{_esc(municipio_txt)}</td></tr>
    <tr><td>Superficie útil y tipología</td><td>{_num(vivienda.superficie_util_m2, 1)} m² · {_esc(ETIQUETA_TIPO.get(vivienda.tipo_vivienda.value, vivienda.tipo_vivienda.value))}</td></tr>
    <tr><td>Año efectivo</td><td>{vivienda.año_construccion}</td></tr>
    <tr><td>Aislamiento de fachada y cubierta</td><td>Fachada: {_si_no(vivienda.aislamiento_fachada)} · Cubierta: {_si_no(_fila(detalle, "aislamiento_cubierta").get("valor_asignado"))}</td></tr>
    <tr><td>Carpinterías</td><td>{_esc(ETIQUETA_VENTANA.get(str(_fila(detalle, "tipo_ventanas").get("valor_asignado")), vivienda.tipo_ventanas.value))}</td></tr>
    <tr><td>Calefacción</td><td>{_esc(ETIQUETA_CALEFACCION.get(vivienda.sistema_calefaccion.value, vivienda.sistema_calefaccion.value))}</td></tr>
    <tr><td>Gasto anual declarado</td><td>{_eur(vivienda.factura_anual_estimada_eur)}</td></tr>
    <tr><td>Régimen, ámbito y obras</td><td>{_esc(regimen.get("contestacion", "—"))} · {_esc("Edificio" if ambito_edificio else "Vivienda")} · {_esc(obras.get("contestacion", "—"))}</td></tr>
  </table>
  <p>Registro de presunciones cuando la contestación fue «Lo desconozco»:</p>
  <ul>{lista_presunciones}</ul>
  <table>
    <tr><th>Pregunta</th><th>Contestación</th></tr>
    {filas_ficha}
  </table>

  <h2>2. Diagnóstico del estado actual</h2>
  <p>Para saber cuánto aire hay que calentar se ha supuesto una altura de techo de {_num(inicial["altura_libre_m"], 1)} m, la habitual en una vivienda. Con {_num(vivienda.superficie_util_m2, 1)} m² útiles, el volumen de aire de la casa es de unos {_num(inicial["volumen_m3"], 0)} m³. También se supone que ese aire se renueva {_num(inicial["renovaciones_hora"], 2)} veces cada hora: es el aire que entra por rendijas y por la ventilación, y con él se escapa calor.</p>
  <p>La letra U mide cuánto calor deja pasar un metro cuadrado de muro, ventana o cubierta cuando fuera hay un grado menos que dentro. Cuanto más alto es el número, peor aísla. Uw es esa misma medida aplicada a la ventana completa, marco y cristal juntos. Htr resume el calor que se va por muros, ventanas y cubierta; se aumenta un {_num((inicial["factor_puentes"] - 1) * 100, 0)} % para contar los puentes térmicos, que son los puntos donde el aislamiento se corta (esquinas, cantos de forjado y el perímetro de las ventanas). Hve resume el calor que se va con el aire renovado. El rendimiento del equipo dice cuánto calor útil se obtiene por cada unidad de energía que se paga. En una bomba de calor ese rendimiento medio de invierno se llama SCOP: un SCOP de 3,8 significa unos 3,8 kWh de calor por cada kWh de electricidad. La energía primaria no renovable es la energía de origen no renovable que hay que producir en origen para cubrir el consumo de la casa. Es la cifra que mira la administración para decidir la ayuda, y no coincide exactamente con lo que marca el contador.</p>
  <table>
    <tr><th>Qué se mide</th><th>Valor</th></tr>
    <tr><td>Superficie estimada de fachada, ventanas y cubierta</td><td>{_num(inicial["fachada_opaca_m2"], 1)} / {_num(inicial["ventanas_m2"], 1)} / {_num(inicial["cubierta_m2"], 1)} m²</td></tr>
    <tr><td>U de fachada, Uw de ventanas y U de cubierta</td><td>{_num(inicial["u_muro"], 2)} / {_num(inicial["u_ventanas"], 2)} / {_num(inicial["u_cubierta"], 2)} W/m²K</td></tr>
    <tr><td>Pérdidas por la envolvente (Htr), con el recargo de puentes térmicos</td><td>{_num(inicial["h_tr"], 1)} W/K</td></tr>
    <tr><td>Pérdidas por el aire que se renueva (Hve)</td><td>{_num(inicial["h_ve"], 1)} W/K</td></tr>
    <tr><td>Calor que hay que aportar al año, en total y por metro cuadrado</td><td>{_num(inicial["demanda_calefaccion_kwh"], 0)} kWh/año · {_num(inicial["demanda_especifica_kwh_m2"], 1)} kWh/m²·año</td></tr>
    <tr><td>Energía que consume el equipo actual (rendimiento {_num(inicial["rendimiento"], 2)})</td><td>{_num(inicial["energia_final_kwh"], 0)} kWh/año</td></tr>
    <tr><td>Energía primaria no renovable</td><td>{_num(inicial["energia_primaria_nren_kwh_m2"], 1)} kWh/m²·año</td></tr>
  </table>
  {_parrafos(diagnostico)}

  <h2>3. Propuestas de intervención</h2>
  <p>Estas son las obras que mejorarían la eficiencia energética de esta vivienda. Solo aparecen las que, con los datos actuales, suponen una mejora.</p>
  <ul>{lista_propuestas}</ul>
  <table>
    <tr><th>Indicador</th><th>Estado actual</th><th>Estado rehabilitado</th><th>Reducción</th></tr>
    <tr><td>Calor necesario por metro cuadrado</td><td>{_num(inicial["demanda_especifica_kwh_m2"], 1)} kWh/m²·año</td><td>{_num(propuesto["demanda_especifica_kwh_m2"], 1)} kWh/m²·año</td><td>{variacion(inicial["demanda_especifica_kwh_m2"], propuesto["demanda_especifica_kwh_m2"])}</td></tr>
    <tr><td>Energía primaria no renovable</td><td>{_num(inicial["energia_primaria_nren_kwh_m2"], 1)} kWh/m²·año</td><td>{_num(propuesto["energia_primaria_nren_kwh_m2"], 1)} kWh/m²·año</td><td>{_num(simulacion["porcentaje_ahorro_ep"], 1)} %</td></tr>
    <tr><td>Gasto energético anual estimado</td><td>{_eur(vivienda.factura_anual_estimada_eur)}</td><td>{_eur(economia["gasto_rehabilitado"])}</td><td>{_eur(simulacion["ahorro_factura_anual_eur"])}/año</td></tr>
  </table>

  <h2>4. Subvenciones y ayudas a las que puede acogerse</h2>
  <ul>{lista_ayudas}</ul>
  <h3>Fragmentos recuperados de la base normativa</h3>
  {citas}

  <h2>5. Análisis económico</h2>
  <p>Los precios siguientes son una orientación para decidir, no el presupuesto de un constructor. Aislar la fachada por fuera ronda {_eur(PRECIO_SATE_EUR_M2)} por m²; la cubierta, {_eur(PRECIO_CUBIERTA_EUR_M2)} por m²; cambiar ventanas, {_eur(PRECIO_VENTANA_EUR_M2)} por m²; y la bomba de calor, {_eur(PRECIO_AEROTERMIA_FIJO_EUR)} más {_eur(PRECIO_AEROTERMIA_EUR_M2)} por m² útil.</p>
  <table>
    <tr><th>Partida</th><th>Medición</th><th>Precio unitario</th><th>Importe</th></tr>
    {filas_capex}
    <tr><td>Inversión bruta (coste de las obras, antes de ayudas)</td><td></td><td></td><td>{_eur(economia["capex"])}</td></tr>
    <tr><td>Subvención estimada del Real Decreto 853/2021</td><td></td><td></td><td>{_eur(economia["subvencion_estimada"])}</td></tr>
    <tr><td>Deducción estimada en la declaración de la renta (IRPF)</td><td></td><td></td><td>{_eur(economia["deduccion_irpf"])}</td></tr>
    <tr><td>Inversión neta (lo que pagaría el propietario)</td><td></td><td></td><td>{_eur(economia["capex_neto"])}</td></tr>
  </table>
  <p>El ahorro estimado en la factura es de {_eur(simulacion["ahorro_factura_anual_eur"])} al año. Con lo que quedaría por pagar después de ayudas y deducción, el tiempo para recuperar esa inversión es de {payback}. Se supone que la factura baja en la misma proporción que la energía primaria no renovable.</p>

  <h2>6. Hoja de ruta</h2>
  <ol>
    <li>Contratar a un arquitecto o a un ingeniero para que visite la vivienda, emita el certificado de eficiencia energética inicial y lo registre. Sin ese certificado registrado no se puede justificar la ayuda.</li>
    <li>Pedir presupuestos de obra a empresas instaladoras o a un agente rehabilitador.</li>
    <li>Presentar la solicitud ante el órgano de vivienda de {_esc(comunidad)}, en el momento que indique la convocatoria de esa comunidad: a veces antes de empezar la obra y a veces después.</li>
    <li>Hacer las obras y guardar facturas y justificantes del banco.</li>
    <li>Registrar el certificado final. Ese documento demuestra que la energía primaria no renovable ha bajado y es el que permite cobrar la subvención y aplicar la deducción en la renta.</li>
  </ol>
  {_parrafos(hoja)}
</main>
</body>
</html>"""
