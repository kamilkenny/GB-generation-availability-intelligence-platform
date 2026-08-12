from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from config.settings import PROCESSED_DATA_DIR
from src.database.postgres import get_engine


PROCESSED_DIRECTORY = (
    PROCESSED_DATA_DIR / "uou2t14d"
)

FUEL_FILE = (
    PROCESSED_DIRECTORY
    / "latest_fuel_availability.parquet"
)

SYSTEM_FILE = (
    PROCESSED_DIRECTORY
    / "latest_system_availability.parquet"
)


def load_processed_files():
    """Load the latest transformed availability datasets."""

    if not FUEL_FILE.exists():
        raise FileNotFoundError(
            f"Fuel availability file not found: {FUEL_FILE}"
        )

    if not SYSTEM_FILE.exists():
        raise FileNotFoundError(
            f"System availability file not found: {SYSTEM_FILE}"
        )

    fuel_df = pd.read_parquet(FUEL_FILE)
    system_df = pd.read_parquet(SYSTEM_FILE)

    return fuel_df, system_df


def prepare_fuel_dataframe(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Prepare fuel-level data for PostgreSQL."""

    prepared = df.rename(
        columns={
            "publishTime": "publish_time",
            "forecastDate": "forecast_date",
            "fuelType": "fuel_type",
        }
    ).copy()

    prepared["publish_time"] = pd.to_datetime(
        prepared["publish_time"],
        utc=True,
    )

    prepared["forecast_date"] = pd.to_datetime(
        prepared["forecast_date"],
    ).dt.date

    prepared["available_mw"] = pd.to_numeric(
        prepared["available_mw"],
    )

    prepared["bm_units"] = pd.to_numeric(
        prepared["bm_units"],
    ).astype(int)

    prepared["zero_availability_units"] = pd.to_numeric(
        prepared["zero_availability_units"],
    ).astype(int)

    return prepared


def prepare_system_dataframe(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Prepare system-level data for PostgreSQL."""

    prepared = df.rename(
        columns={
            "publishTime": "publish_time",
            "forecastDate": "forecast_date",
        }
    ).copy()

    prepared["publish_time"] = pd.to_datetime(
        prepared["publish_time"],
        utc=True,
    )

    prepared["forecast_date"] = pd.to_datetime(
        prepared["forecast_date"],
    ).dt.date

    prepared["total_available_mw"] = pd.to_numeric(
        prepared["total_available_mw"],
    )

    prepared["bm_units"] = pd.to_numeric(
        prepared["bm_units"],
    ).astype(int)

    prepared["zero_availability_units"] = pd.to_numeric(
        prepared["zero_availability_units"],
    ).astype(int)

    return prepared


def upsert_fuel_availability(
    connection,
    df: pd.DataFrame,
) -> int:
    """Insert/update fuel-level Silver records."""

    records = []

    for row in df.itertuples(index=False):
        records.append(
            {
                "publish_time": row.publish_time.to_pydatetime(),
                "forecast_date": row.forecast_date,
                "fuel_type": row.fuel_type,
                "available_mw": float(row.available_mw),
                "bm_units": int(row.bm_units),
                "zero_availability_units": int(
                    row.zero_availability_units
                ),
            }
        )

    statement = insert(
        __import__(
            "sqlalchemy"
        ).Table(
            "fuel_availability",
            __import__(
                "sqlalchemy"
            ).MetaData(),
            autoload_with=connection,
            schema="silver",
        )
    )

    statement = statement.on_conflict_do_update(
        index_elements=[
            "publish_time",
            "forecast_date",
            "fuel_type",
        ],
        set_={
            "available_mw": statement.excluded.available_mw,
            "bm_units": statement.excluded.bm_units,
            "zero_availability_units":
                statement.excluded.zero_availability_units,
        },
    )

    connection.execute(
        statement,
        records,
    )

    return len(records)


def upsert_system_availability(
    connection,
    df: pd.DataFrame,
) -> int:
    """Insert/update system-level Silver records."""

    records = []

    for row in df.itertuples(index=False):
        records.append(
            {
                "publish_time": row.publish_time.to_pydatetime(),
                "forecast_date": row.forecast_date,
                "total_available_mw": float(
                    row.total_available_mw
                ),
                "bm_units": int(row.bm_units),
                "zero_availability_units": int(
                    row.zero_availability_units
                ),
            }
        )

    statement = insert(
        __import__(
            "sqlalchemy"
        ).Table(
            "system_availability",
            __import__(
                "sqlalchemy"
            ).MetaData(),
            autoload_with=connection,
            schema="silver",
        )
    )

    statement = statement.on_conflict_do_update(
        index_elements=[
            "publish_time",
            "forecast_date",
        ],
        set_={
            "total_available_mw":
                statement.excluded.total_available_mw,
            "bm_units":
                statement.excluded.bm_units,
            "zero_availability_units":
                statement.excluded.zero_availability_units,
        },
    )

    connection.execute(
        statement,
        records,
    )

    return len(records)


def verify_database(
    connection,
    publish_time,
) -> dict:
    """Return database row counts for one publication."""

    fuel_rows = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM silver.fuel_availability
            WHERE publish_time = :publish_time
            """
        ),
        {"publish_time": publish_time},
    ).scalar_one()

    system_rows = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM silver.system_availability
            WHERE publish_time = :publish_time
            """
        ),
        {"publish_time": publish_time},
    ).scalar_one()

    return {
        "fuel_rows": fuel_rows,
        "system_rows": system_rows,
    }


def main() -> None:
    """Load Silver availability tables into PostgreSQL."""

    fuel_df, system_df = load_processed_files()

    fuel_df = prepare_fuel_dataframe(
        fuel_df
    )

    system_df = prepare_system_dataframe(
        system_df
    )

    publish_time = (
        fuel_df["publish_time"]
        .iloc[0]
        .to_pydatetime()
    )

    engine = get_engine()

    with engine.begin() as connection:

        fuel_processed = upsert_fuel_availability(
            connection,
            fuel_df,
        )

        system_processed = upsert_system_availability(
            connection,
            system_df,
        )

        verification = verify_database(
            connection,
            publish_time,
        )

    print()
    print("SILVER DATABASE LOAD RESULT")
    print("---------------------------")
    print("Publication:", publish_time)
    print(
        "Fuel rows processed:",
        f"{fuel_processed:,}",
    )
    print(
        "System rows processed:",
        f"{system_processed:,}",
    )
    print(
        "Fuel rows in database:",
        f"{verification['fuel_rows']:,}",
    )
    print(
        "System rows in database:",
        f"{verification['system_rows']:,}",
    )


if __name__ == "__main__":
    main()
