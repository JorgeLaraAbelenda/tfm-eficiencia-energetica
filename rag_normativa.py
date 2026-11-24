"""Indexa los PDF de la carpeta RAG en ChromaDB y recupera los fragmentos
que alimentan la consulta de subvenciones."""

import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, List
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from pypdf import PdfReader

CARPETA_RAG = Path(__file__).resolve().parent / "RAG"
# Chroma no reabre el índice HNSW si la ruta lleva tildes (la carpeta del proyecto va en OneDrive).
CARPETA_CHROMA = Path(os.environ.get(
    "CHROMA_PATH",
    Path.home() / "AppData" / "Local" / "tfm-eficiencia-energetica" / "chroma_db",
))
ARCHIVO_CUESTIONARIO = Path(__file__).resolve().parent / "cuestionario_vivienda.xlsx"
NOMBRE_COLECCION = "normativa_ayudas"
TAMANO_FRAGMENTO = 1100
SOLAPE = 180

NS_HOJA = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
NS_REL = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

_embedding = DefaultEmbeddingFunction()


def _firma_pdfs() -> str:
    partes = []
    for pdf in sorted(CARPETA_RAG.glob("*.pdf")):
        stat = pdf.stat()
        partes.append(f"{pdf.name}:{stat.st_size}:{stat.st_mtime_ns}")
    return hashlib.sha256("\n".join(partes).encode("utf-8")).hexdigest()


def _texto_pagina(pagina) -> str:
    texto = pagina.extract_text() or ""
    return re.sub(r"\s+", " ", texto).strip()


def _trocear(texto: str) -> List[str]:
    if len(texto) <= TAMANO_FRAGMENTO:
        return [texto] if len(texto) >= 80 else []
    fragmentos = []
    inicio = 0
    while inicio < len(texto):
        fin = min(inicio + TAMANO_FRAGMENTO, len(texto))
        if fin < len(texto):
            corte = texto.rfind(". ", inicio + 400, fin)
            if corte != -1:
                fin = corte + 1
        pieza = texto[inicio:fin].strip()
        if len(pieza) >= 80:
            fragmentos.append(pieza)
        if fin >= len(texto):
            break
        inicio = max(fin - SOLAPE, inicio + 1)
    return fragmentos


def _documentos_pdf() -> List[Dict[str, Any]]:
    if not CARPETA_RAG.is_dir():
        raise FileNotFoundError(f"No existe la carpeta de normativa: {CARPETA_RAG}")
    pdfs = sorted(CARPETA_RAG.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No hay PDF en {CARPETA_RAG}")

    documentos = []
    for pdf in pdfs:
        lector = PdfReader(str(pdf))
        for numero, pagina in enumerate(lector.pages, start=1):
            texto = _texto_pagina(pagina)
            for indice, fragmento in enumerate(_trocear(texto), start=1):
                documentos.append({
                    "id": f"{pdf.stem}-p{numero}-f{indice}",
                    "texto": fragmento,
                    "metadata": {
                        "fuente": pdf.name,
                        "pagina": numero,
                        "fragmento": indice,
                    },
                })
    if not documentos:
        raise ValueError("Los PDF de RAG no contienen texto extraíble.")
    return documentos


def _cliente():
    CARPETA_CHROMA.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CARPETA_CHROMA))


def asegurar_indice():
    """Crea o reutiliza la colección vectorial. Reindexa si cambia algún PDF."""
    firma = _firma_pdfs()
    marca = CARPETA_CHROMA / "firma.txt"
    cliente = _cliente()
    if marca.exists() and marca.read_text(encoding="utf-8") == firma:
        return cliente.get_collection(NOMBRE_COLECCION, embedding_function=_embedding)

    try:
        cliente.delete_collection(NOMBRE_COLECCION)
    except Exception:
        pass

    coleccion = cliente.create_collection(
        name=NOMBRE_COLECCION,
        embedding_function=_embedding,
        metadata={"hnsw:space": "cosine"},
    )
    documentos = _documentos_pdf()
    lote = 64
    for inicio in range(0, len(documentos), lote):
        grupo = documentos[inicio:inicio + lote]
        coleccion.add(
            ids=[item["id"] for item in grupo],
            documents=[item["texto"] for item in grupo],
            metadatas=[item["metadata"] for item in grupo],
        )
    marca.write_text(firma, encoding="utf-8")
    return coleccion


def _coleccion():
    return _cliente().get_collection(NOMBRE_COLECCION, embedding_function=_embedding)


def recuperar(consulta: str, k: int = 6) -> List[Dict[str, Any]]:
    coleccion = _coleccion()
    resultado = coleccion.query(query_texts=[consulta], n_results=k)
    fragmentos = []
    documentos = resultado.get("documents") or [[]]
    metadatos = resultado.get("metadatas") or [[]]
    distancias = resultado.get("distances") or [[]]
    for texto, meta, distancia in zip(documentos[0], metadatos[0], distancias[0]):
        fragmentos.append({
            "fuente": meta.get("fuente", ""),
            "pagina": meta.get("pagina", ""),
            "texto": texto,
            "distancia": distancia,
        })
    return fragmentos


