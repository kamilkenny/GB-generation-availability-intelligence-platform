from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
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

DUPLICATE_KEY = [
    "bmUnit",
    "publishTime",
    "forecastDate",
]


def configure_logging() -> logging.Logger:
    """Create console and file logging for the ingestion pipeline."""

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_file = LOG_DIR / "uou2t14d_ingestion.log"

    logger = logging.getLogger("uou2t14d_ingestion")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


def validate_dataframe(df: pd.DataFrame) -> dict:
    """Validate the basic structure and quality of an Elexon snapshot."""

    if df.empty:
        raise ValueError("Elexon returned an empty UOU2T14D dataset.")

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Required columns missing: {missing_columns}"
        )

    null_counts = {
        column: int(df[column].isna().sum())
        for column in REQUIRED_COLUMNS
    }

    duplicate_count = int(
        df.duplicated(subset=DUPLICATE_KEY).sum()
    )

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


def timestamp_to_text(value) -> str | None:
    """Convert a pandas timestamp/date value into JSON-safe text."""

    if pd.isna(value):
        return None

    return pd.Timestamp(value).isoformat()


def save_snapshot(
    df: pd.DataFrame,
    validation_results: dict,
) -> tuple[Path, Path]:
    """Save a timestamped Parquet snapshot and metadata file."""

    snapshot_directory = RAW_DATA_DIR / "uou2t14d"
    snapshot_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    now_utc = datetime.now(timezone.utc)
    timestamp = now_utc.strftime("%Y%m%dT%H%M%SZ")

    parquet_path = (
        snapshot_directory
        / f"uou2t14d_{timestamp}.parquet"
    )

    metadata_path = (
        snapshot_directory
        / f"uou2t14d_{timestamp}_metadata.json"
    )

    df.to_parquet(
        parquet_path,
        index=False,
    )

    metadata = {
        "dataset": DATASET_NAME,
        "source": "Elexon Insights API",
        "endpoint": "/datasets/UOU2T14D/stream",
        "collected_at_utc": now_utc.isoformat(),
        "rows": int(len(df)),
        "columns": df.columns.tolist(),
        "distinct_bm_units": int(
            df["bmUnit"].nunique(dropna=True)
        ),
        "distinct_fuel_types": int(
            df["fuelType"].nunique(dropna=True)
        ),
        "distinct_publication_times": int(
            df["publishTime"].nunique(dropna=True)
        ),
        "earliest_publish_time": timestamp_to_text(
            df["publishTime"].min()
        ),
        "latest_publish_time": timestamp_to_text(
            df["publishTime"].max()
        ),
        "earliest_forecast_date": timestamp_to_text(
            df["forecastDate"].min()
        ),
        "latest_forecast_date": timestamp_to_text(
            df["forecastDate"].max()
        ),
        "validation": validation_results,
    }

    with metadata_path.open(
        "w",
        encoding="utf-8",
    ) as metadata_file:
        json.dump(
            metadata,
            metadata_file,
            indent=2,
        )

    return parquet_path, metadata_path


def main() -> None:
    """Run the UOU2T14D ingestion pipeline."""

    logger = configure_logging()

    logger.info(
        "Starting %s ingestion.",
        DATASET_NAME,
    )

    try:
        client = ElexonClient()

        logger.info(
            "Requesting latest generation availability from Elexon."
        )

        df = client.get_latest_generation_availability()

        logger.info(
            "Received %s rows.",
            f"{len(df):,}",
        )

        validation_results = validate_dataframe(df)

        parquet_path, metadata_path = save_snapshot(
            df,
            validation_results,
        )

        logger.info(
            "Parquet snapshot saved to %s",
            parquet_path,
        )

        logger.info(
            "Metadata saved to %s",
            metadata_path,
        )

        print()
        print("UOU2T14D INGESTION COMPLETE")
        print("---------------------------")
        print(f"Rows:              {len(df):,}")
        print(
            f"BM Units:          "
            f"{df['bmUnit'].nunique(dropna=True):,}"
        )
        print(
            f"Fuel types:        "
            f"{df['fuelType'].nunique(dropna=True):,}"
        )
        print(
            f"Publication times: "
            f"{df['publishTime'].nunique(dropna=True):,}"
        )
        print(
            f"Duplicate keys:    "
            f"{validation_results['duplicate_key_rows']:,}"
        )
        print(f"Parquet:           {parquet_path}")
        print(f"Metadata:          {metadata_path}")

    except Exception:
        logger.exception(
            "%s ingestion failed.",
            DATASET_NAME,
        )
        raise


if __name__ == "__main__":
    main()
