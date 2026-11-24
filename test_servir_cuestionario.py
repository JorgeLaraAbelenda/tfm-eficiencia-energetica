import json
from tempfile import TemporaryDirectory
from pathlib import Path
from threading import Thread
from urllib.request import Request, urlopen
from zipfile import ZipFile

from pydantic import ValidationError

import servir_cuestionario
from servir_cuestionario import Manejador, escribir_xlsx, mensaje_modelo, xml_escape
from http.server import ThreadingHTTPServer

print("=== PRUEBAS: servir_cuestionario.py ===")

assert xml_escape('A & B <C>') == "A &amp; B &lt;C&gt;"
print("[OK] El texto del libro se escapa antes de guardarlo.")

try:
    from models import ViviendaModel
    ViviendaModel(superficie_util_m2=5, año_construccion=2030, factura_anual_estimada_eur=-1)
    raise AssertionError("La ficha invalida deberia fallar.")
except ValidationError as exc:
    texto = mensaje_modelo(exc)
    assert "1800 y 2026" in texto
    assert "mayor que 10" in texto
    assert "mayor o igual que 0" in texto
print("[OK] El error de validacion se traduce a un mensaje de la pagina.")

with TemporaryDirectory() as carpeta:
    servir_cuestionario.XLSX = Path(carpeta) / "cuestionario_vivienda.xlsx"
    escribir_xlsx({
        "filas": [{
            "pregunta": 1,
            "contestacion": "Jaén & norte",
            "variable": "ubicacion",
            "valor_asignado": "D",
            "presumido": False,
        }],
        "diccionario": {"1": "Jaén"},
    })
    with ZipFile(servir_cuestionario.XLSX) as libro:
        hoja = libro.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "Jaén &amp; norte" in hoja
    print("[OK] Las respuestas se guardan en el libro sin tocar el fichero real.")

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    hilo = Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    puerto = servidor.server_address[1]
    try:
        cuerpo = json.dumps({"filas": [], "diccionario": {}}).encode("utf-8")
        peticion = Request(
            f"http://127.0.0.1:{puerto}/api/respuestas",
            data=cuerpo,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(peticion) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
        assert datos["ok"] is True
        assert servir_cuestionario.XLSX.exists()
        print("[OK] La pagina puede enviar las respuestas al programa local.")
    finally:
        servidor.shutdown()

print("=== TODAS LAS PRUEBAS DE servir_cuestionario.py HAN FINALIZADO ===")
