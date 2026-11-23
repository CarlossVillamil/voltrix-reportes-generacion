"""Datos de la petición en curso, disponibles en todas las capas.

El middleware de la API los fija al recibir cada petición. Los clientes de los Equipos 1 y 2
(app/services) los leen para reenviar X-Request-Id y registrar en sus logs la misma traza:

    from app.contexto import request_id_actual
    cabeceras = {"X-Equipo-Consumidor": "equipo-4", "X-Request-Id": request_id_actual()}
"""

from __future__ import annotations

from contextvars import ContextVar

EQUIPO_PROPIO = "equipo-4"

_request_id: ContextVar[str] = ContextVar("request_id", default="-")
_equipo_consumidor: ContextVar[str] = ContextVar("equipo_consumidor", default="-")


def request_id_actual() -> str:
    return _request_id.get()


def equipo_consumidor_actual() -> str:
    return _equipo_consumidor.get()


def fijar(request_id: str, equipo_consumidor: str | None) -> None:
    _request_id.set(request_id)
    _equipo_consumidor.set(equipo_consumidor or "-")
