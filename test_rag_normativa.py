from rag_normativa import (
    _identificador_norma,
    _trocear,
    consulta_desde_diccionario,
    fragmentos_a_contexto,
)

print("=== PRUEBAS: rag_normativa.py ===")

assert _trocear("corto") == []
largo = ("Frase uno. " * 200).strip()
piezas = _trocear(largo)
assert len(piezas) >= 2
assert all(len(pieza) >= 80 for pieza in piezas)
print("[OK] El troceo descarta textos minimos y parte los largos.")

assert _identificador_norma("BOE-A-2021-16233-consolidado.pdf") == "BOE-A-2021-16233"
assert "Documento Básico HE" in _identificador_norma("DBHE.pdf")
print("[OK] El identificador sale del codigo del BOE o del documento basico.")

consulta = consulta_desde_diccionario({
    "detalle": [{
        "pregunta": 1,
        "variable": "ubicacion",
        "contestacion": "Jaén",
        "valor_asignado": "D",
    }]
})
assert "Jaén" in consulta and "ubicacion" in consulta
print("[OK] La consulta incluye la contestacion de la vivienda.")

contexto = fragmentos_a_contexto([{
    "fuente": "BOE-A-2021-16233.pdf",
    "pagina": 30,
    "texto": "Articulo 30. Programa de ayuda.",
}])
assert contexto.startswith("[1] BOE-A-2021-16233")
assert "Articulo 30" in contexto
print("[OK] El contexto numera el fragmento con el identificador de la norma.")
print("=== TODAS LAS PRUEBAS DE rag_normativa.py HAN FINALIZADO ===")
