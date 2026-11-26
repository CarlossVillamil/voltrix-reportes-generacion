"""Clientes de los servicios de otros equipos: Inventario (Equipo 1) y Telemetría (Equipo 2).

Cada servicio tiene dos implementaciones con la misma interfaz:

  * Real (httpx): la URL base sale de INVENTARIO_URL / TELEMETRIA_URL.
  * Simulada: datos sintéticos deterministas, sin red. Se activa con MODO_SIMULADO=true.

El resto del servicio solo usa obtener_series(), y no sabe cuál de las dos está detrás:

    from app.services.clientes import crear_fuente

    with crear_fuente() as fuente:
        series = fuente.obtener_series(["PL-001", "PL-002"], desde, hasta)

Todo fallo de un servicio ajeno (sin conexión, timeout, 4xx/5xx, cuerpo inesperado) se convierte
en ErrorApi 502 DEPENDENCIA_FALLIDA, como pide el contrato.

SUPUESTOS SOBRE LOS CONTRATOS DE LOS EQUIPOS 1 Y 2 (ajustar aquí si difieren):
  * GET {INVENTARIO_URL}/activos/{id}        -> objeto con id, plantaId, tipo y capacidadNominalKw.
  * GET {TELEMETRIA_URL}/telemetria/{planta} -> lecturas con activoId, timestamp y potenciaKw,
    filtradas con ?desde=&hasta= (RFC 3339; desde inclusivo, hasta exclusivo) y paginadas con
    ?limit= (por defecto 50, máximo 200) y ?offset= (por defecto 0). La respuesta puede ser una
    lista o un objeto con las lecturas en "datos" (y total/limit/offset, como en la plantilla común).
  Los nombres de campo aceptados están en las tuplas CAMPOS_* de abajo.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

import httpx
import numpy as np

from app.api.errores import ErrorApi, dependencia_fallida
from app.config import Configuracion, config
from app.contexto import EQUIPO_PROPIO, request_id_actual
from app.services.modelos import ActivoInfo, SerieLecturas

log = logging.getLogger("reportes.clientes")

EQUIPO_INVENTARIO = "equipo-1"
EQUIPO_TELEMETRIA = "equipo-2"

# Nombres de campo aceptados en las respuestas de los otros equipos (el primero que exista).
CAMPOS_ACTIVO_ID = ("id", "activoId")
CAMPOS_PLANTA_ID = ("plantaId",)
CAMPOS_TIPO = ("tipo", "tipoActivo")
CAMPOS_CAPACIDAD = ("capacidadNominalKw",)
CAMPOS_LISTA = ("datos", "lecturas", "items")
CAMPOS_LECTURA_ACTIVO = ("activoId",)
CAMPOS_LECTURA_TIEMPO = ("timestamp", "instante", "fecha")
CAMPOS_LECTURA_POTENCIA = ("potenciaKw", "potencia")

# Límite máximo de lecturas por página que acepta Telemetría (Equipo 2); por defecto ellos usan 50
PAGINA_TELEMETRIA = 200

# activo_id -> (timestamps_epoch, potencias_kw), ordenadas por tiempo
LecturasPlanta = dict[str, tuple[np.ndarray, np.ndarray]]


# ------------------------------------------------------------------ interfaces

class ClienteInventario(Protocol):
    def obtener_activo(self, activo_id: str) -> ActivoInfo: ...
    def close(self) -> None: ...


class ClienteTelemetria(Protocol):
    def obtener_lecturas(self, planta_id: str, desde: datetime, hasta: datetime) -> LecturasPlanta: ...
    def close(self) -> None: ...


# ------------------------------------------------------------------ utilidades HTTP

def _primero(cuerpo: dict[str, Any], nombres: tuple[str, ...]) -> Any:
    for nombre in nombres:
        if nombre in cuerpo and cuerpo[nombre] is not None:
            return cuerpo[nombre]
    raise KeyError(nombres[0])


class _ClienteHttp:
    """Base de los clientes reales: httpx.Client con cabeceras de trazabilidad y errores unificados."""

    def __init__(
        self,
        *,
        url_base: str | None,
        variable: str,
        equipo: str,
        nombre_servicio: str,
        timeout_s: float,
        reintentos: int,
        transporte: httpx.BaseTransport | None = None,
    ) -> None:
        if not url_base:
            # Configuración incompleta: se avisa con un error claro en lugar de un fallo de red críptico.
            raise dependencia_fallida(
                equipo,
                f"falta la variable de entorno {variable}",
                f"No hay URL configurada para {nombre_servicio}. Defina {variable} o active MODO_SIMULADO=true.",
            )
        self._equipo = equipo
        self._servicio = nombre_servicio
        self._http = httpx.Client(
            base_url=url_base.rstrip("/"),
            timeout=timeout_s,
            transport=transporte or httpx.HTTPTransport(retries=max(0, reintentos)),
        )

    def close(self) -> None:
        self._http.close()

    def _get(self, ruta: str, params: dict[str, Any] | None = None) -> Any:
        etiqueta = f"GET {ruta}"
        cabeceras = {"X-Equipo-Consumidor": EQUIPO_PROPIO, "X-Request-Id": request_id_actual()}
        try:
            respuesta = self._http.get(ruta, params=params, headers=cabeceras)
        except httpx.TimeoutException as exc:
            raise self._fallo(f"{etiqueta} superó el tiempo de espera", exc) from exc
        except httpx.HTTPError as exc:
            raise self._fallo(f"{etiqueta} no pudo conectar ({exc.__class__.__name__})", exc) from exc

        if respuesta.status_code >= 400:
            raise self._fallo(f"{etiqueta} respondió {respuesta.status_code}")
        try:
            return respuesta.json()
        except ValueError as exc:
            raise self._fallo(f"{etiqueta} no devolvió JSON válido", exc) from exc

    def _fallo(self, problema: str, causa: Exception | None = None) -> ErrorApi:
        log.warning("dependencia fallida (%s): %s", self._equipo, problema, exc_info=causa is not None)
        return dependencia_fallida(self._equipo, problema, f"{self._servicio} no respondió como se esperaba.")


# ------------------------------------------------------------------ Equipo 1: Inventario

class ClienteInventarioHttp(_ClienteHttp):
    def __init__(self, url_base: str | None, *, timeout_s: float = 10.0, reintentos: int = 2,
                 transporte: httpx.BaseTransport | None = None) -> None:
        super().__init__(url_base=url_base, variable="INVENTARIO_URL", equipo=EQUIPO_INVENTARIO,
                         nombre_servicio="Inventario de Activos", timeout_s=timeout_s,
                         reintentos=reintentos, transporte=transporte)

    def obtener_activo(self, activo_id: str) -> ActivoInfo:
        ruta = f"/activos/{activo_id}"
        cuerpo = self._get(ruta)
        try:
            return ActivoInfo(
                activo_id=str(_primero(cuerpo, CAMPOS_ACTIVO_ID)),
                planta_id=str(_primero(cuerpo, CAMPOS_PLANTA_ID)),
                tipo_activo=str(_primero(cuerpo, CAMPOS_TIPO)),
                capacidad_nominal_kw=float(_primero(cuerpo, CAMPOS_CAPACIDAD)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise self._fallo(f"GET {ruta} devolvió un activo sin los campos esperados ({exc})", exc) from exc


# ------------------------------------------------------------------ Equipo 2: Telemetría

class ClienteTelemetriaHttp(_ClienteHttp):
    def __init__(self, url_base: str | None, *, timeout_s: float = 10.0, reintentos: int = 2,
                 transporte: httpx.BaseTransport | None = None) -> None:
        super().__init__(url_base=url_base, variable="TELEMETRIA_URL", equipo=EQUIPO_TELEMETRIA,
                         nombre_servicio="Telemetría de Plantas", timeout_s=timeout_s,
                         reintentos=reintentos, transporte=transporte)

    def obtener_lecturas(self, planta_id: str, desde: datetime, hasta: datetime) -> LecturasPlanta:
        ruta = f"/telemetria/{planta_id}"
        base = {"desde": desde.isoformat(), "hasta": hasta.isoformat()}
        lecturas: list[dict[str, Any]] = []
        offset = 0
        while True:
            cuerpo = self._get(ruta, {**base, "limit": PAGINA_TELEMETRIA, "offset": offset})
            pagina = self._extraer_lista(ruta, cuerpo)
            lecturas.extend(pagina)
            offset += len(pagina)
            if self._es_ultima_pagina(cuerpo, len(pagina), offset):
                break
        return self._agrupar(ruta, lecturas)

    @staticmethod
    def _es_ultima_pagina(cuerpo: Any, recibidas: int, offset: int) -> bool:
        """Con "total" se sabe exactamente; sin él, una página incompleta indica que no hay más.

        Si el servidor recortó el límite pedido, se usa el "limit" que informa en la respuesta.
        """
        if recibidas == 0:
            return True
        datos = cuerpo if isinstance(cuerpo, dict) else {}
        if datos.get("total") is not None:
            return offset >= int(datos["total"])
        limite = int(datos.get("limit") or PAGINA_TELEMETRIA)
        return recibidas < limite

    def _extraer_lista(self, ruta: str, cuerpo: Any) -> list[dict[str, Any]]:
        if isinstance(cuerpo, list):
            return cuerpo
        if isinstance(cuerpo, dict):
            for nombre in CAMPOS_LISTA:
                if isinstance(cuerpo.get(nombre), list):
                    return cuerpo[nombre]
        raise self._fallo(f"GET {ruta} no devolvió una lista de lecturas")

    def _agrupar(self, ruta: str, lecturas: Iterable[dict[str, Any]]) -> LecturasPlanta:
        por_activo: dict[str, list[tuple[float, float]]] = {}
        try:
            for lectura in lecturas:
                activo_id = str(_primero(lectura, CAMPOS_LECTURA_ACTIVO))
                instante = datetime.fromisoformat(str(_primero(lectura, CAMPOS_LECTURA_TIEMPO)))
                if instante.tzinfo is None:
                    raise ValueError("timestamp sin zona horaria")
                potencia = float(_primero(lectura, CAMPOS_LECTURA_POTENCIA))
                por_activo.setdefault(activo_id, []).append((instante.timestamp(), potencia))
        except (KeyError, TypeError, ValueError) as exc:
            raise self._fallo(f"GET {ruta} devolvió una lectura inválida ({exc})", exc) from exc

        resultado: LecturasPlanta = {}
        for activo_id, pares in por_activo.items():
            matriz = np.array(sorted(pares), dtype=np.float64)
            resultado[activo_id] = (matriz[:, 0], matriz[:, 1])
        return resultado


# ------------------------------------------------------------------ modo simulado

_TIPOS_SIMULADOS = ("panel_solar", "turbina_eolica", "bateria")
_PREFIJOS_SIMULADOS = {"panel_solar": "PS", "turbina_eolica": "TE", "bateria": "BT"}
_CAPACIDAD_SIMULADA_KW = {"panel_solar": 250.0, "turbina_eolica": 500.0, "bateria": 100.0}
ACTIVOS_POR_PLANTA_SIMULADOS = 6
INTERVALO_SIMULADO_S = 15 * 60


def _activos_simulados(planta_id: str) -> list[ActivoInfo]:
    activos = []
    for i in range(ACTIVOS_POR_PLANTA_SIMULADOS):
        tipo = _TIPOS_SIMULADOS[i % len(_TIPOS_SIMULADOS)]
        activos.append(ActivoInfo(
            activo_id=f"{planta_id}-{_PREFIJOS_SIMULADOS[tipo]}-{i + 1:02d}",
            planta_id=planta_id,
            tipo_activo=tipo,
            capacidad_nominal_kw=_CAPACIDAD_SIMULADA_KW[tipo],
        ))
    return activos


class ClienteInventarioSimulado:
    """Acepta cualquier id con el formato PL-001-PS-01 y deduce planta y tipo del propio id."""

    def obtener_activo(self, activo_id: str) -> ActivoInfo:
        partes = activo_id.rsplit("-", 2)
        planta_id = partes[0] if len(partes) == 3 else activo_id
        for activo in _activos_simulados(planta_id):
            if activo.activo_id == activo_id:
                return activo
        raise dependencia_fallida(EQUIPO_INVENTARIO, f"GET /activos/{activo_id} respondió 404 (simulado)",
                                  "Inventario de Activos no respondió como se esperaba.")

    def close(self) -> None:
        return None


class ClienteTelemetriaSimulado:
    """Lecturas cada 15 min, deterministas (misma entrada, mismos datos)."""

    def obtener_lecturas(self, planta_id: str, desde: datetime, hasta: datetime) -> LecturasPlanta:
        inicio = int(desde.timestamp()) // INTERVALO_SIMULADO_S * INTERVALO_SIMULADO_S
        if inicio < desde.timestamp():
            inicio += INTERVALO_SIMULADO_S
        instantes = np.arange(inicio, hasta.timestamp(), INTERVALO_SIMULADO_S, dtype=np.float64)
        if instantes.size == 0:
            return {}
        # Hora local del instante, según la zona horaria con que se pidió el rango
        desfase_h = desde.utcoffset().total_seconds() / 3600.0 if desde.utcoffset() else 0.0
        hora_local = ((instantes / 3600.0) + desfase_h) % 24.0

        resultado: LecturasPlanta = {}
        for activo in _activos_simulados(planta_id):
            semilla = abs(hash_estable(activo.activo_id)) % (2**32)
            rng = np.random.default_rng(semilla + int(inicio))
            if activo.tipo_activo == "panel_solar":
                perfil = np.sin(np.clip((hora_local - 6.0) / 12.0, 0.0, 1.0) * np.pi)
            elif activo.tipo_activo == "turbina_eolica":
                perfil = 0.45 + 0.25 * np.sin(hora_local / 3.0)
            else:
                perfil = 0.5 + 0.5 * np.sin(hora_local / 6.0)
            ruido = rng.normal(0.0, 0.03, size=instantes.shape[0])
            potencias = np.clip(activo.capacidad_nominal_kw * (perfil + ruido), 0.0, activo.capacidad_nominal_kw)
            resultado[activo.activo_id] = (instantes, potencias)
        return resultado

    def close(self) -> None:
        return None


def hash_estable(texto: str) -> int:
    """hash() de Python cambia entre ejecuciones; esto no, y así el modo simulado es reproducible."""
    valor = 5381
    for caracter in texto:
        valor = (valor * 33 + ord(caracter)) & 0xFFFFFFFF
    return valor


# ------------------------------------------------------------------ fuente de datos

@dataclass
class FuenteDatos:
    inventario: ClienteInventario
    telemetria: ClienteTelemetria

    def __enter__(self) -> FuenteDatos:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self.inventario.close()
        self.telemetria.close()

    def obtener_series(self, planta_ids: list[str], desde: datetime, hasta: datetime) -> list[SerieLecturas]:
        """Una SerieLecturas por activo con lecturas en el rango, lista para el motor de agregación."""
        activos: dict[str, ActivoInfo] = {}
        series: list[SerieLecturas] = []
        for planta_id in planta_ids:
            for activo_id, (instantes, potencias) in self.telemetria.obtener_lecturas(planta_id, desde, hasta).items():
                if activo_id not in activos:
                    activos[activo_id] = self.inventario.obtener_activo(activo_id)
                series.append(SerieLecturas(activo=activos[activo_id], timestamps_epoch=instantes,
                                            potencias_kw=potencias))
        return series


def crear_fuente(cfg: Configuracion = config, *, transporte_inventario: httpx.BaseTransport | None = None,
                 transporte_telemetria: httpx.BaseTransport | None = None) -> FuenteDatos:
    """Fuente simulada si MODO_SIMULADO=true; en otro caso, clientes httpx con las URLs del entorno."""
    if cfg.modo_simulado:
        log.info("MODO_SIMULADO activo: no se llamará a los Equipos 1 y 2")
        return FuenteDatos(ClienteInventarioSimulado(), ClienteTelemetriaSimulado())
    inventario = ClienteInventarioHttp(cfg.inventario_url, timeout_s=cfg.timeout_clientes_s,
                                       reintentos=cfg.reintentos_clientes, transporte=transporte_inventario)
    try:
        telemetria = ClienteTelemetriaHttp(cfg.telemetria_url, timeout_s=cfg.timeout_clientes_s,
                                           reintentos=cfg.reintentos_clientes, transporte=transporte_telemetria)
    except Exception:
        inventario.close()
        raise
    return FuenteDatos(inventario, telemetria)
