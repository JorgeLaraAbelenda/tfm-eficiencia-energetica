from pydantic import ValidationError
from models import (
    ViviendaModel,
    TipoVivienda,
    ZonaClimatica,
    TipoVentana,
    SistemaCalefaccion
)

print("=== INICIANDO BATERIA DE PRUEBAS: models.py ===")

# Test 1: Instanciacion correcta con todos los datos validos
try:
    vivienda_valida = ViviendaModel(
        superficie_util_m2=90.0,
        año_construccion=1985,
        zona_climatica=ZonaClimatica.D,
        tipo_vivienda=TipoVivienda.PISO_INTERMEDIO,
        tipo_ventanas=TipoVentana.DOBLE_ALUMINIO,
        aislamiento_fachada=False,
        sistema_calefaccion=SistemaCalefaccion.GAS_NATURAL,
        factura_anual_estimada_eur=1080.0
    )
    assert vivienda_valida.zona_climatica == ZonaClimatica.D
    assert vivienda_valida.superficie_util_m2 == 90.0
    assert vivienda_valida.año_construccion == 1985
    print("\n[TEST 1 - OK] Creacion valida exitosa:")
    print(vivienda_valida.model_dump_json(indent=2))
except ValidationError as e:
    raise AssertionError("Una ficha valida no deberia fallar") from e

# Test 2: Control de campos obligatorios faltantes
try:
    ViviendaModel(
        superficie_util_m2=80.0,
        año_construccion=1995,
        zona_climatica=ZonaClimatica.C,
        tipo_vivienda=TipoVivienda.ATICO
        # Faltan 4 campos obligatorios
    )
    raise AssertionError("Se permitio crear una instancia incompleta.")
except ValidationError as e:
    assert len(e.errors()) == 4, e.errors()
    print(f"\n[TEST 2 - OK] Pydantic detecto correctamente los campos faltantes ({len(e.errors())} errores detectados).")
# Test 3: Control de restricciones numericas y rangos (gt=10, le=2026)
try:
    ViviendaModel(
        superficie_util_m2=5.0,        # Invalido: menor a 10
        año_construccion=2030,        # Invalido: mayor a 2026
        zona_climatica=ZonaClimatica.A,
        tipo_vivienda=TipoVivienda.BAJO,
        tipo_ventanas=TipoVentana.SIMPLE_METAL,
        aislamiento_fachada=False,
        sistema_calefaccion=SistemaCalefaccion.GAS_NATURAL,
        factura_anual_estimada_eur=-50.0  # Invalido: menor a 0
    )
    raise AssertionError("Se permitieron valores fuera de rango.")
except ValidationError as e:
    assert len(e.errors()) == 3, e.errors()
    print(f"\n[TEST 3 - OK] Pydantic freno valores fuera de rango ({len(e.errors())} errores de rango/valor detectados).")

print("\n=== TODAS LAS VALIDACIONES DE models.py HAN FINALIZADO ===")
