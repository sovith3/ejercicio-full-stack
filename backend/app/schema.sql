-- Esquema del servicio de lecturas.
-- Todo el DDL es idempotente: se ejecuta al arrancar la API y en cada carga.

-- Un registro por archivo procesado: es la memoria de la idempotencia.
CREATE TABLE IF NOT EXISTS loads (
    id                    BIGSERIAL   PRIMARY KEY,
    file_name             TEXT        NOT NULL,
    file_hash             TEXT        NOT NULL UNIQUE,   -- sha256 del contenido
    rows_read             INTEGER     NOT NULL,
    rows_valid            INTEGER     NOT NULL,
    rows_inserted         INTEGER     NOT NULL DEFAULT 0,
    rows_updated          INTEGER     NOT NULL DEFAULT 0,
    rows_rejected         INTEGER     NOT NULL,
    rows_without_position INTEGER     NOT NULL DEFAULT 0,
    rejections            JSONB       NOT NULL DEFAULT '{}'::jsonb, -- motivo -> cantidad
    loaded_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Padrón de dispositivos: permite distinguir "no existe" (404) de "existe sin
-- lecturas ese día" (200 con readings: 0).
CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY      -- normalizado: sin espacios y en mayúsculas
);

-- Una fila por dispositivo e instante: la llave primaria materializa la regla
-- "la última lectura recibida gana". `load_id` guarda el orden de llegada, así
-- que un archivo posterior siempre pisa a uno anterior y recargar el mismo
-- archivo (mismo hash) no cambia nada.
CREATE TABLE IF NOT EXISTS readings (
    device_id   TEXT             NOT NULL REFERENCES devices (device_id) ON DELETE CASCADE,
    recorded_at TIMESTAMPTZ      NOT NULL,
    value       DOUBLE PRECISION,          -- NULL = "sin dato", no promedia
    lat         DOUBLE PRECISION,          -- NULL = "sin posición", no se dibuja
    lon         DOUBLE PRECISION,
    load_id     BIGINT           NOT NULL REFERENCES loads (id),
    PRIMARY KEY (device_id, recorded_at)
);

CREATE INDEX IF NOT EXISTS readings_load_id_idx ON readings (load_id);

COMMENT ON TABLE readings IS 'Lecturas deduplicadas por (device_id, recorded_at).';
