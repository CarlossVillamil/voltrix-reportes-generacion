"""Pruebas de la capa de presentación, sin base de datos.

La sesión, los repositorios y el servicio de generación se reemplazan por dobles, así que
estas pruebas solo verifican lo que promete el contrato: rutas, validación, formato de error
y cabeceras. Se ejecutan desde la raíz del repositorio con:
    python -m pytest tests/test_api.py
"""

from __future__ import annotations

import uuid
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api import routes_operacion, routes_reportes
from app.main import app
from app.services import generacion

BOGOTA = timezone(timedelta(hours=-5))
CAMPOS_AGREGADO = {
    "plantaId", "activoId", "tipoActivo", "granularidad", "periodoInicio", "periodoFin", "energiaKwh",
    "potenciaPromedioKw", "potenciaMaximaKw", "numeroLecturas", "capacidadNominalKw", "factorPlanta", "generadoEn",
}


def agregado(dia: int) -> dict:
    inicio = datetime(2026, 11, 1, tzinfo=BOGOTA) + timedelta(days=dia)
    return {
        "plantaId": "PL-001", "activoId": None, "tipoActivo": None, "granularidad": "dia",
        "periodoInicio": inicio, "periodoFin": inicio + timedelta(days=1),
        "energiaKwh": 1843.52, "potenciaPromedioKw": 76.81, "potenciaMaximaKw": 212.4,
        "numeroLecturas": 960, "capacidadNominalKw": 250.0, "factorPlanta": 0.3072,
        "generadoEn": datetime(2026, 11, 8, 2, 15, 44, tzinfo=timezone.utc),
    }


@pytest.fixture
def llamadas():
    return {}


@pytest.fixture
def cliente(monkeypatch, llamadas):
    def consultar(_sesion, **filtros):
        llamadas["consultar"] = filtros
        return [agregado(0), agregado(1)], 2

    def generar(solicitud, **opciones):
        llamadas["generar"] = (solicitud, opciones)
        workers = generacion.workers_efectivos(opciones["modo"], opciones["workers"])
        return {"generados": 14, "metricas": {"modo": opciones["modo"], "workers": workers,
                                              "elementos": 13440, "duracionMs": 842}}

    monkeypatch.setattr(routes_reportes.agregados, "consultar", consultar)
    monkeypatch.setattr(routes_reportes.generacion, "generar", generar)
    monkeypatch.setattr(routes_reportes, "transaccion", nullcontext)
    monkeypatch.setattr(routes_operacion.database, "verificar_conexion", lambda: True)
    return TestClient(app, raise_server_exceptions=False)


def es_error(respuesta, status: int, codigo: str) -> dict:
    assert respuesta.status_code == status
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == codigo
    assert set(cuerpo) <= {"codigo", "mensaje", "requestId", "detalles"}
    assert cuerpo["requestId"] == respuesta.headers["X-Request-Id"]
    return cuerpo


# ------------------------------ GET /reportes/generacion ------------------------------

def test_consulta_devuelve_pagina_del_contrato(cliente, llamadas):
    r = cliente.get("/reportes/generacion", params={"plantaId": "PL-001", "limit": 2},
                    headers={"X-Equipo-Consumidor": "equipo-5"})
    assert r.status_code == 200
    cuerpo = r.json()
    assert set(cuerpo) == {"datos", "total", "limit", "offset"}
    assert (cuerpo["total"], cuerpo["limit"], cuerpo["offset"]) == (2, 2, 0)
    assert set(cuerpo["datos"][0]) == CAMPOS_AGREGADO
    assert cuerpo["datos"][0]["periodoInicio"] == "2026-11-01T00:00:00-05:00"
    assert llamadas["consultar"]["granularidad"] == "dia"  # valor por defecto del contrato
    uuid.UUID(r.headers["X-Request-Id"])


def test_consulta_pasa_los_filtros_al_repositorio(cliente, llamadas):
    cliente.get("/reportes/generacion", params={
        "activoId": "PL-001-PS-07", "desde": "2026-11-01T00:00:00-05:00",
        "hasta": "2026-11-08T00:00:00-05:00", "granularidad": "hora", "offset": 10})
    filtros = llamadas["consultar"]
    assert filtros["activo_id"] == "PL-001-PS-07"
    assert filtros["granularidad"] == "hora"
    assert filtros["offset"] == 10
    assert filtros["desde"] == datetime(2026, 11, 1, tzinfo=BOGOTA)


