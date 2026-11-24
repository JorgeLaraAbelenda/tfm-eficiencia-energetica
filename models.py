from enum import Enum
from pydantic import BaseModel, Field

class TipoVivienda(str, Enum):
    PISO_INTERMEDIO = "piso_intermedio"
    ATICO = "atico"
    BAJO = "bajo"
    UNIFAMILIAR_AISLADA = "unifamiliar_aislada"
    UNIFAMILIAR_ADOSADA = "unifamiliar_adosada"

class ZonaClimatica(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"

class TipoVentana(str, Enum):
    SIMPLE_METAL = "simple_metal"
    DOBLE_ALUMINIO = "doble_aluminio"
    DOBLE_PVC = "doble_pvc"
    TRIPLE_BAJO_EMISIVO = "triple_bajo_emisivo"

class SistemaCalefaccion(str, Enum):
    GAS_NATURAL = "gas_natural"
    GASOLEO = "gasoleo"
    ELECTRICO_EFECTO_JOULE = "electrico_efecto_joule"
    BOMBA_CALOR_AEROTERMIA = "bomba_calor_aerotermia"
    BIOMASA = "biomasa"

class ViviendaModel(BaseModel):
    """Modelo estructurado con todos los atributos obligatorios para la auditoria."""
    superficie_util_m2: float = Field(..., gt=10, lt=1000, description="Superficie util habitable en m2")
    año_construccion: int = Field(..., ge=1800, le=2026, description="Año de construcción del edificio")
    zona_climatica: ZonaClimatica = Field(..., description="Zona climatica CTE (A, B, C, D o E)")
    tipo_vivienda: TipoVivienda = Field(..., description="Tipologia constructiva de la vivienda")
    tipo_ventanas: TipoVentana = Field(..., description="Tipo de carpinteria y acristalamiento actual")
    aislamiento_fachada: bool = Field(..., description="Existencia de aislamiento termico en la envolvente")
    sistema_calefaccion: SistemaCalefaccion = Field(..., description="Instalacion termica principal")
    factura_anual_estimada_eur: float = Field(..., ge=0, description="Gasto anual energetico estimado en euros")
