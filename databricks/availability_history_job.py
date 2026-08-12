from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pyspark.sql import SparkSession


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from src.pipeline.spark_availability_pipeline import (
    run_spark_pipeline,
)


def parse_args() -> argparse.Namespace:
    """Parse Databricks or local job parameters."""

    parser = argparse.ArgumentParser(
        description=(
            "Run GB generation availability "
            "Spark analytics."
        )
    )

    parser.add_argument(
        "--raw-directory",
        required=True,
        help=(
            "Directory containing canonical "
            "UOU2T14D Parquet publications."
        ),
    )

    parser.add_argument(
        "--output-directory",
        required=True,
        help=(
            "Directory for persistent Spark "
            "analytical outputs."
        ),
    )

    return parser.parse_args()


def get_spark_session() -> tuple[
    SparkSession,
    bool,
]:
    """
    Reuse Databricks Spark when available.

    Returns the Spark session and whether this
    script created the session locally.
    """

    active_session = (
        SparkSession.getActiveSession()
    )

    if active_session is not None:
        active_session.conf.set(
            "spark.sql.session.timeZone",
            "UTC",
        )

        return (
            active_session,
            False,
        )

    local_session = (
        SparkSession.builder
        .master("local[2]")
        .appName(
            "gb-generation-databricks-job"
        )
        .config(
            "spark.sql.session.timeZone",
            "UTC",
        )
        .getOrCreate()
    )

    return (
        local_session,
        True,
    )


def execute_job(
    spark: SparkSession,
    raw_directory: str,
    output_directory: str,
) -> dict:
    """Execute the shared Spark pipeline."""

    return run_spark_pipeline(
        spark,
        raw_directory=Path(
            raw_directory
        ),
        output_directory=Path(
            output_directory
        ),
    )


def main() -> None:
    """Run the availability analytics job."""

    args = parse_args()

    spark, created_locally = (
        get_spark_session()
    )

    spark.sparkContext.setLogLevel(
        "ERROR"
    )

    try:
        result = execute_job(
            spark,
            raw_directory=(
                args.raw_directory
            ),
            output_directory=(
                args.output_directory
            ),
        )

        print()
        print(
            "DATABRICKS AVAILABILITY JOB"
        )
        print(
            "---------------------------"
        )

        print(
            "Raw rows:",
            result["quality"]["rows"],
        )

        print(
            "Publications:",
            result["quality"][
                "publications"
            ],
        )

        print(
            "Duplicate source keys:",
            result["quality"][
                "duplicate_source_keys"
            ],
        )

        print()
        print(
            "ANALYTICAL OUTPUTS"
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

    finally:
        if created_locally:
            spark.stop()


if __name__ == "__main__":
    main()
