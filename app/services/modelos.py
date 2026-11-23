from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ActivoInfo:
    activo_id: str
    planta_id: str
    tipo_activo: str
    capacidad_nominal_kw: float


@dataclass(frozen=True)
class SerieLecturas:
    """Lecturas de un único activo, ordenadas por tiempo."""

    activo: ActivoInfo
    timestamps_epoch: np.ndarray
    potencias_kw: np.ndarray
