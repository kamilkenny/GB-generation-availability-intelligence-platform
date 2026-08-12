from __future__ import annotations

import pandas as pd
from sqlalchemy import MetaData, Table
from sqlalchemy.dialects.postgresql import insert

from config.settings import PROCESSED_DATA_DIR
from src.database.postgres import get_engine


REVISION_DIRECTORY = (
    PROCESSED_DATA_DIR
    / "uou2t14d"
    / "revisions"
)

UNIT_FILE = (
    REVISION_DIRECTORY
    / "latest_unit_revisions.parquet"
)

FUEL_FILE = (
    REVISION_DIRECTORY
    / "latest_fuel_revisions.parquet"
)

SYSTEM_FILE = (
    REVISION_DIRECTORY
    / "latest_system_revisions.parquet"
)


def load_revision_files():
    """Load latest revision intelligence outputs."""

    required_files = [
        UNIT_FILE,
        FUEL_FILE,
        SYSTEM_FILE,
    ]

    missing = [
        path
        for path in required_files
        if not path.exists()
    ]

    if missing:
        raise FileNotFoundError(
            "Missing revision output files: "
            + ", ".join(str(path) for path in missing)
        )

    return (
        pd.read_parquet(UNIT_FILE),
        pd.read_parquet(FUEL_FILE),
        pd.read_parquet(SYSTEM_FILE),
    )


def prepare_unit_revisions(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Prepare unit-level revisions for PostgreSQL."""

    prepared = df.rename(
        columns={
            "previousPublishTime":
                "previous_publish_time",
            "latestPublishTime":
                "latest_publish_time",
            "forecastDate":
                "forecast_date",
            "nationalGridBmUnit":
                "national_grid_bm_unit",
            "fuelType":
                "fuel_type",
            "previousAvailableMW":
                "previous_available_mw",
            "latestAvailableMW":
                "latest_available_mw",
            "revisionMW":
                "revision_mw",
            "absoluteRevisionMW":
                "absolute_revision_mw",
            "changeDirection":
                "change_direction",
            "becameUnavailable":
                "became_unavailable",
            "returnedAvailable":
                "returned_available",
        }
    ).copy()

    prepared["previous_publish_time"] = (
        pd.to_datetime(
            prepared["previous_publish_time"],
            utc=True,
        )
    )

    prepared["latest_publish_time"] = (
        pd.to_datetime(
            prepared["latest_publish_time"],
            utc=True,
        )
    )

    prepared["forecast_date"] = (
        pd.to_datetime(
            prepared["forecast_date"]
        ).dt.date
    )

    return prepared


def prepare_fuel_revisions(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Prepare fuel-level revisions for PostgreSQL."""

    prepared = df.rename(
        columns={
            "previousPublishTime":
                "previous_publish_time",
            "latestPublishTime":
                "latest_publish_time",
            "forecastDate":
                "forecast_date",
            "fuelType":
                "fuel_type",
            "previousAvailableMW":
                "previous_available_mw",
            "latestAvailableMW":
                "latest_available_mw",
            "revisionMW":
                "revision_mw",
            "changedUnits":
                "changed_units",
            "becameUnavailableUnits":
                "became_unavailable_units",
            "returnedAvailableUnits":
                "returned_available_units",
        }
    ).copy()

    prepared["previous_publish_time"] = (
        pd.to_datetime(
            prepared["previous_publish_time"],
            utc=True,
        )
    )

    prepared["latest_publish_time"] = (
        pd.to_datetime(
            prepared["latest_publish_time"],
            utc=True,
        )
    )

    prepared["forecast_date"] = (
        pd.to_datetime(
            prepared["forecast_date"]
        ).dt.date
    )

    return prepared


def prepare_system_revisions(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Prepare system-level revisions for PostgreSQL."""

    prepared = df.rename(
        columns={
            "previousPublishTime":
                "previous_publish_time",
            "latestPublishTime":
                "latest_publish_time",
            "forecastDate":
                "forecast_date",
            "previousAvailableMW":
                "previous_available_mw",
            "latestAvailableMW":
                "latest_available_mw",
            "revisionMW":
                "revision_mw",
            "changedUnits":
                "changed_units",
            "becameUnavailableUnits":
                "became_unavailable_units",
            "returnedAvailableUnits":
                "returned_available_units",
        }
    ).copy()

    prepared["previous_publish_time"] = (
        pd.to_datetime(
            prepared["previous_publish_time"],
            utc=True,
        )
    )

    prepared["latest_publish_time"] = (
        pd.to_datetime(
            prepared["latest_publish_time"],
            utc=True,
        )
    )

    prepared["forecast_date"] = (
        pd.to_datetime(
            prepared["forecast_date"]
        ).dt.date
    )

    return prepared


def dataframe_records(
    df: pd.DataFrame,
) -> list[dict]:
    """Convert DataFrame rows to database-safe dictionaries."""

    records = []

    for record in df.to_dict(
        orient="records"
    ):
        converted = {}

        for key, value in record.items():
            if isinstance(value, pd.Timestamp):
                converted[key] = (
                    value.to_pydatetime()
                )
            elif pd.isna(value):
                converted[key] = None
            else:
                converted[key] = value

        records.append(converted)

    return records


def upsert_dataframe(
    connection,
    table_name: str,
    df: pd.DataFrame,
    conflict_columns: list[str],
) -> int:
    """Upsert one revision DataFrame."""

    metadata = MetaData()

    table = Table(
        table_name,
        metadata,
        schema="analytics",
        autoload_with=connection,
    )

    records = dataframe_records(df)

    if not records:
        return 0

    statement = insert(table)

    update_columns = {
        column.name:
            statement.excluded[column.name]
        for column in table.columns
        if column.name not in conflict_columns
    }

    statement = (
        statement.on_conflict_do_update(
            index_elements=conflict_columns,
            set_=update_columns,
        )
    )

    connection.execute(
        statement,
        records,
    )

    return len(records)


def main() -> None:
    """Load latest availability revisions into Analytics."""

    (
        unit_df,
        fuel_df,
        system_df,
    ) = load_revision_files()

    unit_df = prepare_unit_revisions(
        unit_df
    )

    fuel_df = prepare_fuel_revisions(
        fuel_df
    )

    system_df = prepare_system_revisions(
        system_df
    )

    engine = get_engine()

    with engine.begin() as connection:

        unit_rows = upsert_dataframe(
            connection=connection,
            table_name="unit_availability_revision",
            df=unit_df,
            conflict_columns=[
                "previous_publish_time",
                "latest_publish_time",
                "forecast_date",
                "national_grid_bm_unit",
            ],
        )

        fuel_rows = upsert_dataframe(
            connection=connection,
            table_name="fuel_availability_revision",
            df=fuel_df,
            conflict_columns=[
                "previous_publish_time",
                "latest_publish_time",
                "forecast_date",
                "fuel_type",
            ],
        )

        system_rows = upsert_dataframe(
            connection=connection,
            table_name="system_availability_revision",
            df=system_df,
            conflict_columns=[
                "previous_publish_time",
                "latest_publish_time",
                "forecast_date",
            ],
        )

    print()
    print("REVISION ANALYTICS DATABASE LOAD")
    print("--------------------------------")
    print(
        "Unit revision rows processed:",
        f"{unit_rows:,}",
    )
    print(
        "Fuel revision rows processed:",
        f"{fuel_rows:,}",
    )
    print(
        "System revision rows processed:",
        f"{system_rows:,}",
    )


if __name__ == "__main__":
    main()
