from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.agregador_paralelo import calcular_paralelo
from app.services.agregador_secuencial import calcular_secuencial
from benchmark.generador_datos import ParametrosGenerador, generar_datos_sinteticos

ZONA_BOGOTA = ZoneInfo("America/Bogota")

TOLERANCIA_KWH = 1e-6


def _dataset_pequeno():
    parametros = ParametrosGenerador(num_plantas=5, activos_por_planta=4, dias=3, seed=7)
    return generar_datos_sinteticos(parametros)


def _por_clave(agregados: list[dict]) -> dict[tuple, dict]:
    return {(a["plantaId"], a["activoId"], a["periodoInicio"]): a for a in agregados}


@pytest.mark.parametrize("nivel", ["planta", "activo"])
@pytest.mark.parametrize("granularidad", ["hora", "dia"])
def test_secuencial_y_paralelo_coinciden(granularidad: str, nivel: str):
    series = _dataset_pequeno()
    desde = datetime(2026, 11, 1, tzinfo=ZONA_BOGOTA)
    hasta = datetime(2026, 11, 3, tzinfo=ZONA_BOGOTA)

    agregados_secuencial = calcular_secuencial(series, desde, hasta, granularidad, nivel)
    agregados_paralelo = calcular_paralelo(series, desde, hasta, granularidad, nivel, workers=3)

    assert len(agregados_secuencial) == len(agregados_paralelo)
    assert len(agregados_secuencial) > 0

    por_clave_secuencial = _por_clave(agregados_secuencial)
    por_clave_paralelo = _por_clave(agregados_paralelo)
    assert por_clave_secuencial.keys() == por_clave_paralelo.keys()

    for clave, agregado_secuencial in por_clave_secuencial.items():
        agregado_paralelo = por_clave_paralelo[clave]
        assert agregado_secuencial["numeroLecturas"] == agregado_paralelo["numeroLecturas"]
        assert agregado_secuencial["energiaKwh"] == pytest.approx(
            agregado_paralelo["energiaKwh"], abs=TOLERANCIA_KWH
        )
        assert agregado_secuencial["potenciaPromedioKw"] == pytest.approx(
            agregado_paralelo["potenciaPromedioKw"], abs=TOLERANCIA_KWH
        )
        assert agregado_secuencial["potenciaMaximaKw"] == agregado_paralelo["potenciaMaximaKw"]


def test_particion_vacia_no_rompe_el_paralelo():
    series = _dataset_pequeno()
    desde = datetime(2030, 1, 1, tzinfo=ZONA_BOGOTA)
    hasta = datetime(2030, 1, 2, tzinfo=ZONA_BOGOTA)

    agregados = calcular_paralelo(series, desde, hasta, "dia", "planta", workers=2)

    assert agregados == []
