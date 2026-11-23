from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from app.services.modelos import ActivoInfo, SerieLecturas

_DURACION_FIJA = {
    "hora": timedelta(hours=1),
    "dia": timedelta(days=1),
}


@dataclass(frozen=True)
class Particion:
    activo: ActivoInfo
    periodo_inicio: datetime
    periodo_fin: datetime
    timestamps_epoch: np.ndarray
    potencias_kw: np.ndarray
    n_reales: int


def _siguiente_periodo(inicio: datetime, granularidad: str) -> datetime:
    if granularidad == "mes":
        if inicio.month == 12:
            return inicio.replace(year=inicio.year + 1, month=1)
        return inicio.replace(month=inicio.month + 1)
    return inicio + _DURACION_FIJA[granularidad]


def _periodos(desde: datetime, hasta: datetime, granularidad: str) -> list[tuple[datetime, datetime]]:
    periodos = []
    inicio = desde
    while inicio < hasta:
        fin = min(_siguiente_periodo(inicio, granularidad), hasta)
        periodos.append((inicio, fin))
        inicio = fin
    return periodos


def particionar_serie(
    serie: SerieLecturas,
    desde: datetime,
    hasta: datetime,
    granularidad: str,
) -> list[Particion]:
    timestamps = serie.timestamps_epoch
    potencias = serie.potencias_kw

    particiones = []
    for periodo_inicio, periodo_fin in _periodos(desde, hasta, granularidad):
        inicio_epoch = periodo_inicio.timestamp()
        fin_epoch = periodo_fin.timestamp()
        a = int(np.searchsorted(timestamps, inicio_epoch, side="left"))
        b = int(np.searchsorted(timestamps, fin_epoch, side="left"))
        n_reales = b - a
        if n_reales == 0:
            continue

        if b < timestamps.shape[0]:
            ts_particion = np.concatenate([timestamps[a:b], timestamps[b : b + 1]])
            pot_particion = np.concatenate([potencias[a:b], potencias[b : b + 1]])
        else:
            ts_particion = timestamps[a:b]
            pot_particion = potencias[a:b]

        particiones.append(
            Particion(
                activo=serie.activo,
                periodo_inicio=periodo_inicio,
                periodo_fin=periodo_fin,
                timestamps_epoch=ts_particion,
                potencias_kw=pot_particion,
                n_reales=n_reales,
            )
        )
    return particiones
