"""Conexión a PostgreSQL.

La URL sale de la variable de entorno DATABASE_URL, que docker-compose define como
postgresql+psycopg://<usuario>:<clave>@db-reportes:5432/reportes.

El pool es pequeño a propósito: la instancia EC2 tiene 1 GiB y PostgreSQL acepta como
máximo 20 conexiones (max_connections=20 en docker-compose.yml).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def crear_engine(url: str | None = None) -> Engine:
    """Crea el engine con un pool fijo de POOL_SIZE conexiones y sin conexiones extra."""
    url = url or os.environ["DATABASE_URL"]
    return create_engine(
        url,
        pool_size=POOL_SIZE,
        max_overflow=0,        # nunca más de POOL_SIZE conexiones abiertas
        pool_timeout=5,        # si el pool está lleno, esperar 5 s y fallar
        pool_pre_ping=True,    # descarta conexiones muertas (p. ej. tras reiniciar la BD)
        pool_recycle=1800,
        connect_args={"connect_timeout": 3},
    )


def obtener_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        _engine = crear_engine()
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def configurar(engine: Engine) -> None:
    """Usa un engine ya creado (pruebas o arranque personalizado)."""
    global _engine, _SessionLocal
    _engine = engine
    _SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def transaccion() -> Iterator[Session]:
    """Sesión que hace commit al salir sin errores y rollback si hay una excepción.

    Uso en la capa de servicios:
        with transaccion() as sesion:
            ejecuciones.iniciar(sesion, ...)
    """
    obtener_engine()
    assert _SessionLocal is not None
    sesion = _SessionLocal()
    try:
        yield sesion
        sesion.commit()
    except Exception:
        sesion.rollback()
        raise
    finally:
        sesion.close()


def obtener_sesion() -> Iterator[Session]:
    """Dependencia de FastAPI:  sesion: Session = Depends(obtener_sesion)."""
    with transaccion() as sesion:
        yield sesion


def verificar_conexion() -> bool:
    """True si la base de datos responde a SELECT 1. Lo usa GET /health."""
    try:
        with obtener_engine().connect() as conexion:
            conexion.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
