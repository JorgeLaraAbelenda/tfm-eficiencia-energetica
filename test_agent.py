import agent
from agent import _leer_json, consultar_y_redactar

print("=== PRUEBAS: agent.py ===")

leido = _leer_json('```json\n{"diagnostico": "Aire", "ayudas_complementarias": "Ninguna", "hoja_de_ruta": "Certificado"}\n```')
assert leido == {
    "diagnostico": "Aire",
    "ayudas_complementarias": "Ninguna",
    "hoja_de_ruta": "Certificado",
}
assert _leer_json("sin json") == {}
print("[OK] El JSON se lee dentro de una respuesta con marcas.")

fragmento = {
    "fuente": "BOE-A-2021-16233.pdf",
    "pagina": 30,
    "texto": "Articulo 30. Programa de ayuda a nivel de edificio.",
    "distancia": 0.12,
}
agent.asegurar_indice = lambda: None
agent.recuperar = lambda consulta, k=6: [fragmento]
llamadas = {"n": 0}

def falso_pedir(contenido, herramienta, instruccion):
    llamadas["n"] += 1
    texto = herramienta("ayudas rehabilitacion energetica")
    assert "BOE-A-2021-16233" in texto

    class Respuesta:
        text = '{"diagnostico": "Por la ventilacion.", "ayudas_complementarias": "Sin tramo.", "hoja_de_ruta": "Registrar el certificado."}'

    return Respuesta()

agent._pedir = falso_pedir
paquete = consultar_y_redactar({"comunidad": "Andalucía", "perdidas_kwh": {}})
assert llamadas["n"] == 1
assert paquete["relatos"]["diagnostico"] == "Por la ventilacion."
assert paquete["fragmentos"] == [fragmento]
print("[OK] El modelo consulta la base y la redaccion conserva los fragmentos.")

agent.recuperar = lambda consulta, k=6: []

def pedir_vacio(contenido, herramienta, instruccion):
    llamadas["n"] += 1
    herramienta("otra consulta")

    class Respuesta:
        text = "no es json"

    return Respuesta()

agent._pedir = pedir_vacio
vacio = consultar_y_redactar({"comunidad": "Andalucía"})
assert llamadas["n"] == 3
assert vacio["relatos"] == {}
assert vacio["fragmentos"] == []
print("[OK] Si la consulta no devuelve fragmentos, se reintenta y la redaccion queda vacia.")
print("=== TODAS LAS PRUEBAS DE agent.py HAN FINALIZADO ===")
