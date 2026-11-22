"""Repositorio de agregado_generacion.

Los agregados entran y salen como diccionarios con los nombres de campo del contrato
(esquema AgregadoGeneracion de openapi.yaml: plantaId, energiaKwh, periodoInicio...),
así la capa de presentación y el motor de cálculo no ven nombres de columnas.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .models import AgregadoGeneracion

# Campo del contrato -> columna de la tabla
CAMPOS: dict[str, str] = {
    "plantaId": "planta_id",
    "activoId": "activo_id",
    "tipoActivo": "tipo_activo",
    "granularidad": "granularidad",
    "periodoInicio": "periodo_inicio",
    "periodoFin": "periodo_fin",
    "energiaKwh": "energia_kwh",
    "potenciaPromedioKw": "potencia_promedio_kw",
    "potenciaMaximaKw": "potencia_maxima_kw",
    "numeroLecturas": "numero_lecturas",
    "capacidadNominalKw": "capacidad_nominal_kw",
    "factorPlanta": "factor_planta",
    "generadoEn": "generado_en",
}
OBLIGATORIOS = ("plantaId", "granularidad", "periodoInicio", "periodoFin", "energiaKwh", "numeroLecturas")


def a_contrato(agregado: AgregadoGeneracion) -> dict[str, Any]:
    """Convierte una fila al diccionario del esquema AgregadoGeneracion."""
    return {campo: getattr(agregado, columna) for campo, columna in CAMPOS.items()}


def consultar(
    sesion: Session,
    *,
    planta_id: str | None = None,
    activo_id: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    granularidad: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Consulta paginada para GET /reportes/generacion.

    - Sin activo_id devuelve los agregados de planta (activo_id NULL); con activo_id, los del activo.
    - desde es inclusivo y hasta exclusivo, sobre periodo_inicio.
    Devuelve (página de agregados, total sin paginar).
    """
    filtros = []
    if planta_id is not None:
        filtros.append(AgregadoGeneracion.planta_id == planta_id)
    if activo_id is None:
        filtros.append(AgregadoGeneracion.activo_id.is_(None))
    else:
        filtros.append(AgregadoGeneracion.activo_id == activo_id)
    if desde is not None:
        filtros.append(AgregadoGeneracion.periodo_inicio >= desde)
    if hasta is not None:
        filtros.append(AgregadoGeneracion.periodo_inicio < hasta)
    if granularidad is not None:
        filtros.append(AgregadoGeneracion.granularidad == granularidad)

    total = sesion.scalar(select(func.count()).select_from(AgregadoGeneracion).where(*filtros)) or 0

    filas = sesion.scalars(
        select(AgregadoGeneracion)
        .where(*filtros)
        .order_by(
            AgregadoGeneracion.planta_id,
            AgregadoGeneracion.activo_id.nulls_first(),
            AgregadoGeneracion.periodo_inicio,
        )
        .limit(limit)
        .offset(offset)
    ).all()

    return [a_contrato(fila) for fila in filas], total


def guardar(
    sesion: Session,
    agregados: Iterable[Mapping[str, Any]],
    ejecucion_id: int | None = None,
) -> int:
    """Guarda agregados reemplazando los que ya existan para el mismo
    (planta, activo, granularidad, periodo). Devuelve cuántos se guardaron.

    Cada agregado es un diccionario con los campos del contrato; generadoEn es opcional
    (por defecto, la hora actual de la base de datos).
    """
    ahora = datetime.now(timezone.utc)
    filas = []
    for agregado in agregados:
        faltan = [campo for campo in OBLIGATORIOS if agregado.get(campo) is None]
        if faltan:
            raise ValueError(f"Faltan campos en el agregado: {', '.join(faltan)}")
        # Todas las filas con las mismas columnas, para un solo INSERT de varias filas
        fila = {columna: agregado.get(campo) for campo, columna in CAMPOS.items()}
        fila["generado_en"] = fila["generado_en"] or ahora
        fila["ejecucion_id"] = ejecucion_id
        filas.append(fila)

    if not filas:
        return 0

    clave = ("planta_id", "activo_id", "granularidad", "periodo_inicio")
    sentencia = insert(AgregadoGeneracion).values(filas)
    sentencia = sentencia.on_conflict_do_update(
        constraint="uq_agregado_periodo",
        set_={columna: sentencia.excluded[columna] for columna in filas[0] if columna not in clave},
    )
    sesion.execute(sentencia)
    return len(filas)