@pytest.mark.parametrize("params, campo", [
    ({"limit": 0}, "limit"),
    ({"limit": 201}, "limit"),
    ({"offset": -1}, "offset"),
    ({"granularidad": "semana"}, "granularidad"),
    ({"plantaId": "PL 001"}, "plantaId"),
    ({"desde": "2026-11-01T00:00:00"}, "desde"),     # sin zona horaria
    ({"desde": "ayer"}, "desde"),
])
def test_consulta_parametros_invalidos(cliente, params, campo):
    cuerpo = es_error(cliente.get("/reportes/generacion", params=params), 400, "SOLICITUD_INVALIDA")
    assert cuerpo["detalles"][0]["campo"] == campo


def test_consulta_hasta_antes_de_desde(cliente):
    r = cliente.get("/reportes/generacion", params={"desde": "2026-11-08T00:00:00Z", "hasta": "2026-11-01T00:00:00Z"})
    assert es_error(r, 400, "SOLICITUD_INVALIDA")["detalles"] == [{"campo": "hasta", "problema": "debe ser posterior a desde"}]


def test_equipo_consumidor_con_formato_invalido(cliente):
    r = cliente.get("/reportes/generacion", headers={"X-Equipo-Consumidor": "equipo-9"})
    assert es_error(r, 400, "SOLICITUD_INVALIDA")["detalles"][0]["campo"] == "X-Equipo-Consumidor"


def test_request_id_del_consumidor_se_reutiliza(cliente):
    propio = str(uuid.uuid4())
    assert cliente.get("/reportes/generacion", headers={"X-Request-Id": propio}).headers["X-Request-Id"] == propio
    assert cliente.get("/reportes/generacion", headers={"X-Request-Id": "no-es-uuid"}).headers["X-Request-Id"] != "no-es-uuid"


def test_base_de_datos_caida_responde_503(cliente, monkeypatch):
    def caida(*_a, **_k):
        raise OperationalError("SELECT", {}, Exception("connection refused"))

    monkeypatch.setattr(routes_reportes.agregados, "consultar", caida)
    es_error(cliente.get("/reportes/generacion"), 503, "NO_DISPONIBLE")


def test_peticion_invalida_no_toca_la_base_de_datos(cliente, monkeypatch):
    def sin_base(*_a, **_k):
        raise AssertionError("no debía abrir la base de datos")

    monkeypatch.setattr(routes_reportes, "transaccion", sin_base)
    es_error(cliente.get("/reportes/generacion", params={"limit": 0}), 400, "SOLICITUD_INVALIDA")


def test_error_no_controlado_responde_500_con_formato_comun(cliente, monkeypatch):
    def falla(*_a, **_k):
        raise RuntimeError("inesperado")

    monkeypatch.setattr(routes_reportes.agregados, "consultar", falla)
    es_error(cliente.get("/reportes/generacion"), 500, "ERROR_INTERNO")


# ------------------------------- POST /reportes/generar -------------------------------

SOLICITUD = {"plantaIds": ["PL-001", "PL-002"], "desde": "2026-11-01T00:00:00-05:00",
             "hasta": "2026-11-08T00:00:00-05:00", "granularidad": "dia", "nivel": "planta"}


def test_generar_responde_resultado_del_contrato(cliente, llamadas):
    r = cliente.post("/reportes/generar", params={"modo": "paralelo", "workers": 2}, json=SOLICITUD,
                     headers={"X-Equipo-Consumidor": "equipo-7"})
    assert r.status_code == 200
    assert r.json() == {"generados": 14, "metricas": {"modo": "paralelo", "workers": 2,
                                                      "elementos": 13440, "duracionMs": 842}}
    solicitud, opciones = llamadas["generar"]
    assert solicitud["plantaIds"] == ["PL-001", "PL-002"]
    assert opciones["equipo_consumidor"] == "equipo-7"
    assert opciones["request_id"] == r.headers["X-Request-Id"]


