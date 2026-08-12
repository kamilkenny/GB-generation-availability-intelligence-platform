CREATE SCHEMA IF NOT EXISTS gold;


-- =========================================================
-- LATEST AVAILABILITY OUTLOOK
-- Separates interconnectors from GB generation/storage.
-- =========================================================

CREATE OR REPLACE VIEW gold.latest_availability_outlook AS
WITH latest_publication AS (
    SELECT MAX(publish_time) AS publish_time
    FROM silver.fuel_availability
)
SELECT
    f.publish_time,
    f.forecast_date,

    SUM(f.available_mw) AS total_available_mw,

    SUM(
        CASE
            WHEN f.fuel_type LIKE 'INT%'
            THEN f.available_mw
            ELSE 0
        END
    ) AS interconnector_available_mw,

    SUM(
        CASE
            WHEN f.fuel_type NOT LIKE 'INT%'
            THEN f.available_mw
            ELSE 0
        END
    ) AS gb_generation_storage_available_mw,

    SUM(f.bm_units) AS bm_unit_records,

    SUM(f.zero_availability_units)
        AS zero_availability_units

FROM silver.fuel_availability AS f

JOIN latest_publication AS lp
    ON f.publish_time = lp.publish_time

GROUP BY
    f.publish_time,
    f.forecast_date;


-- =========================================================
-- LATEST SYSTEM REVISION
-- Most recent publication-to-publication comparison.
-- =========================================================

CREATE OR REPLACE VIEW gold.latest_system_revision AS
WITH latest_pair AS (
    SELECT
        previous_publish_time,
        latest_publish_time
    FROM analytics.system_availability_revision
    ORDER BY latest_publish_time DESC
    LIMIT 1
)
SELECT
    r.previous_publish_time,
    r.latest_publish_time,
    r.forecast_date,
    r.previous_available_mw,
    r.latest_available_mw,
    r.revision_mw,
    r.changed_units,
    r.became_unavailable_units,
    r.returned_available_units

FROM analytics.system_availability_revision AS r

JOIN latest_pair AS p
    ON r.previous_publish_time =
       p.previous_publish_time
   AND r.latest_publish_time =
       p.latest_publish_time;


-- =========================================================
-- LATEST CHANGED BM UNITS
-- Only units whose availability actually changed.
-- =========================================================

CREATE OR REPLACE VIEW gold.latest_changed_units AS
WITH latest_pair AS (
    SELECT
        previous_publish_time,
        latest_publish_time
    FROM analytics.unit_availability_revision
    ORDER BY latest_publish_time DESC
    LIMIT 1
)
SELECT
    r.previous_publish_time,
    r.latest_publish_time,
    r.forecast_date,
    r.national_grid_bm_unit,
    r.fuel_type,
    r.previous_available_mw,
    r.latest_available_mw,
    r.revision_mw,
    r.absolute_revision_mw,
    r.change_direction,
    r.became_unavailable,
    r.returned_available

FROM analytics.unit_availability_revision AS r

JOIN latest_pair AS p
    ON r.previous_publish_time =
       p.previous_publish_time
   AND r.latest_publish_time =
       p.latest_publish_time

WHERE r.revision_mw <> 0;


-- =========================================================
-- PIPELINE HEALTH
-- Latest governed execution.
-- =========================================================

CREATE OR REPLACE VIEW gold.pipeline_health AS
SELECT
    pipeline_run_id,
    pipeline_name,
    source_dataset,
    source_publish_time,
    rows_processed,
    status,
    started_at,
    completed_at,
    error_message,

    EXTRACT(
        EPOCH FROM (
            completed_at - started_at
        )
    ) AS duration_seconds

FROM governance.pipeline_run

ORDER BY pipeline_run_id DESC

LIMIT 1;
