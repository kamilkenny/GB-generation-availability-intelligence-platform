from datetime import datetime

import pytest
from pyspark.sql import SparkSession

from src.pipeline.spark_availability_pipeline import (
    build_analytical_datasets,
    write_analytical_outputs,
)


@pytest.fixture(scope="module")
def spark():
    session = (
        SparkSession.builder
        .master("local[2]")
        .appName("test-spark-pipeline")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )

    session.sparkContext.setLogLevel("ERROR")

    yield session

    session.stop()


def sample_dataframe(spark):
    publish_00 = datetime(2026, 8, 12, 0, 0)
    publish_01 = datetime(2026, 8, 12, 1, 0)
    forecast = datetime(2026, 8, 14, 0, 0)
    collected = datetime(2026, 8, 12, 2, 0)

    rows = [
        {
            "dataset": "UOU2T14D",
            "fuelType": "CCGT",
            "nationalGridBmUnit": "UNIT-A",
            "bmUnit": "T_UNIT-A",
            "publishTime": publish_00,
            "forecastDate": forecast,
            "outputUsable": 100,
            "collectedAt": collected,
        },
        {
            "dataset": "UOU2T14D",
            "fuelType": "WIND",
            "nationalGridBmUnit": "UNIT-B",
            "bmUnit": "T_UNIT-B",
            "publishTime": publish_00,
            "forecastDate": forecast,
            "outputUsable": 50,
            "collectedAt": collected,
        },
        {
            "dataset": "UOU2T14D",
            "fuelType": "CCGT",
            "nationalGridBmUnit": "UNIT-A",
            "bmUnit": "T_UNIT-A",
            "publishTime": publish_01,
            "forecastDate": forecast,
            "outputUsable": 110,
            "collectedAt": collected,
        },
        {
            "dataset": "UOU2T14D",
            "fuelType": "WIND",
            "nationalGridBmUnit": "UNIT-B",
            "bmUnit": "T_UNIT-B",
            "publishTime": publish_01,
            "forecastDate": forecast,
            "outputUsable": 50,
            "collectedAt": collected,
        },
    ]

    return spark.createDataFrame(rows)


def test_build_analytical_datasets(spark):
    raw_df = sample_dataframe(spark)

    datasets = build_analytical_datasets(raw_df)

    counts = {
        name: dataframe.count()
        for name, dataframe in datasets.items()
    }

    assert counts == {
        "fuel_availability_history": 4,
        "system_availability_history": 2,
        "unit_revision_history": 2,
        "fuel_revision_history": 2,
        "system_revision_history": 1,
    }


def test_write_outputs_is_idempotent(
    spark,
    tmp_path,
):
    raw_df = sample_dataframe(spark)

    datasets = build_analytical_datasets(raw_df)

    output_directory = (
        tmp_path
        / "spark"
        / "uou2t14d"
    )

    write_analytical_outputs(
        datasets,
        output_directory=output_directory,
    )

    first_counts = {
        name: spark.read.parquet(
            str(output_directory / name)
        ).count()
        for name in datasets
    }

    write_analytical_outputs(
        datasets,
        output_directory=output_directory,
    )

    second_counts = {
        name: spark.read.parquet(
            str(output_directory / name)
        ).count()
        for name in datasets
    }

    expected = {
        "fuel_availability_history": 4,
        "system_availability_history": 2,
        "unit_revision_history": 2,
        "fuel_revision_history": 2,
        "system_revision_history": 1,
    }

    assert first_counts == expected
    assert second_counts == expected
