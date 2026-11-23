"""Orquestación de POST /reportes/generar.

Esta es la interfaz entre la capa de presentación y el resto de la capa de negocio. La ruta
ya validó la solicitud (rango, fechas, granularidad, nivel) y llama a generar().

Estado en el Avance 1: se registra la ejecución en ejecucion_calculo y se responde con el
formato del contrato, pero todavía no se calcula nada (generados = 0). Los agregados de
ejemplo de GET /reportes/generacion vienen de db/datos_ejemplo.sql.

Pendiente para el Avance 2, en el punto marcado con TODO:
  1. Obtener capacidades (Equipo 1) y lecturas (Equipo 2) con los clientes  -> Camilo
  2. Calcular con agregador_secuencial / agregador_paralelo (Map-Reduce)    -> Tiffany
  3. Guardar con agregados.guardar(sesion, resultado, ejecucion_id)
"""

from __future__ import annotations

import time
from typing import Any

from app.config import config
from app.repositories import ejecuciones
from app.repositories.database import transaccion


def workers_efectivos(modo: str, workers: int | None) -> int:
    """La línea base secuencial usa siempre 1 proceso; en paralelo, lo pedido o MAX_WORKERS."""
    if modo == "secuencial":
        return 1
    return workers or config.max_workers


def generar(
    solicitud: dict[str, Any],
    *,
    modo: str,
    workers: int | None,
    request_id: str,
    equipo_consumidor: str | None,
) -> dict[str, Any]:
    """Ejecuta un cálculo y devuelve el cuerpo de ResultadoGeneracion.

    solicitud tiene las claves de SolicitudGeneracion: plantaIds, desde, hasta, granularidad, nivel.
    """
    n_workers = workers_efectivos(modo, workers)
    inicio = time.perf_counter()

    with transaccion() as sesion:
        ejecucion_id = ejecuciones.iniciar(
            sesion,
            request_id=request_id,
            equipo_consumidor=equipo_consumidor,
            modo=modo,
            workers=n_workers,
            granularidad=solicitud["granularidad"],
            nivel=solicitud["nivel"],
            desde=solicitud["desde"],
            hasta=solicitud["hasta"],
            planta_ids=solicitud.get("plantaIds"),
        )

        # TODO (Avance 2): obtener datos de los Equipos 1 y 2, calcular y guardar los agregados.
        elementos = 0
        generados = 0

        duracion_ms = int((time.perf_counter() - inicio) * 1000)
        ejecuciones.completar(sesion, ejecucion_id, elementos=elementos, generados=generados,
                              duracion_ms=duracion_ms)

    return {
        "generados": generados,
        "metricas": {"modo": modo, "workers": n_workers, "elementos": elementos, "duracionMs": duracion_ms},
    }
