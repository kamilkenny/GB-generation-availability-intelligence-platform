from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import text

from config.settings import RAW_DATA_DIR
from src.database.postgres import get_engine


RAW_DIRECTORY = RAW_DATA_DIR / "uou2t14d"


def latest_canonical_publication() -> Path:
    """Return latest canonical UOU2T14D publication."""

    files = sorted(
        RAW_DIRECTORY.glob(
            "uou2t14d_publish_*.parquet"
        )
    )

    if not files:
        raise FileNotFoundError(
            "No canonical UOU2T14D publication found."
        )

    return files[-1]


def prepare_dataframe(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Convert Elexon column names to database names."""

    prepared = df.rename(
        columns={
            "nationalGridBmUnit": "national_grid_bm_unit",
            "bmUnit": "bm_unit",
            "fuelType": "fuel_type",
            "publishTime": "publish_time",
            "forecastDate": "forecast_date",
            "outputUsable": "output_usable_mw",
            "collectedAt": "collected_at",
        }
    ).copy()

    prepared["publish_time"] = pd.to_datetime(
        prepared["publish_time"],
        utc=True,
    )

    prepared["forecast_date"] = pd.to_datetime(
        prepared["forecast_date"]
    ).dt.date

    prepared["collected_at"] = pd.to_datetime(
        prepared["collected_at"],
        utc=True,
    )

    return prepared[
        [
            "national_grid_bm_unit",
            "bm_unit",
            "fuel_type",
            "publish_time",
            "forecast_date",
            "output_usable_mw",
            "collected_at",
            "dataset",
        ]
    ]


def load_publication_file(
    file_path: Path,
) -> dict:
    """Load one explicit canonical publication idempotently."""

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"Canonical publication not found: {file_path}"
        )

    df = pd.read_parquet(file_path)

    if df.empty:
        raise ValueError(
            f"Canonical publication is empty: {file_path}"
        )

    df = prepare_dataframe(df)

    publish_times = (
        df["publish_time"]
        .dropna()
        .drop_duplicates()
    )

    if len(publish_times) != 1:
        raise ValueError(
            "Expected exactly one publish_time in "
            f"{file_path.name}, but found "
            f"{len(publish_times)}."
        )

    publish_time = pd.Timestamp(
        publish_times.iloc[0]
    )

    engine = get_engine()

    with engine.begin() as connection:

        existing_count = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM raw.uou2t14d
                WHERE publish_time = :publish_time
                """
            ),
            {
                "publish_time":
                    publish_time.to_pydatetime()
            },
        ).scalar_one()

        if existing_count > 0:
            print()
            print("DATABASE LOAD RESULT")
            print("--------------------")
            print(
                "Status: PUBLICATION ALREADY LOADED"
            )
            print("Source file:", file_path)
            print("Publish time:", publish_time)
            print(
                "Existing rows:",
                f"{existing_count:,}",
            )

            return {
                "status": "already_loaded",
                "file_path": file_path,
                "publish_time": publish_time,
                "rows": int(existing_count),
            }

        df.to_sql(
            name="uou2t14d",
            con=connection,
            schema="raw",
            if_exists="append",
            index=False,
            method="multi",
            chunksize=1000,
        )

        row_count = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM raw.uou2t14d
                WHERE publish_time = :publish_time
                """
            ),
            {
                "publish_time":
                    publish_time.to_pydatetime()
            },
        ).scalar_one()

    print()
    print("DATABASE LOAD RESULT")
    print("--------------------")
    print("Status: NEW PUBLICATION LOADED")
    print("Source file:", file_path)
    print("Publish time:", publish_time)
    print("Rows loaded:", f"{row_count:,}")

    return {
        "status": "loaded",
        "file_path": file_path,
        "publish_time": publish_time,
        "rows": int(row_count),
    }


def load_publication() -> dict:
    """Load the latest canonical Raw publication."""

    return load_publication_file(
        latest_canonical_publication()
    )


if __name__ == "__main__":
    load_publication()
