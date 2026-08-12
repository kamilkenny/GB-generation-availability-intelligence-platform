from __future__ import annotations

from pathlib import Path

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

from config.settings import RAW_DATA_DIR


RAW_DIRECTORY = RAW_DATA_DIR / "uou2t14d"

REQUIRED_COLUMNS = {
    "dataset",
    "fuelType",
    "nationalGridBmUnit",
    "bmUnit",
    "publishTime",
    "forecastDate",
    "outputUsable",
    "collectedAt",
}


def create_spark_session(
    app_name: str = "gb-generation-availability",
) -> SparkSession:
    """Create a local Spark session with UTC timestamps."""

    return (
        SparkSession.builder
        .master("local[2]")
        .appName(app_name)
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )


def read_canonical_history(
    spark: SparkSession,
    raw_directory: Path = RAW_DIRECTORY,
) -> DataFrame:
    """Read all canonical UOU2T14D publication Parquet files."""

    pattern = str(
        raw_directory
        / "uou2t14d_publish_*.parquet"
    )

    return spark.read.parquet(pattern)


def validate_canonical_history(
    df: DataFrame,
) -> dict:
    """Validate canonical columns, keys and null constraints."""

    missing_columns = (
        REQUIRED_COLUMNS
        - set(df.columns)
    )

    if missing_columns:
        raise ValueError(
            "Missing canonical columns: "
            + ", ".join(sorted(missing_columns))
        )

    total_rows = df.count()

    publication_count = (
        df.select("publishTime")
        .distinct()
        .count()
    )

    duplicate_source_keys = (
        df.groupBy(
            "nationalGridBmUnit",
            "publishTime",
            "forecastDate",
        )
        .count()
        .filter(F.col("count") > 1)
        .count()
    )

    null_national_grid_bm_units = (
        df.filter(
            F.col("nationalGridBmUnit").isNull()
        )
        .count()
    )

    null_publish_times = (
        df.filter(
            F.col("publishTime").isNull()
        )
        .count()
    )

    null_forecast_dates = (
        df.filter(
            F.col("forecastDate").isNull()
        )
        .count()
    )

    null_output_usable = (
        df.filter(
            F.col("outputUsable").isNull()
        )
        .count()
    )

    quality = {
        "rows": total_rows,
        "publications": publication_count,
        "duplicate_source_keys":
            duplicate_source_keys,
        "null_national_grid_bm_units":
            null_national_grid_bm_units,
        "null_publish_times":
            null_publish_times,
        "null_forecast_dates":
            null_forecast_dates,
        "null_output_usable":
            null_output_usable,
    }

    failures = {
        key: value
        for key, value in quality.items()
        if key not in {"rows", "publications"}
        and value != 0
    }

    if failures:
        raise ValueError(
            f"Canonical Spark quality checks failed: {failures}"
        )

    return quality


def build_fuel_availability_history(
    df: DataFrame,
) -> DataFrame:
    """Aggregate usable availability by publication, date and fuel."""

    return (
        df.groupBy(
            "publishTime",
            "forecastDate",
            "fuelType",
        )
        .agg(
            F.sum("outputUsable")
            .alias("availableMW")
        )
    )


def build_system_availability_history(
    df: DataFrame,
) -> DataFrame:
    """Aggregate total system usable availability."""

    return (
        df.groupBy(
            "publishTime",
            "forecastDate",
        )
        .agg(
            F.sum("outputUsable")
            .alias("availableMW")
        )
    )


def build_unit_revision_history(
    df: DataFrame,
) -> DataFrame:
    """Build publication-to-publication BM Unit revisions."""

    window = (
        Window.partitionBy(
            "nationalGridBmUnit",
            "forecastDate",
        )
        .orderBy("publishTime")
    )

    revisions = (
        df.withColumn(
            "previousPublishTime",
            F.lag("publishTime").over(window),
        )
        .withColumn(
            "previousAvailableMW",
            F.lag("outputUsable").over(window),
        )
        .withColumn(
            "previousFuelType",
            F.lag("fuelType").over(window),
        )
        .filter(
            F.col("previousPublishTime").isNotNull()
        )
        .withColumnRenamed(
            "publishTime",
            "latestPublishTime",
        )
        .withColumnRenamed(
            "outputUsable",
            "latestAvailableMW",
        )
        .withColumn(
            "revisionMW",
            F.col("latestAvailableMW")
            - F.col("previousAvailableMW"),
        )
        .withColumn(
            "fuelTypeChanged",
            ~F.col("fuelType").eqNullSafe(
                F.col("previousFuelType")
            ),
        )
        .withColumn(
            "revisionDirection",
            F.when(
                F.col("revisionMW") > 0,
                F.lit("up"),
            )
            .when(
                F.col("revisionMW") < 0,
                F.lit("down"),
            )
            .otherwise(
                F.lit("unchanged")
            ),
        )
    )

    return revisions


def build_aggregate_revision_history(
    history_df: DataFrame,
    partition_columns: list[str],
) -> DataFrame:
    """Build revisions for an aggregated availability history."""

    window = (
        Window.partitionBy(
            *partition_columns
        )
        .orderBy("publishTime")
    )

    return (
        history_df.withColumn(
            "previousPublishTime",
            F.lag("publishTime").over(window),
        )
        .withColumn(
            "previousAvailableMW",
            F.lag("availableMW").over(window),
        )
        .filter(
            F.col("previousPublishTime").isNotNull()
        )
        .withColumnRenamed(
            "publishTime",
            "latestPublishTime",
        )
        .withColumnRenamed(
            "availableMW",
            "latestAvailableMW",
        )
        .withColumn(
            "revisionMW",
            F.col("latestAvailableMW")
            - F.col("previousAvailableMW"),
        )
        .withColumn(
            "revisionDirection",
            F.when(
                F.col("revisionMW") > 0,
                F.lit("up"),
            )
            .when(
                F.col("revisionMW") < 0,
                F.lit("down"),
            )
            .otherwise(
                F.lit("unchanged")
            ),
        )
    )


def main() -> None:
    """Run historical Spark availability analytics."""

    spark = create_spark_session()
    spark.sparkContext.setLogLevel("ERROR")

    try:
        raw_df = read_canonical_history(spark)

        quality = validate_canonical_history(
            raw_df
        )

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

        print()
        print("SPARK AVAILABILITY ANALYTICS")
        print("----------------------------")
        print("Raw rows:", quality["rows"])
        print(
            "Publications:",
            quality["publications"],
        )
        print(
            "Duplicate source keys:",
            quality["duplicate_source_keys"],
        )
        print(
            "Fuel history rows:",
            fuel_history.count(),
        )
        print(
            "System history rows:",
            system_history.count(),
        )
        print(
            "Unit revision rows:",
            unit_revisions.count(),
        )
        print(
            "Fuel revision rows:",
            fuel_revisions.count(),
        )
        print(
            "System revision rows:",
            system_revisions.count(),
        )

        print()
        print("UNIT REVISION PAIRS")
        print("-------------------")

        (
            unit_revisions
            .groupBy(
                "previousPublishTime",
                "latestPublishTime",
            )
            .agg(
                F.sum(
                    F.when(
                        F.col("revisionMW") != 0,
                        F.lit(1),
                    )
                    .otherwise(
                        F.lit(0)
                    )
                )
                .alias("changedRows")
            )
            .orderBy(
                "previousPublishTime",
                "latestPublishTime",
            )
            .show(
                truncate=False
            )
        )

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
