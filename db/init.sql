-- =============================================================================
-- Voltrix Energy · Equipo 4 · Reportes de Generación
-- Creación de las tablas. PostgreSQL lo ejecuta una sola vez, al crear el volumen
-- (docker-entrypoint-initdb.d). Si cambia, hay que recrear el volumen:
--   docker compose down -v && docker compose up -d
-- =============================================================================

-- Cada llamada a POST /reportes/generar deja un registro aquí, haya salido bien o no.
CREATE TABLE IF NOT EXISTS ejecucion_calculo (
    id                 BIGSERIAL    PRIMARY KEY,
    request_id         VARCHAR(64)  NOT NULL,
    equipo_consumidor  VARCHAR(16),
    modo               VARCHAR(10)  NOT NULL CHECK (modo IN ('secuencial', 'paralelo')),
    workers            INTEGER      NOT NULL CHECK (workers >= 1),
    granularidad       VARCHAR(4)   NOT NULL CHECK (granularidad IN ('hora', 'dia', 'mes')),
    nivel              VARCHAR(6)   NOT NULL CHECK (nivel IN ('planta', 'activo')),
    planta_ids         TEXT,                      -- IDs separados por coma; NULL = todas
    desde              TIMESTAMPTZ  NOT NULL,
    hasta              TIMESTAMPTZ  NOT NULL,
    estado             VARCHAR(12)  NOT NULL DEFAULT 'en_curso'
                                    CHECK (estado IN ('en_curso', 'completado', 'error')),
    elementos          INTEGER      CHECK (elementos >= 0),
    generados          INTEGER      CHECK (generados >= 0),
    duracion_ms        INTEGER      CHECK (duracion_ms >= 0),
    mensaje_error      TEXT,
    iniciado_en        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    finalizado_en      TIMESTAMPTZ,
    CHECK (hasta > desde)
);

CREATE INDEX IF NOT EXISTS ix_ejecucion_iniciado_en ON ejecucion_calculo (iniciado_en DESC);

-- Agregados de energía por planta (activo_id NULL) o por activo, y por periodo.
-- Los campos siguen el esquema AgregadoGeneracion de openapi.yaml.
CREATE TABLE IF NOT EXISTS agregado_generacion (
    id                    BIGSERIAL         PRIMARY KEY,
    planta_id             VARCHAR(64)       NOT NULL,
    activo_id             VARCHAR(64),
    tipo_activo           VARCHAR(32),
    granularidad          VARCHAR(4)        NOT NULL CHECK (granularidad IN ('hora', 'dia', 'mes')),
    periodo_inicio        TIMESTAMPTZ       NOT NULL,
    periodo_fin           TIMESTAMPTZ       NOT NULL,
    energia_kwh           DOUBLE PRECISION  NOT NULL CHECK (energia_kwh >= 0),
    potencia_promedio_kw  DOUBLE PRECISION,
    potencia_maxima_kw    DOUBLE PRECISION,
    numero_lecturas       INTEGER           NOT NULL CHECK (numero_lecturas >= 0),
    capacidad_nominal_kw  DOUBLE PRECISION,
    factor_planta         DOUBLE PRECISION,
    generado_en           TIMESTAMPTZ       NOT NULL DEFAULT now(),
    ejecucion_id          BIGINT            REFERENCES ejecucion_calculo (id) ON DELETE SET NULL,
    CHECK (periodo_fin > periodo_inicio),
    -- Un solo agregado por (planta, activo, granularidad, periodo). NULLS NOT DISTINCT hace
    -- que dos agregados de planta (activo_id NULL) del mismo periodo también choquen.
    CONSTRAINT uq_agregado_periodo
        UNIQUE NULLS NOT DISTINCT (planta_id, activo_id, granularidad, periodo_inicio)
);

-- Consultas de GET /reportes/generacion: por planta o por activo, granularidad y fechas.
CREATE INDEX IF NOT EXISTS ix_agregado_planta
    ON agregado_generacion (planta_id, granularidad, periodo_inicio);
CREATE INDEX IF NOT EXISTS ix_agregado_activo
    ON agregado_generacion (activo_id, granularidad, periodo_inicio)
    WHERE activo_id IS NOT NULL;
