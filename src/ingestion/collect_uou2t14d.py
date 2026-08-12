from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from config.settings import LOG_DIR, RAW_DATA_DIR
from src.ingestion.elexon_client import ElexonClient


DATASET_NAME = "UOU2T14D"

REQUIRED_COLUMNS = [
    "dataset",
    "fuelType",
    "nationalGridBmUnit",
    "bmUnit",
    "publishTime",
    "forecastDate",
    "outputUsable",
    "collectedAt",
]

# nationalGridBmUnit is the complete unit identifier
# in the returned UOU2T14D dataset.
DUPLICATE_KEY = [
    "nationalGridBmUnit",
    "publishTime",
    "forecastDate",
]


def configure_logging() -> logging.Logger:
    """Configure console and file logging."""

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("uou2t14d_ingestion")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )

        file_handler = logging.FileHandler(
            LOG_DIR / "uou2t14d_ingestion.log"
        )
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


def validate_dataframe(df: pd.DataFrame) -> dict:
    """Validate an incoming UOU2T14D publication."""

    if df.empty:
        raise ValueError(
            "Elexon returned an empty UOU2T14D dataset."
        )

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Required columns missing: {missing_columns}"
        )

    duplicate_count = int(
        df.duplicated(
            subset=DUPLICATE_KEY,
            keep=False,
        ).sum()
    )

    if duplicate_count > 0:
        raise ValueError(
            f"Detected {duplicate_count:,} rows involved "
            f"in duplicate source keys."
        )

    null_counts = {
        column: int(df[column].isna().sum())
        for column in REQUIRED_COLUMNS
    }

    negative_output_count = int(
        (
            pd.to_numeric(
                df["outputUsable"],
                errors="coerce",
            )
            < 0
        ).sum()
    )

    return {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "missing_required_columns": missing_columns,
        "null_counts": null_counts,
        "duplicate_key_rows": duplicate_count,
        "negative_output_usable_rows": negative_output_count,
    }


def get_publication_time(df: pd.DataFrame) -> pd.Timestamp:
    """Return the unique source publication timestamp."""

    publication_times = (
        df["publishTime"]
        .dropna()
        .drop_duplicates()
        .sort_values()
    )

    if len(publication_times) != 1:
        raise ValueError(
            "Expected exactly one publishTime in the latest "
            f"UOU2T14D snapshot, but found "
            f"{len(publication_times)}."
        )

    publication_time = pd.Timestamp(
        publication_times.iloc[0]
    )

    if publication_time.tzinfo is None:
        publication_time = publication_time.tz_localize("UTC")
    else:
        publication_time = publication_time.tz_convert("UTC")

    return publication_time


def publication_file_stamp(
    publication_time: pd.Timestamp,
) -> str:
    """Convert publication timestamp to a stable filename."""

    return publication_time.strftime(
        "%Y%m%dT%H%M%SZ"
    )


def write_spark_compatible_parquet(
    df: pd.DataFrame,
    parquet_path: Path,
) -> None:
    """Write Parquet using Spark-compatible timestamp resolution."""

    df.to_parquet(
        parquet_path,
        index=False,
        engine="pyarrow",
        version="1.0",
        coerce_timestamps="us",
        allow_truncated_timestamps=True,
    )


def repair_spark_compatible_parquet(
    parquet_path: Path,
) -> bool:
    """Rewrite Parquet only when nanosecond timestamps are present."""

    import pyarrow as pa
    import pyarrow.parquet as pq

    schema = pq.read_schema(parquet_path)

    has_nanosecond_timestamp = any(
        pa.types.is_timestamp(field.type)
        and field.type.unit == "ns"
        for field in schema
    )

    if not has_nanosecond_timestamp:
        return False

    existing_df = pd.read_parquet(
        parquet_path,
        engine="pyarrow",
    )

    write_spark_compatible_parquet(
        existing_df,
        parquet_path,
    )

    return True


def repair_snapshot_directory(
    snapshot_directory: Path,
) -> list[Path]:
    """Repair incompatible canonical Parquet timestamp encodings."""

    repaired = []

    for parquet_path in sorted(
        Path(snapshot_directory).glob(
            "uou2t14d_publish_*.parquet"
        )
    ):
        if repair_spark_compatible_parquet(
            parquet_path
        ):
            repaired.append(parquet_path)

    return repaired


