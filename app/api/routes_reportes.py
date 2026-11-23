"""GET /reportes/generacion y POST /reportes/generar."""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Header, Query
from pydantic import AwareDatetime

from app.api.errores import rango_excedido, solicitud_invalida
from app.api.schemas import (
    PATRON_EQUIPO,
    Granularidad,
    Identificador,
    Modo,
    PaginaAgregados,
    ResultadoGeneracion,
    SolicitudGeneracion,
)
from app.config import config
from app.contexto import request_id_actual
from app.repositories import agregados
from app.repositories.database import transaccion
from app.services import generacion

router = APIRouter(prefix="/reportes", tags=["Reportes"])

EquipoConsumidor = Annotated[str | None, Header(alias="X-Equipo-Consumidor", pattern=PATRON_EQUIPO)]


@router.get("/generacion", response_model=PaginaAgregados)
def consultar_reportes_generacion(
    _equipo: EquipoConsumidor = None,
    plantaId: Annotated[Identificador | None, Query()] = None,
    activoId: Annotated[Identificador | None, Query()] = None,
    desde: Annotated[AwareDatetime | None, Query(description="Inclusivo, RFC 3339 con zona horaria")] = None,
    hasta: Annotated[AwareDatetime | None, Query(description="Exclusivo, RFC 3339 con zona horaria")] = None,
    granularidad: Annotated[Granularidad, Query()] = "dia",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginaAgregados:
    if desde is not None and hasta is not None and hasta <= desde:
        raise solicitud_invalida("hasta", "debe ser posterior a desde")

    # La sesión se abre aquí y no con Depends: FastAPI resuelve las dependencias antes de
    # validar los parámetros, y una petición inválida no debe tocar la base de datos.
    with transaccion() as sesion:
        datos, total = agregados.consultar(
            sesion,
            planta_id=plantaId,
            activo_id=activoId,
            desde=desde,
            hasta=hasta,
            granularidad=granularidad,
            limit=limit,
            offset=offset,
        )
    # Página vacía con 200 si no hay agregados para el filtro (contrato)
    return PaginaAgregados(datos=datos, total=total, limit=limit, offset=offset)


@router.post("/generar", response_model=ResultadoGeneracion, tags=["Procesamiento"])
def generar_reportes(
    solicitud: SolicitudGeneracion,
    equipo: EquipoConsumidor = None,
    modo: Annotated[Modo, Query()] = "paralelo",
    workers: Annotated[int | None, Query(ge=1, le=64)] = None,
) -> ResultadoGeneracion:
    if solicitud.hasta <= solicitud.desde:
        raise solicitud_invalida("hasta", "debe ser posterior a desde")
    if solicitud.hasta - solicitud.desde > timedelta(days=config.max_dias_rango):
        raise rango_excedido(config.max_dias_rango)

    resultado = generacion.generar(
        solicitud.model_dump(),
        modo=modo,
        workers=workers,
        request_id=request_id_actual(),
        equipo_consumidor=equipo,
    )
    return ResultadoGeneracion.model_validate(resultado)
