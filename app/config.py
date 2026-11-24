"""Configuración del servicio, leída de variables de entorno.

Las variables de la base de datos (DATABASE_URL, DB_POOL_SIZE) las lee directamente
app/repositories/database.py; aquí solo están las que usa el resto del servicio.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _entero(nombre: str, por_defecto: int) -> int:
    valor = os.getenv(nombre)
    return int(valor) if valor else por_defecto


def _decimal(nombre: str, por_defecto: float) -> float:
    valor = os.getenv(nombre)
    return float(valor) if valor else por_defecto


def _booleano(nombre: str, por_defecto: bool = False) -> bool:
    valor = os.getenv(nombre)
    if valor is None or not valor.strip():
        return por_defecto
    return valor.strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


@dataclass(frozen=True)
class Configuracion:
    version: str = field(default_factory=lambda: os.getenv("APP_VERSION", "1.0.0"))
    nivel_log: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper())

    # Contrato que se sirve en GET /openapi.yaml (en la imagen queda en /srv/openapi.yaml)
    ruta_openapi: Path = field(default_factory=lambda: Path(os.getenv("OPENAPI_PATH", RAIZ / "openapi.yaml")))

    # Servicios de otros equipos (los usan los clientes de app/services)
    inventario_url: str | None = field(default_factory=lambda: os.getenv("INVENTARIO_URL") or None)
    telemetria_url: str | None = field(default_factory=lambda: os.getenv("TELEMETRIA_URL") or None)

    # MODO_SIMULADO=true: los clientes devuelven datos sintéticos y no hacen ninguna llamada HTTP.
    # Sirve para trabajar mientras los Equipos 1 y 2 no tienen su servicio disponible.
    modo_simulado: bool = field(default_factory=lambda: _booleano("MODO_SIMULADO"))
    # Tiempo máximo (segundos) de cada llamada a otro equipo y reintentos de conexión
    timeout_clientes_s: float = field(default_factory=lambda: _decimal("CLIENTES_TIMEOUT_S", 10.0))
    reintentos_clientes: int = field(default_factory=lambda: _entero("CLIENTES_REINTENTOS", 2))

    # Procesamiento: en EC2 (1 GiB) docker-compose fija MAX_WORKERS=2
    max_workers: int = field(default_factory=lambda: _entero("MAX_WORKERS", os.cpu_count() or 1))

    # Límite del rango desde-hasta de POST /reportes/generar (error RANGO_EXCEDIDO)
    max_dias_rango: int = field(default_factory=lambda: _entero("MAX_DIAS_RANGO", 31))


config = Configuracion()
