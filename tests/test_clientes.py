"""Pruebas de los clientes de los Equipos 1 y 2, sin red.

Los clientes reales se prueban con httpx.MockTransport (simula las respuestas HTTP del otro
equipo) y el modo simulado se prueba directamente. Se ejecutan con:
    python -m pytest tests/test_clientes.py
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.api.errores import ErrorApi
from app.config import Configuracion
from app.contexto import fijar
from app.services.clientes import (
    ClienteInventarioHttp,
    ClienteTelemetriaHttp,
    crear_fuente,
)

BOGOTA = timezone(timedelta(hours=-5))
DESDE = datetime(2026, 11, 1, tzinfo=BOGOTA)
HASTA = datetime(2026, 11, 3, tzinfo=BOGOTA)


def transporte(manejador) -> httpx.MockTransport:
    return httpx.MockTransport(manejador)


def lectura(activo: str, hora: int, kw: float) -> dict:
    instante = datetime(2026, 11, 1, hora, tzinfo=BOGOTA).isoformat()
    return {"activoId": activo, "timestamp": instante, "potenciaKw": kw}


# ------------------------------------------------------------------ Inventario (Equipo 1)

def test_inventario_lee_activo_y_envia_cabeceras():
    fijar("req-123", "equipo-5")
    vistas = {}

    def responder(peticion: httpx.Request) -> httpx.Response:
        vistas["url"] = str(peticion.url)
        vistas["cabeceras"] = peticion.headers
        return httpx.Response(200, json={"id": "PL-001-PS-01", "plantaId": "PL-001",
                                         "tipo": "panel_solar", "capacidadNominalKw": 250})

    cliente = ClienteInventarioHttp("http://inventario:9000/", transporte=transporte(responder))
    activo = cliente.obtener_activo("PL-001-PS-01")

    assert vistas["url"] == "http://inventario:9000/activos/PL-001-PS-01"
    assert vistas["cabeceras"]["X-Equipo-Consumidor"] == "equipo-4"
    assert vistas["cabeceras"]["X-Request-Id"] == "req-123"
    assert (activo.planta_id, activo.tipo_activo, activo.capacidad_nominal_kw) == ("PL-001", "panel_solar", 250.0)


def test_inventario_sin_url_da_error_claro():
    with pytest.raises(ErrorApi) as error:
        ClienteInventarioHttp(None)
    assert error.value.status == 502 and error.value.codigo == "DEPENDENCIA_FALLIDA"
    assert "INVENTARIO_URL" in error.value.detalles[0]["problema"]


@pytest.mark.parametrize("respuesta", [
    httpx.Response(404, json={}),
    httpx.Response(503, json={}),
    httpx.Response(200, text="no es json"),
    httpx.Response(200, json={"id": "PL-001-PS-01"}),  # faltan campos
])
def test_inventario_respuestas_malas_son_dependencia_fallida(respuesta):
    cliente = ClienteInventarioHttp("http://inventario", transporte=transporte(lambda _: respuesta))
    with pytest.raises(ErrorApi) as error:
        cliente.obtener_activo("PL-001-PS-01")
    assert (error.value.status, error.value.codigo) == (502, "DEPENDENCIA_FALLIDA")
    assert error.value.detalles[0]["campo"] == "equipo-1"


def test_inventario_timeout_es_dependencia_fallida():
    def responder(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lento")

    cliente = ClienteInventarioHttp("http://inventario", transporte=transporte(responder))
    with pytest.raises(ErrorApi) as error:
        cliente.obtener_activo("PL-001-PS-01")
    assert "tiempo de espera" in error.value.detalles[0]["problema"]


# ------------------------------------------------------------------ Telemetría (Equipo 2)

def test_telemetria_agrupa_por_activo_y_ordena_por_tiempo():
    vistas = {}

    def responder(peticion: httpx.Request) -> httpx.Response:
        vistas["ruta"] = peticion.url.path
        vistas["params"] = dict(peticion.url.params)
        # desordenadas a propósito
        return httpx.Response(200, json=[lectura("PL-001-PS-01", 12, 200.0), lectura("PL-001-PS-01", 10, 100.0),
                                         lectura("PL-001-TE-02", 10, 300.0)])

    cliente = ClienteTelemetriaHttp("http://telemetria:9001", transporte=transporte(responder))
    lecturas = cliente.obtener_lecturas("PL-001", DESDE, HASTA)

    assert vistas["ruta"] == "/telemetria/PL-001"
    assert vistas["params"]["desde"] == DESDE.isoformat()
    assert vistas["params"]["hasta"] == HASTA.isoformat()
    instantes, potencias = lecturas["PL-001-PS-01"]
    assert list(potencias) == [100.0, 200.0]
    assert instantes[0] < instantes[1]
    assert list(lecturas["PL-001-TE-02"][1]) == [300.0]


def test_telemetria_sigue_la_paginacion():
    paginas = [
        {"datos": [lectura("PL-001-PS-01", 10, 1.0), lectura("PL-001-PS-01", 11, 2.0)], "total": 3},
        {"datos": [lectura("PL-001-PS-01", 12, 3.0)], "total": 3},
    ]
    offsets = []

    def responder(peticion: httpx.Request) -> httpx.Response:
        offset = int(peticion.url.params["offset"])
        offsets.append(offset)
        return httpx.Response(200, json=paginas[0 if offset == 0 else 1])

    cliente = ClienteTelemetriaHttp("http://telemetria", transporte=transporte(responder))
    lecturas = cliente.obtener_lecturas("PL-001", DESDE, HASTA)

    assert offsets == [0, 2]
    assert list(lecturas["PL-001-PS-01"][1]) == [1.0, 2.0, 3.0]


def test_telemetria_pagina_con_el_limite_maximo_de_200():
    vistas = []

    def responder(peticion: httpx.Request) -> httpx.Response:
        vistas.append((int(peticion.url.params["limit"]), int(peticion.url.params["offset"])))
        return httpx.Response(200, json=[])

    ClienteTelemetriaHttp("http://telemetria", transporte=transporte(responder)).obtener_lecturas("PL-001", DESDE, HASTA)
    assert vistas == [(200, 0)]


def test_telemetria_sin_total_sigue_hasta_una_pagina_incompleta():
    """Si el Equipo 2 no devuelve "total", una página llena (200) obliga a pedir la siguiente."""
    horas = [datetime(2026, 11, 1, tzinfo=BOGOTA) + timedelta(minutes=15 * i) for i in range(250)]
    todas = [{"activoId": "PL-001-PS-01", "timestamp": h.isoformat(), "potenciaKw": float(i)}
             for i, h in enumerate(horas)]
    offsets = []

    def responder(peticion: httpx.Request) -> httpx.Response:
        limite, offset = int(peticion.url.params["limit"]), int(peticion.url.params["offset"])
        offsets.append(offset)
        return httpx.Response(200, json={"datos": todas[offset:offset + limite]})  # sin total

    lecturas = ClienteTelemetriaHttp("http://telemetria", transporte=transporte(responder)).obtener_lecturas(
        "PL-001", DESDE, HASTA)
    assert offsets == [0, 200]
    assert len(lecturas["PL-001-PS-01"][1]) == 250


def test_telemetria_usa_el_limit_que_informa_el_servidor():
    """Si el servidor recorta el límite (p. ej. a 50), una página de 50 no es la última."""
    todas = [lectura("PL-001-PS-01", 10 + i % 12, float(i)) for i in range(120)]
    offsets = []

    def responder(peticion: httpx.Request) -> httpx.Response:
        offset = int(peticion.url.params["offset"])
        offsets.append(offset)
        return httpx.Response(200, json={"datos": todas[offset:offset + 50], "limit": 50, "offset": offset})

    ClienteTelemetriaHttp("http://telemetria", transporte=transporte(responder)).obtener_lecturas("PL-001", DESDE, HASTA)
    assert offsets == [0, 50, 100]


@pytest.mark.parametrize("respuesta", [
    httpx.Response(502, json={}),
    httpx.Response(200, json={"algo": "raro"}),
    httpx.Response(200, json=[{"activoId": "A", "timestamp": "2026-11-01T10:00:00", "potenciaKw": 1}]),  # sin zona
    httpx.Response(200, json=[{"activoId": "A", "timestamp": "2026-11-01T10:00:00-05:00"}]),  # sin potencia
])
def test_telemetria_respuestas_malas_son_dependencia_fallida(respuesta):
    cliente = ClienteTelemetriaHttp("http://telemetria", transporte=transporte(lambda _: respuesta))
    with pytest.raises(ErrorApi) as error:
        cliente.obtener_lecturas("PL-001", DESDE, HASTA)
    assert (error.value.status, error.value.codigo) == (502, "DEPENDENCIA_FALLIDA")
    assert error.value.detalles[0]["campo"] == "equipo-2"


# ------------------------------------------------------------------ fuente completa

def test_fuente_real_combina_telemetria_e_inventario():
    llamadas_inventario = []

    def inventario(peticion: httpx.Request) -> httpx.Response:
        llamadas_inventario.append(peticion.url.path)
        return httpx.Response(200, json={"id": "PL-001-PS-01", "plantaId": "PL-001",
                                         "tipo": "panel_solar", "capacidadNominalKw": 250})

    def telemetria(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[lectura("PL-001-PS-01", 10, 100.0), lectura("PL-001-PS-01", 11, 120.0)])

    cfg = Configuracion(inventario_url="http://inv", telemetria_url="http://tel", modo_simulado=False)
    with crear_fuente(cfg, transporte_inventario=transporte(inventario),
                      transporte_telemetria=transporte(telemetria)) as fuente:
        # dos plantas piden el mismo activo: el inventario se consulta una sola vez
        series = fuente.obtener_series(["PL-001", "PL-001"], DESDE, HASTA)

    assert len(series) == 2
    assert series[0].activo.capacidad_nominal_kw == 250.0
    assert llamadas_inventario == ["/activos/PL-001-PS-01"]


def test_fuente_real_sin_urls_falla_con_mensaje_claro():
    cfg = Configuracion(inventario_url=None, telemetria_url=None, modo_simulado=False)
    with pytest.raises(ErrorApi) as error:
        crear_fuente(cfg)
    assert "MODO_SIMULADO" in error.value.mensaje


# ------------------------------------------------------------------ modo simulado

def test_modo_simulado_no_usa_red_ni_urls():
    cfg = Configuracion(inventario_url=None, telemetria_url=None, modo_simulado=True)
    with crear_fuente(cfg) as fuente:
        series = fuente.obtener_series(["PL-001", "PL-002"], DESDE, HASTA)

    assert len(series) == 12  # 6 activos por planta
    serie = series[0]
    assert serie.timestamps_epoch.shape == serie.potencias_kw.shape == (2 * 96,)  # 2 días a 15 min
    assert (serie.potencias_kw >= 0).all() and (serie.potencias_kw <= serie.activo.capacidad_nominal_kw).all()
    assert (serie.timestamps_epoch[1:] > serie.timestamps_epoch[:-1]).all()


def test_modo_simulado_es_reproducible_y_solar_no_genera_de_noche():
    cfg = Configuracion(modo_simulado=True)
    with crear_fuente(cfg) as fuente:
        a = fuente.obtener_series(["PL-001"], DESDE, HASTA)
        b = fuente.obtener_series(["PL-001"], DESDE, HASTA)
    assert (a[0].potencias_kw == b[0].potencias_kw).all()

    solar = next(s for s in a if s.activo.tipo_activo == "panel_solar")
    medianoche = solar.potencias_kw[0]  # 00:00 hora de Bogotá
    mediodia = solar.potencias_kw[48]  # 12:00
    assert medianoche < 20 and mediodia > 150


def test_modo_simulado_rango_vacio_no_devuelve_series():
    cfg = Configuracion(modo_simulado=True)
    with crear_fuente(cfg) as fuente:
        assert fuente.obtener_series(["PL-001"], DESDE, DESDE) == []


def test_configuracion_lee_el_entorno(monkeypatch):
    monkeypatch.setenv("MODO_SIMULADO", "True")
    monkeypatch.setenv("INVENTARIO_URL", "http://inv:1")
    monkeypatch.setenv("CLIENTES_TIMEOUT_S", "3.5")
    cfg = Configuracion()
    assert cfg.modo_simulado is True
    assert cfg.inventario_url == "http://inv:1"
    assert cfg.timeout_clientes_s == 3.5
    assert cfg.telemetria_url is None
