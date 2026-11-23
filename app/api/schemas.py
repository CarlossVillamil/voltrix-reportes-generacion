"""Modelos Pydantic que reflejan los esquemas de openapi.yaml.

Los nombres de los campos son los del contrato (camelCase). Todos prohíben campos extra,
igual que el contrato (additionalProperties: false).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

Identificador = Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
Granularidad = Literal["hora", "dia", "mes"]
Nivel = Literal["planta", "activo"]
Modo = Literal["secuencial", "paralelo"]

PATRON_EQUIPO = r"^equipo-[1-7]$"


class Esquema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgregadoGeneracion(Esquema):
    plantaId: Identificador
    activoId: Identificador | None = None
    tipoActivo: str | None = None
    granularidad: Granularidad
    periodoInicio: AwareDatetime
    periodoFin: AwareDatetime
    energiaKwh: float = Field(ge=0)
    potenciaPromedioKw: float | None = None
    potenciaMaximaKw: float | None = None
    numeroLecturas: int = Field(ge=0)
    capacidadNominalKw: float | None = None
    factorPlanta: float | None = None
    generadoEn: AwareDatetime


class PaginaAgregados(Esquema):
    datos: list[AgregadoGeneracion]
    total: int = Field(ge=0)
    limit: int
    offset: int


class SolicitudGeneracion(Esquema):
    plantaIds: list[Identificador] | None = Field(default=None, description="Si se omite, todas las plantas.")
    desde: AwareDatetime
    hasta: AwareDatetime
    granularidad: Granularidad = "dia"
    nivel: Nivel = "planta"


class MetricasProcesamiento(Esquema):
    modo: Modo
    workers: int = Field(ge=1)
    elementos: int = Field(ge=0)
    duracionMs: int = Field(ge=0)


class ResultadoGeneracion(Esquema):
    generados: int = Field(ge=0)
    metricas: MetricasProcesamiento


class Salud(Esquema):
    estado: Literal["disponible", "no_disponible"]
    baseDatos: Literal["ok", "error"]
    version: str | None = None
    tiempoActivoSeg: int | None = Field(default=None, ge=0)
