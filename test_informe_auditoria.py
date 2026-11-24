from informe_auditoria import (
    _diagnostico_base,
    construir_informe,
    expediente_para_modelo,
)
from preprocessing import sanear_y_crear_vivienda
from thermal_engine import simular_rehabilitacion_rd853

print("=== PRUEBAS: informe_auditoria.py ===")

vivienda = sanear_y_crear_vivienda({
    "superficie_util_m2": 85.0,
    "año_construccion": 1974,
    "ubicacion": "Madrid",
    "tipo_vivienda": "piso_intermedio",
    "factura_anual_estimada_eur": 1200.0,
})
simulacion = simular_rehabilitacion_rd853(vivienda)
ficha = {
    "detalle": [
        {"pregunta": 1, "contestacion": "Madrid", "variable": "ubicacion", "valor_asignado": "D", "presumido": False},
        {"pregunta": 10, "contestacion": "No", "variable": "vivienda_habitual", "valor_asignado": "no", "presumido": False},
    ],
    "diccionario": {1: "Madrid"},
}

expediente = expediente_para_modelo(ficha, vivienda, simulacion)
assert expediente["zona"] == "D"
assert expediente["comunidad"] == "Comunidad de Madrid"
assert expediente["tramo_irpf"] == 0
assert expediente["perdidas_kwh"]["fachada"] > 0
print("[OK] El expediente reune la zona, la comunidad y las perdidas del motor.")

html_reserva = construir_informe(ficha, vivienda, simulacion)
assert _diagnostico_base(simulacion["inicial"]) in html_reserva
assert "No se han recuperado fragmentos" in html_reserva
print("[OK] Sin texto del modelo, el informe usa la redaccion de reserva.")

html_modelo = construir_informe(
    ficha,
    vivienda,
    simulacion,
    relatos={"diagnostico": "Texto del modelo.", "hoja_de_ruta": "Pasos del modelo."},
    fragmentos=[{
        "fuente": "BOE-A-2021-16233.pdf",
        "pagina": 30,
        "texto": "Articulo 30. Programa de ayuda.",
    }],
)
assert "Texto del modelo." in html_modelo
assert "Pasos del modelo." in html_modelo
assert "BOE-A-2021-16233" in html_modelo
assert "Por donde más calor se escapa" not in html_modelo
print("[OK] La sintesis coloca el texto y los fragmentos que le entrega el modelo.")
print("=== TODAS LAS PRUEBAS DE informe_auditoria.py HAN FINALIZADO ===")
