from preprocessing import sanear_y_crear_vivienda
from models import ZonaClimatica, TipoVentana, SistemaCalefaccion

print("=== INICIANDO PRUEBAS: preprocessing.py ===")

# Caso 1: Entrada mínima (usuario sin conocimientos técnicos)
# Solo indica superficie, año, tipología y ciudad con tildes/mayúsculas
caso_minimo = {
    "superficie_util_m2": 85.0,
    "año_construccion": 1975,       # Pre-1980: debe inferir sin aislamiento y ventana simple
    "ubicacion": "Málaga",          # Con tilde: debe inferir Zona A
    "tipo_vivienda": "piso_intermedio"
}

v1 = sanear_y_crear_vivienda(caso_minimo)
print("\n[CASO 1 - ENTRADA MINIMA INFERIDA]")
print(f"Zona inferida: {v1.zona_climatica} (Esperado: ZonaClimatica.A)")
print(f"Aislamiento fachada: {v1.aislamiento_fachada} (Esperado: False)")
print(f"Tipo ventana: {v1.tipo_ventanas} (Esperado: TipoVentana.SIMPLE_METAL)")
print(f"Sistema calefaccion: {v1.sistema_calefaccion} (Esperado: SistemaCalefaccion.GAS_NATURAL)")
print(f"Factura anual estimada: {v1.factura_anual_estimada_eur} EUR (Esperado: {85.0 * 12.0} EUR)")

assert v1.zona_climatica == ZonaClimatica.A, "Error en zona climática"
assert v1.aislamiento_fachada is False, "Error en aislamiento"
assert v1.tipo_ventanas == TipoVentana.SIMPLE_METAL, "Error en ventanas"
assert v1.sistema_calefaccion == SistemaCalefaccion.GAS_NATURAL, "Error en calefaccion"
assert v1.factura_anual_estimada_eur == 1020.0, "Error en estimación de factura"
print("[CASO 1 - OK]")

# Caso 2: Edificio posterior a 2006 (CTE) con datos explícitos del usuario
# Debe respetar los datos explícitos sin sobreescribirlos con las inferencias
caso_moderno = {
    "superficie_util_m2": 120.0,
    "año_construccion": 2012,
    "ubicacion": "Burgos",          # Zona E
    "tipo_vivienda": "unifamiliar_aislada",
    "sistema_calefaccion": "bomba_calor_aerotermia",
    "factura_anual_estimada_eur": 650.0
}

v2 = sanear_y_crear_vivienda(caso_moderno)
print("\n[CASO 2 - EDIFICIO MODERNO CON DATOS PARCIALES]")
print(f"Zona inferida: {v2.zona_climatica} (Esperado: ZonaClimatica.E)")
print(f"Aislamiento fachada: {v2.aislamiento_fachada} (Esperado: True, por ser post-2006)")
print(f"Tipo ventana: {v2.tipo_ventanas} (Esperado: TipoVentana.DOBLE_PVC, por ser post-2006)")
print(f"Sistema calefaccion respetado: {v2.sistema_calefaccion} (Esperado: SistemaCalefaccion.BOMBA_CALOR_AEROTERMIA)")
print(f"Factura real respetada: {v2.factura_anual_estimada_eur} EUR (Esperado: 650.0 EUR)")

assert v2.zona_climatica == ZonaClimatica.E, "Error en zona climática"
assert v2.aislamiento_fachada is True, "Error en inferencia de aislamiento CTE"
assert v2.tipo_ventanas == TipoVentana.DOBLE_PVC, "Error en ventanas posteriores a 2006"
assert v2.sistema_calefaccion == SistemaCalefaccion.BOMBA_CALOR_AEROTERMIA, "Se sobreescribió el sistema"
assert v2.factura_anual_estimada_eur == 650.0, "Se sobreescribió la factura real"
print("[CASO 2 - OK]")

caso_intermedio = {
    "superficie_util_m2": 70.0,
    "año_construccion": 1990,
    "ubicacion": "Madrid",
    "tipo_vivienda": "piso_intermedio",
}
v3 = sanear_y_crear_vivienda(caso_intermedio)
assert v3.zona_climatica == ZonaClimatica.D
assert v3.aislamiento_fachada is False
assert v3.tipo_ventanas == TipoVentana.DOBLE_ALUMINIO
assert v3.factura_anual_estimada_eur == 840.0
print("[CASO 3 - OK] Entre 1980 y 2006: sin aislamiento y doble acristalamiento.")

print("\n=== TODAS LAS PRUEBAS DE preprocessing.py HAN FINALIZADO EXITOSAMENTE ===")
