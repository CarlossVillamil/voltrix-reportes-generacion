"""GET /health y GET /openapi.yaml (secciones COMÚN del contrato)."""

from __future__ import annotations

import time

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from app.api.errores import respuesta_error
from app.api.schemas import Salud
from app.config import config
from app.repositories import database

router = APIRouter(tags=["Operación"])

_INICIO = time.monotonic()


@router.get("/health", response_model=Salud, responses={503: {"model": Salud}})
def consultar_salud():
    # No exige X-Equipo-Consumidor ni llama a otros equipos: solo comprueba la base de datos
    base_ok = database.verificar_conexion()
    salud = Salud(
        estado="disponible" if base_ok else "no_disponible",
        baseDatos="ok" if base_ok else "error",
        version=config.version,
        tiempoActivoSeg=int(time.monotonic() - _INICIO),
    )
    return JSONResponse(salud.model_dump(), status_code=200 if base_ok else 503)


@router.get("/openapi.yaml", response_class=FileResponse)
def obtener_contrato():
    if not config.ruta_openapi.is_file():
        return respuesta_error(503, "NO_DISPONIBLE", "El contrato no está disponible en el servicio.")
    return FileResponse(config.ruta_openapi, media_type="application/yaml")
