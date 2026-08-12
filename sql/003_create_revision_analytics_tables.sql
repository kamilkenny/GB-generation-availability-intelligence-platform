-- =========================================================
-- UNIT-LEVEL AVAILABILITY REVISIONS
-- =========================================================

CREATE TABLE IF NOT EXISTS analytics.unit_availability_revision (
    previous_publish_time TIMESTAMPTZ NOT NULL,
    latest_publish_time TIMESTAMPTZ NOT NULL,
    forecast_date DATE NOT NULL,
    national_grid_bm_unit VARCHAR(100) NOT NULL,
    fuel_type VARCHAR(50) NOT NULL,

    previous_available_mw NUMERIC(12, 3) NOT NULL,
    latest_available_mw NUMERIC(12, 3) NOT NULL,
    revision_mw NUMERIC(12, 3) NOT NULL,
    absolute_revision_mw NUMERIC(12, 3) NOT NULL,

    change_direction VARCHAR(20) NOT NULL,
    became_unavailable BOOLEAN NOT NULL,
    returned_available BOOLEAN NOT NULL,

    CONSTRAINT pk_unit_availability_revision
        PRIMARY KEY (
            previous_publish_time,
            latest_publish_time,
            forecast_date,
            national_grid_bm_unit
        )
);


CREATE INDEX IF NOT EXISTS
    idx_unit_revision_forecast_date
ON analytics.unit_availability_revision (
    forecast_date
);


CREATE INDEX IF NOT EXISTS
    idx_unit_revision_fuel_type
ON analytics.unit_availability_revision (
    fuel_type
);


CREATE INDEX IF NOT EXISTS
    idx_unit_revision_absolute_revision
ON analytics.unit_availability_revision (
    absolute_revision_mw DESC
);


-- =========================================================
-- FUEL-LEVEL AVAILABILITY REVISIONS
-- =========================================================

CREATE TABLE IF NOT EXISTS analytics.fuel_availability_revision (
    previous_publish_time TIMESTAMPTZ NOT NULL,
    latest_publish_time TIMESTAMPTZ NOT NULL,
    forecast_date DATE NOT NULL,
    fuel_type VARCHAR(50) NOT NULL,

    previous_available_mw NUMERIC(14, 3) NOT NULL,
    latest_available_mw NUMERIC(14, 3) NOT NULL,
    revision_mw NUMERIC(14, 3) NOT NULL,

    changed_units INTEGER NOT NULL,
    became_unavailable_units INTEGER NOT NULL,
    returned_available_units INTEGER NOT NULL,

    CONSTRAINT pk_fuel_availability_revision
        PRIMARY KEY (
            previous_publish_time,
            latest_publish_time,
            forecast_date,
            fuel_type
        )
);


-- =========================================================
-- SYSTEM-LEVEL AVAILABILITY REVISIONS
-- =========================================================

CREATE TABLE IF NOT EXISTS analytics.system_availability_revision (
    previous_publish_time TIMESTAMPTZ NOT NULL,
    latest_publish_time TIMESTAMPTZ NOT NULL,
    forecast_date DATE NOT NULL,

    previous_available_mw NUMERIC(14, 3) NOT NULL,
    latest_available_mw NUMERIC(14, 3) NOT NULL,
    revision_mw NUMERIC(14, 3) NOT NULL,

    changed_units INTEGER NOT NULL,
    became_unavailable_units INTEGER NOT NULL,
    returned_available_units INTEGER NOT NULL,

    CONSTRAINT pk_system_availability_revision
        PRIMARY KEY (
            previous_publish_time,
            latest_publish_time,
            forecast_date
        )
);
