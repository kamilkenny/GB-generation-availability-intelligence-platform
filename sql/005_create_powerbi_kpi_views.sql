-- =========================================================
-- LATEST AVAILABILITY MIX
-- Dashboard-ready capacity split and percentages.
-- =========================================================

CREATE OR REPLACE VIEW gold.latest_availability_mix AS
SELECT
    publish_time,
    forecast_date,

    total_available_mw,
    gb_generation_storage_available_mw,
    interconnector_available_mw,

    ROUND(
        (
            gb_generation_storage_available_mw
            / NULLIF(total_available_mw, 0)
        ) * 100,
        2
    ) AS gb_generation_storage_pct,

    ROUND(
        (
            interconnector_available_mw
            / NULLIF(total_available_mw, 0)
        ) * 100,
        2
    ) AS interconnector_pct,

    zero_availability_units

FROM gold.latest_availability_outlook;


-- =========================================================
-- LATEST FUEL REVISION RANKING
-- Ranks fuel types by absolute availability revision.
-- =========================================================

CREATE OR REPLACE VIEW gold.latest_fuel_revision_ranking AS
WITH latest_pair AS (
    SELECT
        previous_publish_time,
        latest_publish_time
    FROM analytics.fuel_availability_revision
    ORDER BY latest_publish_time DESC
    LIMIT 1
),
latest_revisions AS (
    SELECT
        r.previous_publish_time,
        r.latest_publish_time,
        r.forecast_date,
        r.fuel_type,
        r.previous_available_mw,
        r.latest_available_mw,
        r.revision_mw,
        ABS(r.revision_mw)
            AS absolute_revision_mw,
        r.changed_units,
        r.became_unavailable_units,
        r.returned_available_units

    FROM analytics.fuel_availability_revision AS r

    JOIN latest_pair AS p
        ON r.previous_publish_time =
           p.previous_publish_time
       AND r.latest_publish_time =
           p.latest_publish_time

    WHERE r.revision_mw <> 0
)
SELECT
    *,
    ROW_NUMBER() OVER (
        PARTITION BY forecast_date
        ORDER BY
            absolute_revision_mw DESC,
            fuel_type
    ) AS revision_rank

FROM latest_revisions;


-- =========================================================
-- LATEST UNIT REVISION RANKING
-- Ranks changed BM Units by absolute impact.
-- =========================================================

CREATE OR REPLACE VIEW gold.latest_unit_revision_ranking AS
SELECT
    previous_publish_time,
    latest_publish_time,
    forecast_date,
    national_grid_bm_unit,
    fuel_type,
    previous_available_mw,
    latest_available_mw,
    revision_mw,
    absolute_revision_mw,
    change_direction,
    became_unavailable,
    returned_available,

    ROW_NUMBER() OVER (
        PARTITION BY forecast_date
        ORDER BY
            absolute_revision_mw DESC,
            national_grid_bm_unit
    ) AS revision_rank

FROM gold.latest_changed_units;


-- =========================================================
-- EXECUTIVE DASHBOARD KPI SNAPSHOT
-- One row for Power BI headline cards.
-- =========================================================

CREATE OR REPLACE VIEW gold.dashboard_kpis AS
WITH availability AS (
    SELECT
        MAX(publish_time)
            AS latest_publish_time,

        MIN(forecast_date)
            AS forecast_start_date,

        MAX(forecast_date)
            AS forecast_end_date,

        MIN(total_available_mw)
            AS minimum_total_available_mw,

        MAX(total_available_mw)
            AS maximum_total_available_mw,

        MIN(
            gb_generation_storage_available_mw
        ) AS minimum_gb_generation_storage_mw,

        AVG(
            interconnector_available_mw
        ) AS average_interconnector_available_mw

    FROM gold.latest_availability_outlook
),

lowest_day AS (
    SELECT
        forecast_date
            AS lowest_availability_date,
        total_available_mw
            AS lowest_availability_mw

    FROM gold.latest_availability_outlook

    ORDER BY
        total_available_mw ASC,
        forecast_date ASC

    LIMIT 1
),

revision_summary AS (
    SELECT
        COUNT(*) AS changed_unit_rows,

        COUNT(*) FILTER (
            WHERE change_direction = 'UP'
        ) AS upward_revision_rows,

        COUNT(*) FILTER (
            WHERE change_direction = 'DOWN'
        ) AS downward_revision_rows,

        COUNT(*) FILTER (
            WHERE became_unavailable
        ) AS became_unavailable_rows,

        COUNT(*) FILTER (
            WHERE returned_available
        ) AS returned_available_rows

    FROM gold.latest_changed_units
),

largest_revision AS (
    SELECT
        forecast_date
            AS largest_system_revision_date,

        revision_mw
            AS largest_system_revision_mw

    FROM gold.latest_system_revision

    ORDER BY
        ABS(revision_mw) DESC,
        forecast_date ASC

    LIMIT 1
),

pipeline AS (
    SELECT
        pipeline_run_id,
        status AS pipeline_status,
        duration_seconds
    FROM gold.pipeline_health
)

SELECT
    a.latest_publish_time,
    a.forecast_start_date,
    a.forecast_end_date,

    ld.lowest_availability_date,
    ld.lowest_availability_mw,

    a.minimum_total_available_mw,
    a.maximum_total_available_mw,
    a.minimum_gb_generation_storage_mw,

    ROUND(
        a.average_interconnector_available_mw,
        2
    ) AS average_interconnector_available_mw,

    rs.changed_unit_rows,
    rs.upward_revision_rows,
    rs.downward_revision_rows,
    rs.became_unavailable_rows,
    rs.returned_available_rows,

    lr.largest_system_revision_date,
    lr.largest_system_revision_mw,

    p.pipeline_run_id,
    p.pipeline_status,

    ROUND(
        p.duration_seconds,
        3
    ) AS pipeline_duration_seconds

FROM availability AS a

CROSS JOIN lowest_day AS ld
CROSS JOIN revision_summary AS rs
CROSS JOIN largest_revision AS lr
CROSS JOIN pipeline AS p;
