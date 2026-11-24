"""Sirve el cuestionario y guarda cada respuesta en cuestionario_vivienda.xlsx."""

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent
XLSX = ROOT / "cuestionario_vivienda.xlsx"
PORT = 8765

MENSAJES_MODELO = {
    "año_construccion": "El año de construcción tiene que estar entre 1800 y 2026.",
    "superficie_util_m2": "La superficie útil tiene que ser mayor que 10 y menor que 1000 m².",
    "factura_anual_estimada_eur": "El gasto anual tiene que ser un importe mayor o igual que 0.",
}


def mensaje_modelo(exc):
    textos = []
    for error in exc.errors():
        campo = str(error.get("loc", ("dato",))[-1])
        textos.append(MENSAJES_MODELO.get(campo, "Revisa el dato introducido."))
    return " ".join(dict.fromkeys(textos))


def xml_escape(valor):
    return (
        str(valor)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def hoja(filas):
    letras = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    rows = []
    for indice_fila, fila in enumerate(filas, start=1):
        celdas = []
        for indice_col, valor in enumerate(fila):
            ref = f"{letras[indice_col]}{indice_fila}"
            if isinstance(valor, bool):
                texto = "Sí" if valor else "No"
                celdas.append(
                    f'<c r="{ref}" t="inlineStr"><is><t>{xml_escape(texto)}</t></is></c>'
                )
            elif isinstance(valor, (int, float)):
                celdas.append(f'<c r="{ref}"><v>{valor}</v></c>')
            else:
                celdas.append(
                    f'<c r="{ref}" t="inlineStr"><is><t>{xml_escape(valor)}</t></is></c>'
                )
        rows.append(f'<row r="{indice_fila}">{"".join(celdas)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(rows)}</sheetData></worksheet>"
    )


def normalizar_valor(valor):
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        return valor
    if isinstance(valor, str):
        return valor
    return "" if valor is None else str(valor)


def escribir_xlsx(payload):
    filas_entrada = payload.get("filas") or []
    diccionario = payload.get("diccionario") or {}
    if not isinstance(filas_entrada, list) or not isinstance(diccionario, dict):
        raise ValueError("El cuerpo debe incluir 'filas' y 'diccionario'.")

    tabla = [["pregunta", "contestacion", "variable", "valor_asignado", "presumido"]]
    vistos = set()
    for fila in filas_entrada:
        if not isinstance(fila, dict):
            continue
        pregunta = int(fila.get("pregunta", 0))
        if pregunta < 1 or pregunta > 30 or pregunta in vistos:
            continue
        vistos.add(pregunta)
        tabla.append([
            pregunta,
            str(fila.get("contestacion", "")),
            str(fila.get("variable", "")),
            normalizar_valor(fila.get("valor_asignado")),
            "Sí" if fila.get("presumido") else "No",
        ])

    dict_rows = [["pregunta", "contestacion"]]
    for clave in sorted(diccionario, key=lambda item: int(item)):
        pregunta = int(clave)
        if 1 <= pregunta <= 30:
            dict_rows.append([pregunta, str(diccionario[clave])])

    contenido_tipos = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
    libro = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Respuestas" sheetId="1" r:id="rId1"/>
    <sheet name="Diccionario" sheetId="2" r:id="rId2"/>
  </sheets>
</workbook>"""
    libro_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
</Relationships>"""

    temporal = XLSX.with_suffix(".tmp")
    with ZipFile(temporal, "w", compression=ZIP_DEFLATED) as archivo:
        archivo.writestr("[Content_Types].xml", contenido_tipos)
        archivo.writestr("_rels/.rels", rels)
        archivo.writestr("xl/workbook.xml", libro)
        archivo.writestr("xl/_rels/workbook.xml.rels", libro_rels)
        archivo.writestr("xl/worksheets/sheet1.xml", hoja(tabla))
        archivo.writestr("xl/worksheets/sheet2.xml", hoja(dict_rows))
    temporal.replace(XLSX)


class Manejador(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_POST(self):
        ruta = self.path.split("?", 1)[0]
        if ruta not in {"/api/respuestas", "/api/procesar", "/api/informe"}:
            self.send_error(404)
            return
        longitud = int(self.headers.get("Content-Length", "0"))
        if longitud <= 0 or longitud > 100_000:
            self.send_error(413)
            return
        try:
            payload = json.loads(self.rfile.read(longitud).decode("utf-8"))
        except json.JSONDecodeError as exc:
            self._json(400, json.dumps({"ok": False, "error": str(exc)}).encode("utf-8"))
            return

        if ruta == "/api/respuestas":
            try:
                escribir_xlsx(payload)
            except (ValueError, TypeError, OSError) as exc:
                self._json(400, json.dumps({"ok": False, "error": str(exc)}).encode("utf-8"))
                return
            self._json(200, json.dumps({"ok": True, "archivo": XLSX.name}, ensure_ascii=False).encode("utf-8"))
            return

        try:
            escribir_xlsx(payload)
            if ruta == "/api/informe":
                from main import generar_informe_cuestionario
                resultado = generar_informe_cuestionario(payload)
            else:
                from main import procesar_resultado_cuestionario
                resultado = procesar_resultado_cuestionario(payload)
        except (ValueError, TypeError, OSError) as exc:
            self._json(400, json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False).encode("utf-8"))
            return
        except Exception as exc:
            from pydantic import ValidationError
            if isinstance(exc, ValidationError):
                self._json(400, json.dumps({"ok": False, "error": mensaje_modelo(exc)}, ensure_ascii=False).encode("utf-8"))
                return
            self._json(500, json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False).encode("utf-8"))
            return
        self._json(200, json.dumps(resultado, ensure_ascii=False).encode("utf-8"))

    def _json(self, codigo, cuerpo):
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)


def main():
    servidor = ThreadingHTTPServer(("127.0.0.1", PORT), Manejador)
    print(f"Cuestionario en http://127.0.0.1:{PORT}/cuestionario.html")
    print(f"Las respuestas se guardan en {XLSX}")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        servidor.server_close()


if __name__ == "__main__":
    main()