def recuperar_para_vivienda(ficha: Dict[str, Any], k: int = 8) -> List[Dict[str, Any]]:
    """Lanza varias búsquedas y devuelve fragmentos únicos ordenados por cercanía."""
    consultas = [
        consulta_desde_diccionario(ficha),
        "subvenciones ayudas rehabilitación energética residencial requisitos beneficiarios porcentaje",
        "deducción IRPF obras mejora eficiencia energética vivienda habitual",
        "programa de rehabilitación de edificios y viviendas RD 853 requisitos de ahorro",
    ]
    vistos = set()
    unidos: List[Dict[str, Any]] = []
    for consulta in consultas:
        for fragmento in recuperar(consulta, k=k):
            clave = (fragmento["fuente"], fragmento["pagina"], fragmento["texto"][:80])
            if clave in vistos:
                continue
            vistos.add(clave)
            unidos.append(fragmento)
    unidos.sort(key=lambda item: item["distancia"])
    return unidos[:12]


def consulta_desde_diccionario(ficha: Dict[str, Any]) -> str:
    lineas = ["Vivienda residencial en España. Ayudas y subvenciones aplicables."]
    for fila in ficha.get("detalle", []):
        lineas.append(
            f"Pregunta {fila['pregunta']} ({fila.get('variable', '')}): "
            f"contestación '{fila['contestacion']}', valor asignado '{fila.get('valor_asignado', '')}'."
        )
    if not ficha.get("detalle"):
        for numero, contestacion in ficha.get("diccionario", {}).items():
            lineas.append(f"Pregunta {numero}: {contestacion}")
    return " ".join(lineas)


def _identificador_norma(fuente: str) -> str:
    hallado = re.search(r"(BOE-A-\d{4}-\d+)", fuente or "", flags=re.IGNORECASE)
    if hallado:
        return hallado.group(1).upper()
    if "dbhe" in (fuente or "").lower():
        return "Documento Básico HE del Código Técnico de la Edificación"
    return "norma recuperada"


def fragmentos_a_contexto(fragmentos: List[Dict[str, Any]]) -> str:
    bloques = []
    for indice, fragmento in enumerate(fragmentos, start=1):
        bloques.append(
            f"[{indice}] {_identificador_norma(fragmento['fuente'])}\n{fragmento['texto']}"
        )
    return "\n\n".join(bloques)


def _textos_compartidos(archivo: ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in archivo.namelist():
        return []
    raiz = ET.fromstring(archivo.read("xl/sharedStrings.xml"))
    textos = []
    for nodo in raiz.findall("m:si", NS_HOJA):
        partes = [texto.text or "" for texto in nodo.findall(".//m:t", NS_HOJA)]
        textos.append("".join(partes))
    return textos


def _rutas_hojas(archivo: ZipFile) -> Dict[str, str]:
    libro = ET.fromstring(archivo.read("xl/workbook.xml"))
    relaciones = ET.fromstring(archivo.read("xl/_rels/workbook.xml.rels"))
    destinos = {rel.get("Id"): rel.get("Target") for rel in relaciones.findall("r:Relationship", NS_REL)}
    rutas = {}
    for hoja in libro.findall("m:sheets/m:sheet", NS_HOJA):
        destino = destinos[hoja.get(RID)]
        if not destino.startswith("xl/"):
            destino = "xl/" + destino.lstrip("/")
        rutas[hoja.get("name")] = destino
    return rutas


def _leer_tabla(archivo: ZipFile, ruta: str, compartidos: List[str]) -> List[Dict[str, str]]:
    raiz = ET.fromstring(archivo.read(ruta))
    filas = []
    for fila in raiz.findall("m:sheetData/m:row", NS_HOJA):
        celdas: Dict[str, str] = {}
        for celda in fila.findall("m:c", NS_HOJA):
            columna = "".join(caracter for caracter in celda.get("r", "") if caracter.isalpha())
            tipo = celda.get("t")
            if tipo == "inlineStr":
                nodo = celda.find("m:is/m:t", NS_HOJA)
                valor = nodo.text if nodo is not None and nodo.text else ""
            else:
                nodo = celda.find("m:v", NS_HOJA)
                bruto = nodo.text if nodo is not None and nodo.text else ""
                if tipo == "s" and bruto.isdigit():
                    valor = compartidos[int(bruto)]
                else:
                    valor = bruto
            celdas[columna] = valor
        if any(celdas.values()):
            filas.append(celdas)
    return filas


def cargar_cuestionario(ruta: Path = ARCHIVO_CUESTIONARIO) -> Dict[str, Any]:
    """Lee el diccionario pregunta → contestación y el detalle técnico del Excel."""
    if not ruta.exists():
        raise FileNotFoundError(
            f"No está {ruta.name}. Completa el cuestionario para generar el diccionario."
        )
    with ZipFile(ruta) as archivo:
        compartidos = _textos_compartidos(archivo)
        rutas = _rutas_hojas(archivo)
        tablas = {nombre: _leer_tabla(archivo, destino, compartidos) for nombre, destino in rutas.items()}

    detalle = []
    respuestas = tablas.get("Respuestas", [])
    if len(respuestas) > 1:
        for fila in respuestas[1:]:
            if not fila.get("A"):
                continue
            detalle.append({
                "pregunta": int(float(fila.get("A", "0"))),
                "contestacion": fila.get("B", ""),
                "variable": fila.get("C", ""),
                "valor_asignado": fila.get("D", ""),
                "presumido": fila.get("E", ""),
            })

    diccionario = {}
    hoja_diccionario = tablas.get("Diccionario", [])
    if len(hoja_diccionario) > 1:
        for fila in hoja_diccionario[1:]:
            if fila.get("A"):
                diccionario[int(float(fila["A"]))] = fila.get("B", "")
    elif detalle:
        diccionario = {fila["pregunta"]: fila["contestacion"] for fila in detalle}

    if not diccionario:
        raise ValueError(f"{ruta.name} no contiene respuestas en la hoja Diccionario.")
    return {"diccionario": diccionario, "detalle": detalle}
