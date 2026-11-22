"""Repositorio de ejecucion_calculo: un registro por cada POST /reportes/generar.

Flujo esperado en la capa de servicios:
    ejecucion_id = ejecuciones.iniciar(sesion, ...)     # estado en_curso
    ... cálculo Map-Reduce ...
    agregados.guardar(sesion, resultado, ejecucion_id)
    ejecuciones.completar(sesion, ejecucion_id, ...)    # estado completado
o, si algo falla:
    ejecuciones.marcar_error(sesion, ejecucion_id, str(error))
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import EjecucionCalculo


def iniciar(
    sesion: Session,
    *,
    request_id: str,
    modo: str,
    workers: int,
    granularidad: str,
    nivel: str,
    desde: datetime,
    hasta: datetime,
    planta_ids: Sequence[str] | None = None,
    equipo_consumidor: str | None = None,
) -> int:
    """Registra el inicio de una ejecución y devuelve su id."""
    ejecucion = EjecucionCalculo(
        request_id=request_id,
        equipo_consumidor=equipo_consumidor,
        modo=modo,
        workers=workers,
        granularidad=granularidad,
        nivel=nivel,
        planta_ids=",".join(planta_ids) if planta_ids else None,
        desde=desde,
        hasta=hasta,
        estado="en_curso",
    )
    sesion.add(ejecucion)
    sesion.flush()  # asigna el id sin cerrar la transacción
    return ejecucion.id


def completar(sesion: Session, ejecucion_id: int, *, elementos: int, generados: int, duracion_ms: int) -> None:
    """Marca la ejecución como completada con sus métricas (MetricasProcesamiento)."""
    ejecucion = sesion.get(EjecucionCalculo, ejecucion_id)
    if ejecucion is None:
        raise LookupError(f"No existe la ejecución {ejecucion_id}")
    ejecucion.estado = "completado"
    ejecucion.elementos = elementos
    ejecucion.generados = generados
    ejecucion.duracion_ms = duracion_ms
    ejecucion.finalizado_en = func.now()
    sesion.flush()


def marcar_error(sesion: Session, ejecucion_id: int, mensaje: str) -> None:
    """Marca la ejecución como fallida y guarda el motivo."""
    ejecucion = sesion.get(EjecucionCalculo, ejecucion_id)
    if ejecucion is None:
        raise LookupError(f"No existe la ejecución {ejecucion_id}")
    ejecucion.estado = "error"
    ejecucion.mensaje_error = mensaje[:2000]
    ejecucion.finalizado_en = func.now()
    sesion.flush()


def ultimas(sesion: Session, limit: int = 20) -> list[dict[str, Any]]:
    """Últimas ejecuciones, para revisar benchmarks y depurar."""
    filas = sesion.scalars(
        select(EjecucionCalculo).order_by(EjecucionCalculo.iniciado_en.desc(), EjecucionCalculo.id.desc()).limit(limit)
    ).all()
    return [
        {
            "id": f.id,
            "requestId": f.request_id,
            "equipoConsumidor": f.equipo_consumidor,
            "modo": f.modo,
            "workers": f.workers,
            "estado": f.estado,
            "elementos": f.elementos,
            "generados": f.generados,
            "duracionMs": f.duracion_ms,
            "iniciadoEn": f.iniciado_en,
            "finalizadoEn": f.finalizado_en,
        }
        for f in filas
    ]
