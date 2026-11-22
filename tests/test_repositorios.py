"""Pruebas de la capa de datos contra un PostgreSQL real.

Necesitan una base con las tablas de db/init.sql y la variable TEST_DATABASE_URL, por ejemplo:
    TEST_DATABASE_URL=postgresql+psycopg://reportes:<clave>@localhost:5432/reportes pytest tests/test_repositorios.py
Sin esa variable se omiten. ¡Vacían las tablas! No usar contra la base de EC2.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.repositories import agregados, database, ejecuciones

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL no definida")

BOGOTA = timezone(timedelta(hours=-5))
INICIO = datetime(2026, 11, 1, tzinfo=BOGOTA)


@pytest.fixture(autouse=True)
def base_limpia():
    engine = database.crear_engine(URL)
    database.configurar(engine)
    with engine.begin() as conexion:
        conexion.execute(text("TRUNCATE agregado_generacion, ejecucion_calculo RESTART IDENTITY"))
    yield
    engine.dispose()


def agregado(dia: int, planta="PL-001", activo=None, energia=100.0, granularidad="dia"):
    inicio = INICIO + timedelta(days=dia)
    return {
        "plantaId": planta,
        "activoId": activo,
        "tipoActivo": "panel solar" if activo else None,
        "granularidad": granularidad,
        "periodoInicio": inicio,
        "periodoFin": inicio + timedelta(days=1),
        "energiaKwh": energia,
        "potenciaPromedioKw": energia / 24,
        "potenciaMaximaKw": energia / 10,
        "numeroLecturas": 96,
        "capacidadNominalKw": 250.0,
        "factorPlanta": energia / (250 * 24),
    }


def test_guardar_y_consultar_paginado():
    with database.transaccion() as s:
        assert agregados.guardar(s, [agregado(d) for d in range(10)]) == 10
    with database.transaccion() as s:
        pagina, total = agregados.consultar(s, planta_id="PL-001", granularidad="dia", limit=4, offset=4)
    assert total == 10
    assert len(pagina) == 4
    assert pagina[0]["periodoInicio"] == INICIO + timedelta(days=4)  # orden por periodo
    assert set(pagina[0]) == set(agregados.CAMPOS)                   # campos del contrato
    assert pagina[0]["activoId"] is None


def test_guardar_reemplaza_el_mismo_periodo():
    with database.transaccion() as s:
        agregados.guardar(s, [agregado(0, energia=100)])
    with database.transaccion() as s:
        agregados.guardar(s, [agregado(0, energia=250)])  # mismo agregado de planta (activo NULL)
    with database.transaccion() as s:
        pagina, total = agregados.consultar(s, planta_id="PL-001")
    assert total == 1
    assert pagina[0]["energiaKwh"] == 250


def test_filtro_por_activo_separa_planta_y_activo():
    with database.transaccion() as s:
        agregados.guardar(s, [agregado(0), agregado(0, activo="PL-001-PS-07"), agregado(1, activo="PL-001-PS-07")])
    with database.transaccion() as s:
        _, total_planta = agregados.consultar(s, planta_id="PL-001")
        pagina, total_activo = agregados.consultar(s, activo_id="PL-001-PS-07")
    assert total_planta == 1
    assert total_activo == 2
    assert all(a["activoId"] == "PL-001-PS-07" for a in pagina)


def test_rango_desde_inclusivo_hasta_exclusivo():
    with database.transaccion() as s:
        agregados.guardar(s, [agregado(d) for d in range(7)])
    with database.transaccion() as s:
        pagina, total = agregados.consultar(
            s, desde=INICIO + timedelta(days=2), hasta=INICIO + timedelta(days=5)
        )
    assert total == 3
    assert [a["periodoInicio"].day for a in pagina] == [3, 4, 5]


def test_filtros_por_planta_y_granularidad():
    with database.transaccion() as s:
        agregados.guardar(s, [agregado(0, planta="PL-001"), agregado(0, planta="PL-002"),
                              agregado(0, planta="PL-001", granularidad="hora")])
    with database.transaccion() as s:
        _, total = agregados.consultar(s, planta_id="PL-001", granularidad="dia")
        _, sin_filtros = agregados.consultar(s)
    assert total == 1
    assert sin_filtros == 3


def test_falta_un_campo_obligatorio():
    malo = agregado(0)
    del malo["energiaKwh"]
    with pytest.raises(ValueError, match="energiaKwh"):
        with database.transaccion() as s:
            agregados.guardar(s, [malo])


def test_ejecucion_completa_y_enlace_con_agregados():
    with database.transaccion() as s:
        eid = ejecuciones.iniciar(
            s, request_id="req-1", equipo_consumidor="equipo-5", modo="paralelo", workers=2,
            granularidad="dia", nivel="planta", desde=INICIO, hasta=INICIO + timedelta(days=7),
            planta_ids=["PL-001", "PL-002"],
        )
        agregados.guardar(s, [agregado(d) for d in range(7)], ejecucion_id=eid)
        ejecuciones.completar(s, eid, elementos=6720, generados=7, duracion_ms=842)
    with database.transaccion() as s:
        [ultima] = ejecuciones.ultimas(s)
        enlazados = s.scalar(text("SELECT count(*) FROM agregado_generacion WHERE ejecucion_id = :e"), {"e": eid})
    assert ultima["estado"] == "completado"
    assert (ultima["modo"], ultima["workers"], ultima["duracionMs"]) == ("paralelo", 2, 842)
    assert ultima["finalizadoEn"] is not None
    assert enlazados == 7


def test_ejecucion_con_error():
    with database.transaccion() as s:
        eid = ejecuciones.iniciar(s, request_id="req-2", modo="secuencial", workers=1, granularidad="hora",
                                  nivel="activo", desde=INICIO, hasta=INICIO + timedelta(days=1))
        ejecuciones.marcar_error(s, eid, "Telemetría respondió 503")
    with database.transaccion() as s:
        [ultima] = ejecuciones.ultimas(s)
    assert ultima["estado"] == "error"


def test_rollback_si_hay_excepcion():
    with pytest.raises(RuntimeError):
        with database.transaccion() as s:
            agregados.guardar(s, [agregado(0)])
            raise RuntimeError("falla a mitad del cálculo")
    with database.transaccion() as s:
        _, total = agregados.consultar(s)
    assert total == 0


def test_pool_de_cinco_conexiones_sin_extra():
    engine = database.obtener_engine()
    assert engine.pool.size() == 5
    assert engine.pool._max_overflow == 0


def test_verificar_conexion():
    assert database.verificar_conexion() is True
    database.configurar(database.crear_engine("postgresql+psycopg://x:y@127.0.0.1:1/nada"))
    assert database.verificar_conexion() is False
