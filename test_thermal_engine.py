from preprocessing import sanear_y_crear_vivienda
from thermal_engine import simular_rehabilitacion_rd853

print("=== PRUEBA DEL MOTOR TERMICO (thermal_engine.py) ===")

# Simulamos la auditoría de un piso de 1974 en Madrid
caso = {
    "superficie_util_m2": 85.0,
    "año_construccion": 1974,
    "ubicacion": "Madrid",
    "tipo_vivienda": "piso_intermedio",
    "factura_anual_estimada_eur": 1200.0
}

vivienda = sanear_y_crear_vivienda(caso)
resultado = simular_rehabilitacion_rd853(vivienda)

inicial = resultado["inicial"]
propuesto = resultado["propuesto"]
ep0 = inicial["energia_primaria_nren_kwh_m2"]
ep1 = propuesto["energia_primaria_nren_kwh_m2"]
bruto = (ep0 - ep1) / ep0 * 100.0
esperado = round(bruto, 2)

assert inicial["grados_dia"] == 2100
assert inicial["cubierta_m2"] == 0.0
assert inicial["u_muro"] == 1.80
assert inicial["u_ventanas"] == 5.7
assert inicial["rendimiento"] == 0.85
assert propuesto["u_muro"] == 0.41
assert propuesto["u_ventanas"] == 1.3
assert propuesto["rendimiento"] == 3.8
assert propuesto["factor_paso"] == 1.954
assert resultado["porcentaje_ahorro_ep"] == esperado
assert resultado["porcentaje_ahorro_ep"] == 86.39
assert resultado["subvencion_rd853_porcentaje"] == 80
assert resultado["ayuda_maxima_eur"] == 18800.0
assert resultado["ahorro_factura_anual_eur"] == round(bruto / 100.0 * 1200.0, 2)

print(f"Demanda inicial: {inicial['demanda_especifica_kwh_m2']} kWh/m2 año")
print(f"Consumo Energia Primaria Inicial: {ep0} kWh/m2 año")
print(f"Consumo Energia Primaria Tras Reforma: {ep1} kWh/m2 año")
print(f"Ahorro energetico obtenido: {resultado['porcentaje_ahorro_ep']} %")
print(f"Tramo de subvencion RD 853/2021: {resultado['subvencion_rd853_porcentaje']} % (Max: {resultado['ayuda_maxima_eur']} EUR)")
print(f"Ahorro económico estimado: {resultado['ahorro_factura_anual_eur']} EUR/año")
print("[OK] El balance, el ahorro y el tramo coinciden con las formulas del motor.")
