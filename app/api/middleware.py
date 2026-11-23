"""Middleware de trazabilidad: X-Request-Id y registro de cada petición.

- Si el consumidor envía un X-Request-Id con formato UUID se reutiliza; si no, se genera uno.
- Toda respuesta, también las de error, lleva X-Request-Id.
- Cada petición deja una línea de log con el request id y el X-Equipo-Consumidor; es la
  evidencia de consumo real entre equipos que pide el enunciado.
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request
from starlette.responses import Response

from app import contexto
from app.api.errores import respuesta_error

log = logging.getLogger("reportes.acceso")


def _request_id(valor: str | None) -> str:
    if valor:
        try:
            return str(uuid.UUID(valor))
        except ValueError:
            pass
    return str(uuid.uuid4())


def registrar_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def trazabilidad(request: Request, call_next) -> Response:
        request_id = _request_id(request.headers.get("X-Request-Id"))
        equipo = request.headers.get("X-Equipo-Consumidor")
        contexto.fijar(request_id, equipo)
        inicio = time.perf_counter()
        try:
            respuesta = await call_next(request)
        except Exception:
            log.exception("error no controlado requestId=%s", request_id)
            respuesta = respuesta_error(500, "ERROR_INTERNO", "Error interno del servicio.")
        respuesta.headers["X-Request-Id"] = request_id
        duracion_ms = (time.perf_counter() - inicio) * 1000
        if request.url.path != "/health":  # el healthcheck de Docker llama cada 15 s
            log.info(
                "requestId=%s equipo=%s %s %s -> %s %.0fms",
                request_id, equipo or "-", request.method, request.url.path,
                respuesta.status_code, duracion_ms,
            )
        return respuesta
