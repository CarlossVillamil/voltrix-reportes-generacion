from __future__ import annotations

import csv
import os
import platform
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.services.motor_agregacion import calcular
from benchmark.generador_datos import ParametrosGenerador, generar_datos_sinteticos

ZONA_BOGOTA = ZoneInfo("America/Bogota")
CARPETA_RESULTADOS = Path(__file__).parent / "resultados"

WORKERS_A_PROBAR = (1, 2, 4, 8)


def _declarar_equipo() -> None:
    print("Equipo de medición:")
    print(f"  Procesador: {platform.processor() or platform.machine()}")
    print(f"  Núcleos lógicos: {os.cpu_count()}")
    print(f"  Sistema operativo: {platform.system()} {platform.release()}")
    print(f"  Python: {platform.python_version()}")
    print()


def ejecutar_escenario(nombre_escenario: str, parametros: ParametrosGenerador, granularidad: str, nivel: str) -> list[dict]:
    print(f"Generando datos sintéticos para {nombre_escenario}...")
    series = generar_datos_sinteticos(parametros)
    total_lecturas = sum(s.timestamps_epoch.shape[0] for s in series)
    print(f"  {len(series)} series, {total_lecturas} lecturas totales\n")

    desde = parametros.fecha_inicio
    hasta = parametros.fecha_inicio + timedelta(days=parametros.dias)

    filas = []

    print(f"Corriendo modo=secuencial ({nombre_escenario}, granularidad={granularidad}, nivel={nivel})...")
    _, metricas_base = calcular(series, desde, hasta, granularidad, nivel, modo="secuencial")
    tiempo_base_ms = metricas_base["duracionMs"]
    print(f"  duracionMs={tiempo_base_ms}  elementos={metricas_base['elementos']}\n")
    filas.append({**metricas_base, "escenario": nombre_escenario, "speedup": 1.0, "eficiencia": 1.0})

    for workers in WORKERS_A_PROBAR:
        print(f"Corriendo modo=paralelo workers={workers} ({nombre_escenario})...")
        _, metricas = calcular(series, desde, hasta, granularidad, nivel, modo="paralelo", workers=workers)
        speedup = tiempo_base_ms / metricas["duracionMs"] if metricas["duracionMs"] > 0 else float("inf")
        eficiencia = speedup / workers
        print(f"  duracionMs={metricas['duracionMs']}  speedup={speedup:.2f}  eficiencia={eficiencia:.2f}\n")
        filas.append({**metricas, "escenario": nombre_escenario, "speedup": round(speedup, 3), "eficiencia": round(eficiencia, 3)})

    return filas


def guardar_csv(filas: list[dict], nombre_archivo: str) -> Path:
    CARPETA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    ruta = CARPETA_RESULTADOS / nombre_archivo
    campos = ["escenario", "modo", "workers", "elementos", "duracionMs", "speedup", "eficiencia"]
    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=campos)
        escritor.writeheader()
        for fila in filas:
            escritor.writerow({campo: fila[campo] for campo in campos})
    return ruta


def main() -> None:
    _declarar_equipo()

    escenario_e1 = ParametrosGenerador(
        num_plantas=80,
        activos_por_planta=10,
        dias=7,
        fecha_inicio=datetime(2026, 11, 1, tzinfo=ZONA_BOGOTA),
        seed=42,
    )
    filas = ejecutar_escenario("E1_preliminar", escenario_e1, granularidad="dia", nivel="planta")

    marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = guardar_csv(filas, f"benchmark_preliminar_{marca_tiempo}.csv")
    print(f"Resultados guardados en: {ruta}")


if __name__ == "__main__":
    main()