def test_generar_valores_por_defecto(cliente, llamadas):
    r = cliente.post("/reportes/generar", json={"desde": SOLICITUD["desde"], "hasta": SOLICITUD["hasta"]})
    assert r.status_code == 200
    solicitud, opciones = llamadas["generar"]
    assert (solicitud["granularidad"], solicitud["nivel"], solicitud["plantaIds"]) == ("dia", "planta", None)
    assert opciones["modo"] == "paralelo"


def test_generar_secuencial_usa_un_worker(cliente):
    r = cliente.post("/reportes/generar", params={"modo": "secuencial", "workers": 8}, json=SOLICITUD)
    assert r.json()["metricas"]["workers"] == 1


def test_generar_rango_de_mas_de_31_dias(cliente):
    cuerpo = dict(SOLICITUD, hasta="2026-12-03T00:00:00-05:00")
    es_error(cliente.post("/reportes/generar", json=cuerpo), 400, "RANGO_EXCEDIDO")


def test_generar_rango_de_31_dias_exactos_se_acepta(cliente):
    cuerpo = dict(SOLICITUD, hasta="2026-12-02T00:00:00-05:00")
    assert cliente.post("/reportes/generar", json=cuerpo).status_code == 200


@pytest.mark.parametrize("cambio, campo", [
    ({"desde": None}, "desde"),
    ({"nivel": "region"}, "nivel"),
    ({"granularidad": "anio"}, "granularidad"),
    ({"extra": 1}, "extra"),
    ({"plantaIds": ["PL-001", ""]}, "plantaIds[1]"),
    ({"hasta": "2026-11-08"}, "hasta"),
])
def test_generar_cuerpo_invalido(cliente, cambio, campo):
    cuerpo = {k: v for k, v in {**SOLICITUD, **cambio}.items() if v is not None}
    assert es_error(cliente.post("/reportes/generar", json=cuerpo), 400, "SOLICITUD_INVALIDA")["detalles"][0]["campo"] == campo


@pytest.mark.parametrize("params, campo", [({"modo": "rapido"}, "modo"), ({"workers": 0}, "workers"), ({"workers": 65}, "workers")])
def test_generar_parametros_invalidos(cliente, params, campo):
    r = cliente.post("/reportes/generar", params=params, json=SOLICITUD)
    assert es_error(r, 400, "SOLICITUD_INVALIDA")["detalles"][0]["campo"] == campo


def test_generar_hasta_igual_a_desde(cliente):
    es_error(cliente.post("/reportes/generar", json=dict(SOLICITUD, hasta=SOLICITUD["desde"])), 400, "SOLICITUD_INVALIDA")


def test_generar_cuerpo_que_no_es_json(cliente):
    r = cliente.post("/reportes/generar", content=b"{no es json", headers={"Content-Type": "application/json"})
    es_error(r, 400, "SOLICITUD_INVALIDA")


# ------------------------------- /health y /openapi.yaml ------------------------------

def test_health_disponible(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200
    cuerpo = r.json()
    assert (cuerpo["estado"], cuerpo["baseDatos"]) == ("disponible", "ok")
    assert cuerpo["tiempoActivoSeg"] >= 0


def test_health_sin_base_de_datos(cliente, monkeypatch):
    monkeypatch.setattr(routes_operacion.database, "verificar_conexion", lambda: False)
    r = cliente.get("/health")
    assert r.status_code == 503
    assert (r.json()["estado"], r.json()["baseDatos"]) == ("no_disponible", "error")


def test_openapi_yaml_sirve_el_contrato(cliente):
    r = cliente.get("/openapi.yaml")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/yaml")
    assert "/reportes/generacion:" in r.text


def test_ruta_inexistente_y_metodo_no_permitido(cliente):
    es_error(cliente.get("/no-existe"), 404, "NO_ENCONTRADO")
    es_error(cliente.delete("/reportes/generacion"), 405, "SOLICITUD_INVALIDA")


def test_docs_de_fastapi_desactivados(cliente):
    assert cliente.get("/docs").status_code == 404
    assert cliente.get("/openapi.json").status_code == 404


# ------------------------------------- servicio ---------------------------------------

def test_workers_efectivos():
    assert generacion.workers_efectivos("secuencial", 8) == 1
    assert generacion.workers_efectivos("paralelo", 4) == 4
    assert generacion.workers_efectivos("paralelo", None) == generacion.config.max_workers
