"""Formato de error común (esquema Error de openapi.yaml) y manejadores de excepciones.

Toda respuesta de error tiene la forma:
    {"codigo": "SOLICITUD_INVALIDA", "mensaje": "...", "requestId": "...", "detalles": [...]}

Las capas de negocio y datos lanzan ErrorApi (o las funciones de abajo) y este módulo
se encarga de convertirlas en la respuesta HTTP correcta.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.contexto import request_id_actual

log = logging.getLogger("reportes.errores")


class ErrorApi(Exception):
    """Error con código del contrato. status es el código HTTP."""

    def __init__(
        self,
        status: int,
        codigo: str,
        mensaje: str,
        detalles: list[dict[str, str]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(mensaje)
        self.status = status
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalles = detalles
        self.headers = headers


def solicitud_invalida(campo: str, problema: str) -> ErrorApi:
    return ErrorApi(400, "SOLICITUD_INVALIDA", "La solicitud no cumple el contrato.",
                    [{"campo": campo, "problema": problema}])


def rango_excedido(max_dias: int) -> ErrorApi:
    return ErrorApi(400, "RANGO_EXCEDIDO", f"El rango desde-hasta supera {max_dias} días.",
                    [{"campo": "hasta", "problema": f"el rango admite como máximo {max_dias} días"}])


def sobrecarga(retry_after: int, mensaje: str = "El servicio está atendiendo el máximo de peticiones simultáneas.") -> ErrorApi:
    return ErrorApi(429, "SOBRECARGA", mensaje, headers={"Retry-After": str(max(1, retry_after))})


def no_disponible(mensaje: str = "No hay conexión con la base de datos.") -> ErrorApi:
    return ErrorApi(503, "NO_DISPONIBLE", mensaje)


def dependencia_fallida(equipo: str, problema: str, mensaje: str) -> ErrorApi:
    return ErrorApi(502, "DEPENDENCIA_FALLIDA", mensaje, [{"campo": equipo, "problema": problema}])


def cuerpo_error(codigo: str, mensaje: str, detalles: list[dict[str, str]] | None = None) -> dict[str, Any]:
    cuerpo: dict[str, Any] = {"codigo": codigo, "mensaje": mensaje, "requestId": request_id_actual()}
    if detalles:
        cuerpo["detalles"] = detalles
    return cuerpo


def respuesta_error(status: int, codigo: str, mensaje: str,
                    detalles: list[dict[str, str]] | None = None,
                    headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(cuerpo_error(codigo, mensaje, detalles), status_code=status, headers=headers)


# --------------------------- errores de validación ---------------------------

_UBICACION = {"query", "header", "path", "body", "cookie"}


def _campo(loc: tuple[Any, ...]) -> str:
    partes = list(loc)
    if partes and partes[0] in _UBICACION:
        origen = partes.pop(0)
        if origen == "header" and partes:
            return "-".join(p.capitalize() for p in str(partes[0]).split("-"))
    if not partes:
        return "cuerpo"
    campo = str(partes[0])
    for parte in partes[1:]:
        campo += f"[{parte}]" if isinstance(parte, int) else f".{parte}"
    return campo


def _problema(error: dict[str, Any]) -> str:
    tipo = error.get("type", "")
    ctx = error.get("ctx") or {}
    if tipo == "missing":
        return "es obligatorio"
    if tipo == "extra_forbidden":
        return "no está permitido en el contrato"
    if tipo.startswith("datetime") or tipo.startswith("timezone") or tipo.startswith("date_"):
        return "debe ser una fecha RFC 3339 con zona horaria"
    if tipo in ("enum", "literal_error"):
        esperados = str(ctx.get("expected", "")).replace("'", "").replace(" or ", ", ")
        return f"debe ser uno de: {esperados}"
    if tipo == "greater_than_equal":
        return f"debe ser mayor o igual que {ctx.get('ge')}"
    if tipo == "less_than_equal":
        return f"debe ser menor o igual que {ctx.get('le')}"
    if tipo in ("int_parsing", "int_type", "int_from_float"):
        return "debe ser un número entero"
    if tipo == "string_pattern_mismatch":
        return f"no cumple el formato {ctx.get('pattern', '')}".rstrip()
    if tipo in ("string_too_short", "string_too_long"):
        return "tiene una longitud inválida (1 a 64 caracteres)"
    if tipo == "json_invalid":
        return "el cuerpo no es JSON válido"
    if tipo == "value_error":
        return str(ctx.get("error", error.get("msg", "valor inválido")))
    return error.get("msg", "valor inválido")


def detalles_validacion(errores: list[dict[str, Any]]) -> list[dict[str, str]]:
    detalles = []
    for error in errores:
        detalle = {"campo": _campo(tuple(error.get("loc", ()))), "problema": _problema(error)}
        if detalle not in detalles:
            detalles.append(detalle)
    return detalles


# --------------------------------- manejadores --------------------------------

async def _error_api(_: Request, exc: ErrorApi) -> JSONResponse:
    return respuesta_error(exc.status, exc.codigo, exc.mensaje, exc.detalles, exc.headers)


async def _validacion(_: Request, exc: RequestValidationError) -> JSONResponse:
    detalles = detalles_validacion(list(exc.errors()))
    return respuesta_error(400, "SOLICITUD_INVALIDA", "La solicitud no cumple el contrato.", detalles)


async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 404:
        return respuesta_error(404, "NO_ENCONTRADO", "La ruta solicitada no existe.")
    if exc.status_code == 405:
        return respuesta_error(405, "SOLICITUD_INVALIDA", "Método HTTP no permitido en esta ruta.",
                               headers=dict(exc.headers or {}))
    return respuesta_error(exc.status_code, "SOLICITUD_INVALIDA", str(exc.detail))


async def _base_datos(_: Request, exc: Exception) -> JSONResponse:
    log.error("base de datos no disponible: %s", exc.__class__.__name__)
    return respuesta_error(503, "NO_DISPONIBLE", "No hay conexión con la base de datos.")


def registrar_manejadores(app: FastAPI) -> None:
    app.add_exception_handler(ErrorApi, _error_api)
    app.add_exception_handler(RequestValidationError, _validacion)
    app.add_exception_handler(StarletteHTTPException, _http)
    # Base de datos caída, conexión rechazada o pool lleno -> 503 NO_DISPONIBLE
    app.add_exception_handler(OperationalError, _base_datos)
    app.add_exception_handler(PoolTimeoutError, _base_datos)
