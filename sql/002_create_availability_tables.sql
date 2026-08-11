-- =========================================================
-- RAW LAYER
-- =========================================================

CREATE TABLE IF NOT EXISTS raw.uou2t14d (
    national_grid_bm_unit VARCHAR(100) NOT NULL,
    bm_unit VARCHAR(100),
    fuel_type VARCHAR(50) NOT NULL,
    publish_time TIMESTAMPTZ NOT NULL,
    forecast_date DATE NOT NULL,
    output_usable_mw NUMERIC(12, 3) NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL,
    dataset VARCHAR(20) NOT NULL DEFAULT 'UOU2T14D',

    CONSTRAINT pk_raw_uou2t14d
        PRIMARY KEY (
            national_grid_bm_unit,
            publish_time,
            forecast_date
        )
);


CREATE INDEX IF NOT EXISTS idx_raw_uou2t14d_publish_time
    ON raw.uou2t14d (publish_time);

CREATE INDEX IF NOT EXISTS idx_raw_uou2t14d_forecast_date
    ON raw.uou2t14d (forecast_date);

CREATE INDEX IF NOT EXISTS idx_raw_uou2t14d_fuel_type
    ON raw.uou2t14d (fuel_type);


-- =========================================================
-- SILVER LAYER — FUEL AVAILABILITY
-- =========================================================

CREATE TABLE IF NOT EXISTS silver.fuel_availability (
    publish_time TIMESTAMPTZ NOT NULL,
    forecast_date DATE NOT NULL,
    fuel_type VARCHAR(50) NOT NULL,
    available_mw NUMERIC(14, 3) NOT NULL,
    bm_units INTEGER NOT NULL,
    zero_availability_units INTEGER NOT NULL,

    CONSTRAINT pk_silver_fuel_availability
        PRIMARY KEY (
            publish_time,
            forecast_date,
            fuel_type
        )
);


-- =========================================================
-- SILVER LAYER — SYSTEM AVAILABILITY
-- =========================================================

CREATE TABLE IF NOT EXISTS silver.system_availability (
    publish_time TIMESTAMPTZ NOT NULL,
    forecast_date DATE NOT NULL,
    total_available_mw NUMERIC(14, 3) NOT NULL,
    bm_units INTEGER NOT NULL,
    zero_availability_units INTEGER NOT NULL,

    CONSTRAINT pk_silver_system_availability
        PRIMARY KEY (
            publish_time,
            forecast_date
        )
);


-- =========================================================
-- GOVERNANCE — INGESTION RUNS
-- =========================================================

CREATE TABLE IF NOT EXISTS governance.pipeline_run (
    pipeline_run_id BIGSERIAL PRIMARY KEY,
    pipeline_name VARCHAR(100) NOT NULL,
    source_dataset VARCHAR(50) NOT NULL,
    source_publish_time TIMESTAMPTZ,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    rows_processed INTEGER,
    status VARCHAR(30) NOT NULL,
    error_message TEXT
);
