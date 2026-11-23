from __future__ import annotations

from dataclasses import dataclass

import numpy as np

SEGUNDOS_POR_HORA = 3600.0


@dataclass(frozen=True)
class ResultadoParcial:
    suma_potencias_kw: float
    numero_lecturas: int
    potencia_minima_kw: float
    potencia_maxima_kw: float
    energia_kwh: float


def integrar_particion(
    timestamps_epoch: np.ndarray,
    potencias_kw: np.ndarray,
    n_reales: int,
) -> ResultadoParcial:
    """timestamps_epoch/potencias_kw van ordenados y pueden incluir, al final,
    una lectura de borde (la primera del periodo siguiente) que solo cierra la
    integral sin contarse en los estadísticos; n_reales marca ese límite."""
    if n_reales == 0:
        return ResultadoParcial(0.0, 0, 0.0, 0.0, 0.0)

    reales = potencias_kw[:n_reales]

    if timestamps_epoch.shape[0] < 2:
        energia_kwh = 0.0
    else:
        delta_horas = np.diff(timestamps_epoch) / SEGUNDOS_POR_HORA
        promedios_trapecio = (potencias_kw[:-1] + potencias_kw[1:]) / 2.0
        energia_kwh = float(np.sum(promedios_trapecio * delta_horas))

    return ResultadoParcial(
        suma_potencias_kw=float(np.sum(reales)),
        numero_lecturas=int(n_reales),
        potencia_minima_kw=float(np.min(reales)),
        potencia_maxima_kw=float(np.max(reales)),
        energia_kwh=energia_kwh,
    )
