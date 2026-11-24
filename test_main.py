import base64

import informe_auditoria
import main
from main import datos_desde_detalle, generar_informe_cuestionario, procesar_resultado_cuestionario

print("=== PRUEBAS: main.py ===")

detalle = [
    {"variable": "ubicacion", "contestacion": "Jaén", "valor_asignado": "D"},
    {"variable": "superficie_util_m2", "contestacion": "45.7", "valor_asignado": 45.7},
    {"variable": "tipo_vivienda", "contestacion": "Ático", "valor_asignado": "atico"},
    {"variable": "año_construccion", "contestacion": "2010", "valor_asignado": 2010},
    {"variable": "aislamiento_fachada", "contestacion": "Sí", "valor_asignado": True},
    {"variable": "tipo_ventanas", "contestacion": "Baja emisividad", "valor_asignado": "doble_bajo_emisivo"},
    {"variable": "sistema_calefaccion", "contestacion": "Bomba", "valor_asignado": "bomba_calor_aerotermia"},
    {"variable": "factura_anual_estimada_eur", "contestacion": "1550", "valor_asignado": 1550},
]
datos = datos_desde_detalle(detalle)
assert datos["tipo_ventanas"] == "doble_pvc"
assert datos["tipo_vivienda"] == "atico"
assert datos["zona_climatica"] == "D"
assert datos["aislamiento_fachada"] is True
print("[OK] Las contestaciones de la pagina pasan al esquema del motor.")

filas = []
for numero, fila in enumerate(detalle, start=1):
    filas.append({
        "pregunta": numero,
        "contestacion": fila["contestacion"],
        "variable": fila["variable"],
        "valor_asignado": fila["valor_asignado"],
        "presumido": False,
    })
filas.append({
    "pregunta": 9,
    "contestacion": "Sí",
    "variable": "aislamiento_cubierta",
    "valor_asignado": True,
    "presumido": False,
})
payload = {"diccionario": {str(fila["pregunta"]): fila["contestacion"] for fila in filas}, "filas": filas}
resultado = procesar_resultado_cuestionario(payload)
assert resultado["ok"] is True
assert resultado["termico"]["resumen_inmueble"]["zona_climatica"] == "D"
assert resultado["termico"]["dictamen_ayudas_rd853"]["tramo_subvencion_concedido_pct"] == 0
print("[OK] El calculo del cuestionario no llama al modelo y deja el tramo en cero cuando el ahorro no llega al 30 %.")

main.consultar_y_redactar = lambda expediente: {
    "relatos": {"diagnostico": "Diagnostico de prueba.", "hoja_de_ruta": "Hoja de prueba."},
    "fragmentos": [],
}
informe_auditoria.html_a_pdf = lambda documento: b"%PDF-prueba"

informe = generar_informe_cuestionario(payload)
assert informe["ok"] is True
assert "Diagnostico de prueba." in informe["html"]
assert base64.b64decode(informe["pdf"]).startswith(b"%PDF-prueba")
print("[OK] El informe usa la redaccion devuelta por el modelo y convierte el HTML en PDF.")
print("=== TODAS LAS PRUEBAS DE main.py HAN FINALIZADO ===")
