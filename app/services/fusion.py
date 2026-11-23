from __future__ import annotations

from datetime import datetime, timezone

from app.services.integracion import ResultadoParcial
from app.services.particionador import Particion


def _clave_fusion(particion: Particion, nivel: str) -> tuple:
    periodo = (particion.periodo_inicio, particion.periodo_fin)
    if nivel == "activo":
        return (particion.activo.planta_id, particion.activo.activo_id, *periodo)
    return (particion.activo.planta_id, None, *periodo)


def fusionar_resultados(
    parciales: list[tuple[Particion, ResultadoParcial]],
    granularidad: str,
    nivel: str,
) -> list[dict]:
    grupos: dict[tuple, list[tuple[Particion, ResultadoParcial]]] = {}
    for particion, resultado in parciales:
        grupos.setdefault(_clave_fusion(particion, nivel), []).append((particion, resultado))

    generado_en = datetime.now(timezone.utc).isoformat()
    agregados = []
    for (planta_id, activo_id, periodo_inicio, periodo_fin), items in grupos.items():
        numero_lecturas = sum(r.numero_lecturas for _, r in items)
        energia_kwh = sum(r.energia_kwh for _, r in items)
        suma_potencias = sum(r.suma_potencias_kw for _, r in items)
        potencia_maxima = max(r.potencia_maxima_kw for _, r in items)
        capacidad_nominal = sum(p.activo.capacidad_nominal_kw for p, _ in items)
        tipo_activo = items[0][0].activo.tipo_activo if nivel == "activo" else None

        potencia_promedio = suma_potencias / numero_lecturas if numero_lecturas else 0.0
        horas_periodo = (periodo_fin - periodo_inicio).total_seconds() / 3600.0
        factor_planta = (
            energia_kwh / (capacidad_nominal * horas_periodo)
            if capacidad_nominal > 0 and horas_periodo > 0
            else None
        )

        agregados.append(
            {
                "plantaId": planta_id,
                "activoId": activo_id,
                "tipoActivo": tipo_activo,
                "granularidad": granularidad,
                "periodoInicio": periodo_inicio.isoformat(),
                "periodoFin": periodo_fin.isoformat(),
                "energiaKwh": round(energia_kwh, 3),
                "potenciaPromedioKw": round(potencia_promedio, 3),
                "potenciaMaximaKw": round(potencia_maxima, 3),
                "numeroLecturas": numero_lecturas,
                "capacidadNominalKw": round(capacidad_nominal, 3) if capacidad_nominal > 0 else None,
                "factorPlanta": round(factor_planta, 4) if factor_planta is not None else None,
                "generadoEn": generado_en,
            }
        )
    return agregados
