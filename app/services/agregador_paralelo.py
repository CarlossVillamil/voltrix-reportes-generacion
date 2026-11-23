from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

import numpy as np

from app.services.fusion import fusionar_resultados
from app.services.integracion import ResultadoParcial, integrar_particion
from app.services.modelos import SerieLecturas
from app.services.particionador import Particion, particionar_serie

_SIN_LECTURAS = np.empty(0, dtype=np.float64)


def _procesar_lote(
    series_lote: list[SerieLecturas],
    desde: datetime,
    hasta: datetime,
    granularidad: str,
) -> list[tuple[Particion, ResultadoParcial]]:
    """Se ejecuta dentro de un proceso worker: parte y agrega internamente
    todo el lote de activos que le tocó, para no mover miles de particiones
    diminutas a través de los procesos, solo los lotes de entrada y los
    resultados ya reducidos por partición."""
    resultados = []
    for serie in series_lote:
        for particion in particionar_serie(serie, desde, hasta, granularidad):
            resultado = integrar_particion(
                particion.timestamps_epoch, particion.potencias_kw, particion.n_reales
            )
            info_particion = Particion(
                activo=particion.activo,
                periodo_inicio=particion.periodo_inicio,
                periodo_fin=particion.periodo_fin,
                timestamps_epoch=_SIN_LECTURAS,
                potencias_kw=_SIN_LECTURAS,
                n_reales=particion.n_reales,
            )
            resultados.append((info_particion, resultado))
    return resultados


def _dividir_en_lotes(series: list[SerieLecturas], num_lotes: int) -> list[list[SerieLecturas]]:
    lotes: list[list[SerieLecturas]] = [[] for _ in range(num_lotes)]
    for indice, serie in enumerate(series):
        lotes[indice % num_lotes].append(serie)
    return [lote for lote in lotes if lote]


def calcular_paralelo(
    series: list[SerieLecturas],
    desde: datetime,
    hasta: datetime,
    granularidad: str,
    nivel: str,
    workers: int,
) -> list[dict]:
    if not series:
        return []

    lotes = _dividir_en_lotes(series, workers)

    with ProcessPoolExecutor(max_workers=workers) as executor:
        resultados_por_lote = executor.map(
            _procesar_lote,
            lotes,
            [desde] * len(lotes),
            [hasta] * len(lotes),
            [granularidad] * len(lotes),
        )
        parciales = [item for lote_resultado in resultados_por_lote for item in lote_resultado]

    return fusionar_resultados(parciales, granularidad, nivel)
