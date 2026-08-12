from datetime import datetime

import pytest
from pyspark.sql import SparkSession

from src.analytics.spark_availability import (
    build_aggregate_revision_history,
    build_fuel_availability_history,
    build_system_availability_history,
    build_unit_revision_history,
    validate_canonical_history,
)


@pytest.fixture(scope="module")
def spark():
    """Provide one local Spark session for this test module."""

    session = (
        SparkSession.builder
        .master("local[2]")
        .appName("test-spark-availability")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )

    session.sparkContext.setLogLevel("ERROR")

    yield session

    session.stop()


def canonical_rows():
    """Create two synthetic availability publications."""

    publish_00 = datetime(2026, 8, 12, 0, 0)
    publish_01 = datetime(2026, 8, 12, 1, 0)

    forecast_date = datetime(2026, 8, 14, 0, 0)
    collected_at = datetime(2026, 8, 12, 2, 0)

    return [
        {
            "dataset": "UOU2T14D",
            "fuelType": "CCGT",
            "nationalGridBmUnit": "UNIT-A",
            "bmUnit": "T_UNIT-A",
            "publishTime": publish_00,
            "forecastDate": forecast_date,
            "outputUsable": 100,
            "collectedAt": collected_at,
        },
        {
            "dataset": "UOU2T14D",
            "fuelType": "CCGT",
            "nationalGridBmUnit": "UNIT-B",
            "bmUnit": "T_UNIT-B",
            "publishTime": publish_00,
            "forecastDate": forecast_date,
            "outputUsable": 50,
            "collectedAt": collected_at,
        },
        {
            "dataset": "UOU2T14D",
            "fuelType": "WIND",
            "nationalGridBmUnit": "UNIT-C",
            "bmUnit": "T_UNIT-C",
            "publishTime": publish_00,
            "forecastDate": forecast_date,
            "outputUsable": 30,
            "collectedAt": collected_at,
        },
        {
            "dataset": "UOU2T14D",
            "fuelType": "CCGT",
            "nationalGridBmUnit": "UNIT-A",
            "bmUnit": "T_UNIT-A",
            "publishTime": publish_01,
            "forecastDate": forecast_date,
            "outputUsable": 110,
            "collectedAt": collected_at,
        },
        {
            "dataset": "UOU2T14D",
            "fuelType": "OCGT",
            "nationalGridBmUnit": "UNIT-B",
            "bmUnit": "T_UNIT-B",
            "publishTime": publish_01,
            "forecastDate": forecast_date,
            "outputUsable": 40,
            "collectedAt": collected_at,
        },
        {
            "dataset": "UOU2T14D",
            "fuelType": "WIND",
            "nationalGridBmUnit": "UNIT-C",
            "bmUnit": "T_UNIT-C",
            "publishTime": publish_01,
            "forecastDate": forecast_date,
            "outputUsable": 30,
            "collectedAt": collected_at,
        },
    ]


def canonical_dataframe(spark):
    return spark.createDataFrame(canonical_rows())


def test_validate_canonical_history_accepts_clean_data(spark):
    df = canonical_dataframe(spark)

    result = validate_canonical_history(df)

    assert result == {
        "rows": 6,
        "publications": 2,
        "duplicate_source_keys": 0,
        "null_national_grid_bm_units": 0,
        "null_publish_times": 0,
        "null_forecast_dates": 0,
        "null_output_usable": 0,
    }


def test_validate_canonical_history_requires_columns(spark):
    df = spark.createDataFrame(
        [{"dataset": "UOU2T14D"}]
    )

    with pytest.raises(
        ValueError,
        match="Missing canonical columns",
    ):
        validate_canonical_history(df)


def test_validate_canonical_history_detects_duplicate_keys(spark):
    rows = canonical_rows()
    rows.append(dict(rows[0]))

    df = spark.createDataFrame(rows)

    with pytest.raises(
        ValueError,
        match="Canonical Spark quality checks failed",
    ):
        validate_canonical_history(df)


def test_build_availability_histories(spark):
    df = canonical_dataframe(spark)

    fuel_history = build_fuel_availability_history(df)
    system_history = build_system_availability_history(df)

    assert fuel_history.count() == 5
    assert system_history.count() == 2

    system_values = sorted(
        row.availableMW
        for row in system_history.collect()
    )

    assert system_values == [180, 180]

    first_ccgt = (
        fuel_history
        .filter(
            (fuel_history.publishTime ==
             datetime(2026, 8, 12, 0, 0))
            & (fuel_history.fuelType == "CCGT")
        )
        .collect()[0]
    )

    assert first_ccgt.availableMW == 150


def test_build_unit_revision_history_tracks_changes(spark):
    df = canonical_dataframe(spark)

    revisions = build_unit_revision_history(df)

    assert revisions.count() == 3

    rows = {
        row.nationalGridBmUnit: row
        for row in revisions.collect()
    }

    assert rows["UNIT-A"].revisionMW == 10
    assert rows["UNIT-A"].revisionDirection == "up"
    assert rows["UNIT-A"].fuelTypeChanged is False

    assert rows["UNIT-B"].revisionMW == -10
    assert rows["UNIT-B"].revisionDirection == "down"
    assert rows["UNIT-B"].previousFuelType == "CCGT"
    assert rows["UNIT-B"].fuelType == "OCGT"
    assert rows["UNIT-B"].fuelTypeChanged is True

    assert rows["UNIT-C"].revisionMW == 0
    assert rows["UNIT-C"].revisionDirection == "unchanged"


def test_build_aggregate_revision_history(spark):
    df = canonical_dataframe(spark)

    system_history = build_system_availability_history(df)

    revisions = build_aggregate_revision_history(
        system_history,
        ["forecastDate"],
    )

    assert revisions.count() == 1

    row = revisions.collect()[0]

    assert row.previousAvailableMW == 180
    assert row.latestAvailableMW == 180
    assert row.revisionMW == 0
    assert row.revisionDirection == "unchanged"
