-- =============================================================================
-- Datos de ejemplo para el Avance 1: la API responde con agregados sin depender
-- todavía del motor Map-Reduce ni de los Equipos 1 y 2.
-- Se puede ejecutar varias veces: no duplica filas.
--   docker compose exec -T db-reportes psql -U "$DB_USER" -d reportes < db/datos_ejemplo.sql
-- =============================================================================

-- Una ejecución "secuencial" a la que quedan asociados los agregados de ejemplo
INSERT INTO ejecucion_calculo
    (request_id, equipo_consumidor, modo, workers, granularidad, nivel, planta_ids,
     desde, hasta, estado, elementos, generados, duracion_ms, iniciado_en, finalizado_en)
SELECT 'datos-de-ejemplo', NULL, 'secuencial', 1, 'dia', 'planta', 'PL-001,PL-002,PL-003',
       '2026-11-01T00:00:00-05:00', '2026-11-15T00:00:00-05:00', 'completado',
       40320, 63, 0, now(), now()
WHERE NOT EXISTS (SELECT 1 FROM ejecucion_calculo WHERE request_id = 'datos-de-ejemplo');

-- Plantas de ejemplo: capacidad nominal y factor de planta base
WITH plantas(planta_id, capacidad_kw, factor_base) AS (
    VALUES ('PL-001', 250.0, 0.30),
           ('PL-002', 400.0, 0.24),
           ('PL-003', 180.0, 0.34)
),
dias AS (
    SELECT generate_series(TIMESTAMPTZ '2026-11-01T00:00:00-05:00',
                           TIMESTAMPTZ '2026-11-14T00:00:00-05:00',
                           INTERVAL '1 day') AS inicio
),
calculo AS (
    SELECT p.planta_id, p.capacidad_kw, d.inicio,
           -- variación diaria determinista entre -0.05 y +0.05
           round((p.factor_base + 0.05 * sin(extract(day FROM d.inicio) * 1.7
                                            + length(p.planta_id)))::numeric, 4) AS factor
    FROM plantas p CROSS JOIN dias d
)
INSERT INTO agregado_generacion
    (planta_id, activo_id, tipo_activo, granularidad, periodo_inicio, periodo_fin,
     energia_kwh, potencia_promedio_kw, potencia_maxima_kw, numero_lecturas,
     capacidad_nominal_kw, factor_planta, ejecucion_id)
SELECT c.planta_id, NULL, NULL, 'dia', c.inicio, c.inicio + INTERVAL '1 day',
       round((c.capacidad_kw * 24 * c.factor)::numeric, 2),
       round((c.capacidad_kw * c.factor)::numeric, 2),
       round((c.capacidad_kw * least(0.95, c.factor * 2.8))::numeric, 2),
       960,                                   -- 10 activos x 96 lecturas de 15 min
       c.capacidad_kw, c.factor,
       (SELECT id FROM ejecucion_calculo WHERE request_id = 'datos-de-ejemplo')
FROM calculo c
ON CONFLICT ON CONSTRAINT uq_agregado_periodo DO NOTHING;

-- Algunos agregados por activo (paneles de PL-001) para probar el filtro activoId
WITH activos(activo_id, capacidad_kw) AS (
    VALUES ('PL-001-PS-01', 25.0), ('PL-001-PS-02', 25.0), ('PL-001-PS-03', 25.0)
),
dias AS (
    SELECT generate_series(TIMESTAMPTZ '2026-11-01T00:00:00-05:00',
                           TIMESTAMPTZ '2026-11-07T00:00:00-05:00',
                           INTERVAL '1 day') AS inicio
)
INSERT INTO agregado_generacion
    (planta_id, activo_id, tipo_activo, granularidad, periodo_inicio, periodo_fin,
     energia_kwh, potencia_promedio_kw, potencia_maxima_kw, numero_lecturas,
     capacidad_nominal_kw, factor_planta, ejecucion_id)
SELECT 'PL-001', a.activo_id, 'panel solar', 'dia', d.inicio, d.inicio + INTERVAL '1 day',
       round((a.capacidad_kw * 24 * 0.29)::numeric, 2),
       round((a.capacidad_kw * 0.29)::numeric, 2),
       round((a.capacidad_kw * 0.82)::numeric, 2),
       96, a.capacidad_kw, 0.29,
       (SELECT id FROM ejecucion_calculo WHERE request_id = 'datos-de-ejemplo')
FROM activos a CROSS JOIN dias d
ON CONFLICT ON CONSTRAINT uq_agregado_periodo DO NOTHING;

SELECT granularidad,
       count(*) FILTER (WHERE activo_id IS NULL)     AS por_planta,
       count(*) FILTER (WHERE activo_id IS NOT NULL) AS por_activo
FROM agregado_generacion
GROUP BY granularidad;
