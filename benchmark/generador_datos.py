from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np

from app.services.modelos import ActivoInfo, SerieLecturas

ZONA_BOGOTA = ZoneInfo("America/Bogota")

TIPOS_ACTIVO = ("panel_solar", "turbina_eolica", "bateria")

_CAPACIDAD_KW_POR_TIPO = {
    "panel_solar": (150.0, 350.0),
    "turbina_eolica": (300.0, 800.0),
    "bateria": (50.0, 120.0),
}

_PREFIJO_TIPO = {
    "panel_solar": "PS",
    "turbina_eolica": "TE",
    "bateria": "BA",
}


@dataclass(frozen=True)
class ParametrosGenerador:
    num_plantas: int = 80
    activos_por_planta: int = 10
    dias: int = 7
    intervalo_minutos: int = 15
    fecha_inicio: datetime = datetime(2026, 11, 1, tzinfo=ZONA_BOGOTA)
    seed: int = 42


def _perfil_potencia(
    tipo_activo: str, horas_del_dia: np.ndarray, capacidad_kw: float, rng: np.random.Generator
) -> np.ndarray:
    ruido = rng.normal(loc=0.0, scale=0.05, size=horas_del_dia.shape[0])

    if tipo_activo == "panel_solar":
        angulo = np.clip((horas_del_dia - 6.0) / 12.0, 0.0, 1.0) * np.pi
        perfil = np.sin(angulo)
    elif tipo_activo == "turbina_eolica":
        perfil = 0.45 + 0.25 * np.sin(horas_del_dia / 3.0) + rng.normal(0.0, 0.15, size=horas_del_dia.shape[0])
    else:
        perfil = 0.5 + 0.5 * np.sin(horas_del_dia / 6.0)

    return np.clip(capacidad_kw * (perfil + ruido), 0.0, capacidad_kw * 1.05)


def generar_datos_sinteticos(parametros: ParametrosGenerador = ParametrosGenerador()) -> list[SerieLecturas]:
    rng = np.random.default_rng(parametros.seed)

    num_lecturas = int(parametros.dias * 24 * 60 / parametros.intervalo_minutos) + 1
    offsets_segundos = np.arange(num_lecturas) * parametros.intervalo_minutos * 60
    timestamps_epoch = parametros.fecha_inicio.timestamp() + offsets_segundos
    horas_del_dia = (offsets_segundos / 3600.0) % 24.0

    series = []
    for i_planta in range(parametros.num_plantas):
        planta_id = f"PL-{i_planta + 1:03d}"
        for i_activo in range(parametros.activos_por_planta):
            tipo_activo = TIPOS_ACTIVO[i_activo % len(TIPOS_ACTIVO)]
            minimo, maximo = _CAPACIDAD_KW_POR_TIPO[tipo_activo]
            capacidad_kw = float(rng.uniform(minimo, maximo))

            activo = ActivoInfo(
                activo_id=f"{planta_id}-{_PREFIJO_TIPO[tipo_activo]}-{i_activo + 1:02d}",
                planta_id=planta_id,
                tipo_activo=tipo_activo,
                capacidad_nominal_kw=capacidad_kw,
            )
            potencias_kw = _perfil_potencia(tipo_activo, horas_del_dia, capacidad_kw, rng)

            series.append(
                SerieLecturas(
                    activo=activo,
                    timestamps_epoch=timestamps_epoch.copy(),
                    potencias_kw=potencias_kw,
                )
            )
    return series