def save_snapshot(
    df: pd.DataFrame,
    validation_results: dict,
    snapshot_directory: Path | None = None,
) -> tuple[Path, Path, bool]:
    """
    Save one file per unique Elexon publication.

    Returns
    -------
    parquet_path
    metadata_path
    created
        False when the publication already exists.
    """

    if snapshot_directory is None:
        snapshot_directory = RAW_DATA_DIR / "uou2t14d"

    snapshot_directory = Path(snapshot_directory)

    snapshot_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    publication_time = get_publication_time(df)
    publication_stamp = publication_file_stamp(
        publication_time
    )

    parquet_path = (
        snapshot_directory
        / f"uou2t14d_publish_{publication_stamp}.parquet"
    )

    metadata_path = (
        snapshot_directory
        / f"uou2t14d_publish_{publication_stamp}_metadata.json"
    )

    if parquet_path.exists():
        return parquet_path, metadata_path, False

    write_spark_compatible_parquet(
        df,
        parquet_path,
    )

    forecast_dates = pd.to_datetime(
        df["forecastDate"],
        errors="coerce",
    )

    metadata = {
        "dataset": DATASET_NAME,
        "source": "Elexon Insights API",
        "endpoint": "/datasets/UOU2T14D/stream",
        "publication_time_utc": publication_time.isoformat(),
        "collected_at_utc": pd.Timestamp.now(
            tz="UTC"
        ).isoformat(),
        "rows": int(len(df)),
        "columns": df.columns.tolist(),
        "distinct_national_grid_bm_units": int(
            df["nationalGridBmUnit"].nunique(
                dropna=True
            )
        ),
        "distinct_elexon_bm_units": int(
            df["bmUnit"].nunique(
                dropna=True
            )
        ),
        "distinct_fuel_types": int(
            df["fuelType"].nunique(
                dropna=True
            )
        ),
        "earliest_forecast_date": (
            forecast_dates.min().isoformat()
        ),
        "latest_forecast_date": (
            forecast_dates.max().isoformat()
        ),
        "validation": validation_results,
    }

    with metadata_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            metadata,
            file,
            indent=2,
        )

    return parquet_path, metadata_path, True


def collect_latest_publication(
    snapshot_directory: Path | None = None,
) -> dict:
    """Collect, validate and persist the latest Elexon publication."""

    client = ElexonClient()

    df = client.get_latest_generation_availability()

    validation = validate_dataframe(df)

    publication_time = get_publication_time(df)

    parquet_path, metadata_path, created = save_snapshot(
        df,
        validation,
        snapshot_directory=snapshot_directory,
    )

    active_snapshot_directory = (
        Path(snapshot_directory)
        if snapshot_directory is not None
        else RAW_DATA_DIR / "uou2t14d"
    )

    repaired_files = repair_snapshot_directory(
        active_snapshot_directory
    )

    return {
        "publication_time": publication_time,
        "rows": int(len(df)),
        "national_grid_bm_units": int(
            df["nationalGridBmUnit"].nunique()
        ),
        "fuel_types": int(
            df["fuelType"].nunique()
        ),
        "validation": validation,
        "parquet_path": parquet_path,
        "metadata_path": metadata_path,
        "created": created,
        "repaired_files": [
            str(path)
            for path in repaired_files
        ],
    }


def main() -> None:
    """Run the UOU2T14D ingestion process."""

    logger = configure_logging()

    logger.info(
        "Starting %s ingestion.",
        DATASET_NAME,
    )

    try:
        client = ElexonClient()

        logger.info(
            "Requesting latest generation availability "
            "from Elexon."
        )

        df = client.get_latest_generation_availability()

        logger.info(
            "Received %s rows.",
            f"{len(df):,}",
        )

        validation = validate_dataframe(df)

        publication_time = get_publication_time(df)

        parquet_path, metadata_path, created = (
            save_snapshot(
                df,
                validation,
            )
        )

        print()
        print("UOU2T14D INGESTION RESULT")
        print("-------------------------")
        print(
            "Source publication:",
            publication_time.isoformat(),
        )
        print(
            "Rows:",
            f"{len(df):,}",
        )
        print(
            "National Grid BM Units:",
            f"{df['nationalGridBmUnit'].nunique():,}",
        )
        print(
            "Fuel types:",
            f"{df['fuelType'].nunique():,}",
        )
        print(
            "Duplicate source keys:",
            validation["duplicate_key_rows"],
        )

        if created:
            logger.info(
                "New Elexon publication saved."
            )

            print("Status: NEW PUBLICATION SAVED")
            print("Parquet:", parquet_path)
            print("Metadata:", metadata_path)

        else:
            logger.info(
                "Publication %s already stored. "
                "No duplicate snapshot created.",
                publication_time,
            )

            print("Status: PUBLICATION ALREADY STORED")
            print("No duplicate snapshot created.")
            print("Existing file:", parquet_path)

    except Exception:
        logger.exception(
            "%s ingestion failed.",
            DATASET_NAME,
        )
        raise


if __name__ == "__main__":
    main()
