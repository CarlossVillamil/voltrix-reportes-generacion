from __future__ import annotations

from datetime import datetime

from app.services.fusion import fusionar_resultados
from app.services.integracion import integrar_particion
from app.services.modelos import SerieLecturas
from app.services.particionador import particionar_serie


def calcular_secuencial(
    series: list[SerieLecturas],
    desde: datetime,
    hasta: datetime,
    granularidad: str,
    nivel: str,
) -> list[dict]:
    parciales = []
    for serie in series:
        for particion in particionar_serie(serie, desde, hasta, granularidad):
            resultado = integrar_particion(
                particion.timestamps_epoch, particion.potencias_kw, particion.n_reales
            )
            parciales.append((particion, resultado))

    return fusionar_resultados(parciales, granularidad, nivel)
