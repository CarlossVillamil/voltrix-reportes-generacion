from __future__ import annotations

import time
from datetime import datetime

from app.services.agregador_paralelo import calcular_paralelo
from app.services.agregador_secuencial import calcular_secuencial
from app.services.modelos import SerieLecturas

MODOS_VALIDOS = ("secuencial", "paralelo")


def calcular(
    series: list[SerieLecturas],
    desde: datetime,
    hasta: datetime,
    granularidad: str,
    nivel: str,
    modo: str,
    workers: int | None = None,
) -> tuple[list[dict], dict]:
    if modo not in MODOS_VALIDOS:
        raise ValueError(f"modo debe ser uno de {MODOS_VALIDOS}, recibido: {modo}")

    inicio = time.perf_counter()
    if modo == "secuencial":
        agregados = calcular_secuencial(series, desde, hasta, granularidad, nivel)
        workers_usados = 1
    else:
        workers_usados = workers or 1
        agregados = calcular_paralelo(series, desde, hasta, granularidad, nivel, workers_usados)
    duracion_ms = int((time.perf_counter() - inicio) * 1000)

    elementos = sum(agregado["numeroLecturas"] for agregado in agregados)
    metricas = {
        "modo": modo,
        "workers": workers_usados,
        "elementos": elementos,
        "duracionMs": duracion_ms,
    }
    return agregados, metricas
