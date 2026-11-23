"""Punto de entrada de la API (uvicorn app.main:app)."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from app.api.errores import registrar_manejadores
from app.api.middleware import registrar_middleware
from app.config import config

logging.basicConfig(
    level=config.nivel_log,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def crear_app() -> FastAPI:
    # El contrato oficial es openapi.yaml (GET /openapi.yaml). Se desactivan /docs y
    # /openapi.json de FastAPI para no publicar un segundo contrato distinto.
    app = FastAPI(
        title="Voltrix Energy · Reportes de Generación",
        version=config.version,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    registrar_manejadores(app)
    registrar_middleware(app)
    return app


app = crear_app()
