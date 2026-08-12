from __future__ import annotations

from pathlib import Path

from pyspark.sql import DataFrame, SparkSession

from config.settings import PROCESSED_DATA_DIR
from src.analytics.spark_availability import (
    RAW_DIRECTORY,
    build_aggregate_revision_history,
    build_fuel_availability_history,
    build_system_availability_history,
    build_unit_revision_history,
    create_spark_session,
    read_canonical_history,
    validate_canonical_history,
)


SPARK_OUTPUT_DIRECTORY = (
    PROCESSED_DATA_DIR
    / "spark"
    / "uou2t14d"
)


def build_analytical_datasets(
    raw_df: DataFrame,
) -> dict[str, DataFrame]:
    """Build all Spark analytical availability datasets."""

    fuel_history = (
        build_fuel_availability_history(
            raw_df
        )
    )

    system_history = (
        build_system_availability_history(
            raw_df
        )
    )

    unit_revisions = (
        build_unit_revision_history(
            raw_df
        )
    )

    fuel_revisions = (
        build_aggregate_revision_history(
            fuel_history,
            [
                "fuelType",
                "forecastDate",
            ],
        )
    )

    system_revisions = (
        build_aggregate_revision_history(
            system_history,
            ["forecastDate"],
        )
    )

    return {
        "fuel_availability_history":
            fuel_history,
        "system_availability_history":
            system_history,
        "unit_revision_history":
            unit_revisions,
        "fuel_revision_history":
            fuel_revisions,
        "system_revision_history":
            system_revisions,
    }


def write_analytical_outputs(
    datasets: dict[str, DataFrame],
    output_directory: Path = SPARK_OUTPUT_DIRECTORY,
) -> dict[str, Path]:
    """Persist Spark analytical datasets as Parquet."""

    output_paths = {}

    for name, dataframe in datasets.items():
        output_path = (
            output_directory
            / name
        )

        (
            dataframe.write
            .mode("overwrite")
            .parquet(
                str(output_path)
            )
        )

        output_paths[name] = output_path

    return output_paths


def run_spark_pipeline(
    spark: SparkSession,
    raw_directory: Path = RAW_DIRECTORY,
    output_directory: Path = SPARK_OUTPUT_DIRECTORY,
) -> dict:
    """Run validation, analytics and persistent Spark outputs."""

    raw_df = read_canonical_history(
        spark,
        raw_directory=raw_directory,
    )

    quality = validate_canonical_history(
        raw_df
    )

    datasets = build_analytical_datasets(
        raw_df
    )

    row_counts = {
        name: dataframe.count()
        for name, dataframe in datasets.items()
    }

    output_paths = write_analytical_outputs(
        datasets,
        output_directory=output_directory,
    )

    return {
        "quality": quality,
        "row_counts": row_counts,
        "output_paths": output_paths,
    }


def main() -> None:
    """Run the persistent Spark analytics pipeline locally."""

    spark = create_spark_session(
        app_name="gb-generation-spark-pipeline"
    )

    spark.sparkContext.setLogLevel(
        "ERROR"
    )

    try:
        result = run_spark_pipeline(
            spark
        )

        print()
        print(
            "SPARK ANALYTICAL PIPELINE"
        )
        print(
            "-------------------------"
        )

        print(
            "Raw rows:",
            result["quality"]["rows"],
        )

        print(
            "Publications:",
            result["quality"]["publications"],
        )

        print(
            "Duplicate source keys:",
            result["quality"][
                "duplicate_source_keys"
            ],
        )

        print()
        print(
            "PERSISTED DATASETS"
        )
        print(
            "------------------"
        )

        for name, count in (
            result["row_counts"].items()
        ):
            print(
                f"{name}: {count}"
            )

        print()
        print(
            "OUTPUT DIRECTORY"
        )
        print(
            "----------------"
        )
        print(
            SPARK_OUTPUT_DIRECTORY
        )

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
