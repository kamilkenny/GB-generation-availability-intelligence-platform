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
    run_databricks_pipeline,
)


DEFAULT_RAW_DIRECTORY = (
    "/Volumes/workspace/"
    "gb_generation/"
    "raw_uou2t14d"
)

DEFAULT_CATALOG = "workspace"
DEFAULT_SCHEMA = "gb_generation"


def parse_args() -> argparse.Namespace:
    """Parse Databricks job parameters."""

    parser = argparse.ArgumentParser(
        description=(
            "Run GB generation availability "
            "analytics in Databricks."
        )
    )

    parser.add_argument(
        "--raw-directory",
        default=DEFAULT_RAW_DIRECTORY,
        help=(
            "Unity Catalog volume containing "
            "canonical UOU2T14D publications."
        ),
    )

    parser.add_argument(
        "--catalog",
        default=DEFAULT_CATALOG,
        help="Unity Catalog catalogue.",
    )

    parser.add_argument(
        "--schema",
        default=DEFAULT_SCHEMA,
        help="Unity Catalog schema.",
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
    catalog: str,
    schema: str,
) -> dict:
    """Execute the Databricks Spark pipeline."""

    return run_databricks_pipeline(
        spark,
        raw_directory=Path(
            raw_directory
        ),
        catalog=catalog,
        schema=schema,
    )


def main() -> None:
    """Run the Databricks availability job."""

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
            catalog=args.catalog,
            schema=args.schema,
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
            "UNITY CATALOG TABLES"
        )
        print(
            "--------------------"
        )

        for name, count in (
            result["row_counts"].items()
        ):
            print(
                f"{name}: {count}"
            )

        print()
        print(
            "TABLE LOCATIONS"
        )
        print(
            "---------------"
        )

        for name, table_name in (
            result["table_names"].items()
        ):
            print(
                f"{name}: {table_name}"
            )

    finally:
        if created_locally:
            spark.stop()


if __name__ == "__main__":
    main()
