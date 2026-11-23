# Voltrix Energy · Equipo 4 · Reportes de Generación

Este repositorio contiene el servicio de **Reportes de Generación** de la plataforma Voltrix Energy, el proyecto del curso Infraestructuras Paralelas y Distribuidas de la Universidad del Valle (2026-2).

El servicio toma la telemetría de potencia de las plantas y calcula la energía generada por planta, por activo y por periodo: hora, día o mes. El cálculo se hace con una versión secuencial y con otra paralela, que usa un **Map-Reduce simplificado**, y los agregados se exponen en una API REST que consumen otros equipos.

- **Contrato OpenAPI (documentación):** https://carlossvillamil.github.io/voltrix-reportes-generacion/
- **Archivo del contrato:** https://carlossvillamil.github.io/voltrix-reportes-generacion/openapi.yaml

## Integrantes

| Integrante | Responsabilidad principal |
| --- | --- |
| Carlos Manuel Villamil Grisales | Coordinación, arquitectura, contrato OpenAPI y capa de presentación |
| Tiffany Torres Figueroa | Motor de agregación secuencial y paralelo (Map-Reduce) y benchmarks |
| Sebastián Saldaña Olmos | Capa de acceso a datos, PostgreSQL y docker-compose en EC2 |
| Hector Daniel Carabali Valencia | Clúster Floci EKS, manifiestos de Kubernetes e IaC |
| Camilo Riscanevo | Clientes hacia los Equipos 1 y 2, pruebas de integración y directorio de servicios |

## Integración con otros equipos

| Dirección | Equipo | Servicio | Operación |
| --- | --- | --- | --- |
| Consumimos | 1 | Inventario de Activos | `GET /activos/{id}`: capacidad nominal y tipo de cada activo |
| Consumimos | 2 | Telemetría de Plantas | `GET /telemetria/{plantaId}`: lecturas de potencia |
| Nos consume | 5 | Pronóstico de Generación | `GET /reportes/generacion` |
| Nos consume | 6 | Mantenimiento Predictivo | `GET /reportes/generacion` |
| Nos consume | 7 | Facturación y Liquidación | `GET /reportes/generacion` |

En cada llamada entre servicios se envían las cabeceras `X-Equipo-Consumidor: equipo-<N>` y `X-Request-Id`, y ambas se registran en los logs.

## Endpoints

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/reportes/generacion` | Consulta los agregados, con filtros por planta, activo, fechas y granularidad, y paginación `limit`/`offset` |
| POST | `/reportes/generar` | Calcula los agregados de un rango de hasta 31 días. Acepta `modo` (`secuencial` \| `paralelo`) y `workers`, y devuelve `MetricasProcesamiento` |
| GET | `/health` | Estado del servicio y de la base de datos |
| GET | `/openapi.yaml` | Contrato del servicio |

El detalle completo está en [`openapi.yaml`](openapi.yaml).

## Tecnologías

- Python 3.12, FastAPI y Uvicorn
- Pydantic, SQLAlchemy 2 y psycopg 3
- httpx para los clientes de los Equipos 1 y 2
- NumPy y `ProcessPoolExecutor` para el Map-Reduce
- PostgreSQL 16 (alpine)
- Docker y docker-compose en EC2, y Kubernetes en Floci EKS

## Estructura del repositorio

```
app/
  api/            capa de presentación (rutas y esquemas Pydantic)
  services/       capa de negocio (Map-Reduce, admisión y clientes de los Equipos 1 y 2)
  repositories/   capa de acceso a datos
benchmark/        generador de datos sintéticos y scripts de medición
tests/            pruebas unitarias y de integración
db/               script de creación de la base de datos (init.sql)
k8s/              manifiestos para Floci EKS
infra/            IaC de la instancia EC2 y del clúster
docker-compose.yml
openapi.yaml
index.html        página del contrato publicada en GitHub Pages
```

## Ejecución local

> Estado del Avance 1: los cuatro endpoints responden según el contrato. `POST /reportes/generar` registra la ejecución, pero todavía no calcula (devuelve `generados: 0`); el Map-Reduce y los clientes de los Equipos 1 y 2 llegan en el Avance 2.

1. Crear un archivo `.env` en la raíz con estas variables (no se sube al repositorio):

   ```
   DB_USER=reportes
   DB_PASSWORD=<contraseña>
   INVENTARIO_URL=http://<host-equipo-1>:<puerto>
   TELEMETRIA_URL=http://<host-equipo-2>:<puerto>
   ```

2. Levantar los servicios:

   ```
   docker compose up -d --build
   ```

3. Cargar los datos de ejemplo (se puede repetir, no duplica filas):

   ```
   docker compose exec -T db-reportes sh -c 'psql -U "$POSTGRES_USER" -d reportes' < db/datos_ejemplo.sql
   ```

4. Comprobar que responde:

   ```
   curl http://localhost:8080/health
   curl "http://localhost:8080/reportes/generacion?plantaId=PL-001&limit=5" -H "X-Equipo-Consumidor: equipo-5"
   ```

La API queda publicada en el puerto **8080**. La base de datos no publica puertos: solo se puede llegar a ella desde la red interna `voltrix-reportes-net`.

## Pruebas

```
python -m venv .venv
.venv\Scripts\activate          # en Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest
```

`tests/test_api.py` no necesita base de datos. `tests/test_repositorios.py` se omite si no está definida `TEST_DATABASE_URL` (ver el encabezado del archivo).

## Ver el contrato en local

La página `index.html` carga `openapi.yaml` por HTTP, así que no funciona si se abre con doble clic. Se puede servir con:

```
python -m http.server 8765
```

y abrir http://localhost:8765.

## Cronograma

| Fecha | Entrega | Contenido |
| --- | --- | --- |
| 19 nov 2026 | Diseño y contrato | Informe de diseño y archivo OpenAPI |
| 26 nov 2026 | Avance 1 | API en EC2 con datos de ejemplo, clúster en Floci EKS y registro en el directorio de servicios |
| 3 dic 2026 | Avance 2 | Versiones secuencial y paralela, benchmark preliminar, 2 réplicas en Floci EKS y consumo real de los Equipos 1 y 2 |
| 16 dic 2026 | Entrega final | Sistema completo, IaC, benchmark final con gráficas y sustentación |

## Forma de trabajo

- Cada integrante trabaja en su propia rama y abre un pull request hacia `main`.
- Ningún pull request se integra sin la revisión de otro integrante.
- Los cambios en `openapi.yaml` se avisan antes al grupo y a los equipos que nos consumen.
