import json
import re
from pathlib import Path

print("=== PRUEBAS: municipios_ine.js ===")

texto = Path("municipios_ine.js").read_text(encoding="utf-8")
anio = re.search(r"const AÑO_PADRON = (\d+);", texto)
assert anio and anio.group(1) == "2025"
_, poblacion_bruta = texto.split("const POBLACION_INE = ", 1)
poblacion_bruta, nombres_brutos = poblacion_bruta.split("const NOMBRE_INE = ", 1)
poblacion = json.loads(poblacion_bruta.strip().rstrip(";"))
nombres = json.loads(nombres_brutos.strip().rstrip(";"))

assert set(poblacion) == set(nombres)
assert len(poblacion) > 8000
assert poblacion["jaen|jaen"] == 112235
assert nombres["jaen|jaen"] == "Jaén"
assert any(habitantes <= 5000 for habitantes in poblacion.values())
assert any(habitantes > 5000 for habitantes in poblacion.values())
print(f"[OK] Padron de {anio.group(1)} con {len(poblacion)} municipios, Jaen incluido.")
print("=== TODAS LAS PRUEBAS DE municipios_ine.js HAN FINALIZADO ===")
