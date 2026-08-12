from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.settings import RAW_DATA_DIR
from src.analytics.build_availability_revisions import (
    build_fuel_revisions,
    build_system_revisions,
    build_unit_revisions,
    save_outputs,
)
from src.database.load_revision_analytics import (
    prepare_fuel_revisions,
    prepare_system_revisions,
    prepare_unit_revisions,
    upsert_dataframe,
)
from src.database.load_silver_availability import (
    prepare_fuel_dataframe,
    prepare_system_dataframe,
    upsert_fuel_availability,
    upsert_system_availability,
    verify_database,
)
from src.database.load_uou2t14d import (
    load_publication_file as load_raw_publication_file,
)
from src.database.postgres import get_engine
from src.transformation.transform_uou2t14d import (
    load_publication_file as load_transformation_publication_file,
    transform_publication_file,
)


RAW_DIRECTORY = RAW_DATA_DIR / "uou2t14d"


def get_publication_files() -> list[Path]:
    """Return canonical publication files chronologically."""

    files = sorted(
        RAW_DIRECTORY.glob(
            "uou2t14d_publish_*.parquet"
        )
    )

    if not files:
        raise FileNotFoundError(
            "No canonical UOU2T14D publications found."
        )

    return files


def load_silver_dataframes(
    connection,
    fuel_df: pd.DataFrame,
    system_df: pd.DataFrame,
) -> dict:
    """Load transformed publication data into Silver."""

    prepared_fuel = prepare_fuel_dataframe(
        fuel_df
    )

    prepared_system = prepare_system_dataframe(
        system_df
    )

    if prepared_fuel.empty:
        raise ValueError(
            "Fuel availability DataFrame is empty."
        )

    if prepared_system.empty:
        raise ValueError(
            "System availability DataFrame is empty."
        )

    fuel_publish_times = (
        prepared_fuel["publish_time"]
        .dropna()
        .drop_duplicates()
    )

    system_publish_times = (
        prepared_system["publish_time"]
        .dropna()
        .drop_duplicates()
    )

    if len(fuel_publish_times) != 1:
        raise ValueError(
            "Expected exactly one Silver fuel "
            "publication."
        )

    if len(system_publish_times) != 1:
        raise ValueError(
            "Expected exactly one Silver system "
            "publication."
        )

    fuel_publish_time = pd.Timestamp(
        fuel_publish_times.iloc[0]
    )

    system_publish_time = pd.Timestamp(
        system_publish_times.iloc[0]
    )

    if fuel_publish_time != system_publish_time:
        raise ValueError(
            "Fuel and system publication times "
            "do not match."
        )

    publish_time = (
        fuel_publish_time.to_pydatetime()
    )

    fuel_rows = upsert_fuel_availability(
        connection,
        prepared_fuel,
    )

    system_rows = upsert_system_availability(
        connection,
        prepared_system,
    )

    verification = verify_database(
        connection,
        publish_time,
    )

    return {
        "publish_time": fuel_publish_time,
        "fuel_rows_processed": fuel_rows,
        "system_rows_processed": system_rows,
        "fuel_rows_database":
            verification["fuel_rows"],
        "system_rows_database":
            verification["system_rows"],
    }


def load_analytics_dataframes(
    connection,
    unit_df: pd.DataFrame,
    fuel_df: pd.DataFrame,
    system_df: pd.DataFrame,
) -> dict:
    """Load one revision pair into Analytics."""

    prepared_unit = prepare_unit_revisions(
        unit_df
    )

    prepared_fuel = prepare_fuel_revisions(
        fuel_df
    )

    prepared_system = prepare_system_revisions(
        system_df
    )

    unit_rows = upsert_dataframe(
        connection=connection,
        table_name="unit_availability_revision",
        df=prepared_unit,
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
        df=prepared_fuel,
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
        df=prepared_system,
        conflict_columns=[
            "previous_publish_time",
            "latest_publish_time",
            "forecast_date",
        ],
    )

    return {
        "unit_rows": unit_rows,
        "fuel_rows": fuel_rows,
        "system_rows": system_rows,
    }


def backfill_database() -> dict:
    """Replay all canonical publications through the database."""

    files = get_publication_files()

    engine = get_engine()

    publication_results = []

    print()
    print("HISTORICAL DATABASE BACKFILL")
    print("----------------------------")
    print(
        "Canonical publications:",
        len(files),
    )

    for file_path in files:

        print()
        print("PUBLICATION")
        print("-----------")
        print("Source:", file_path)

        raw_result = load_raw_publication_file(
            file_path
        )

        (
            _,
            fuel_df,
            system_df,
        ) = transform_publication_file(
            file_path
        )

        with engine.begin() as connection:
            silver_result = load_silver_dataframes(
                connection,
                fuel_df,
                system_df,
            )

        publication_results.append(
            {
                "file": file_path,
                "raw": raw_result,
                "silver": silver_result,
            }
        )

        print(
            "Silver fuel rows:",
            silver_result[
                "fuel_rows_database"
            ],
        )
        print(
            "Silver system rows:",
            silver_result[
                "system_rows_database"
            ],
        )

    pair_results = []

    for previous_file, latest_file in zip(
        files,
        files[1:],
    ):

        previous = (
            load_transformation_publication_file(
                previous_file
            )
        )

        latest = (
            load_transformation_publication_file(
                latest_file
            )
        )

        unit_revisions = build_unit_revisions(
            previous,
            latest,
        )

        fuel_revisions = build_fuel_revisions(
            unit_revisions
        )

        system_revisions = build_system_revisions(
            unit_revisions
        )

        save_outputs(
            unit_revisions,
            fuel_revisions,
            system_revisions,
        )

        with engine.begin() as connection:
            analytics_result = (
                load_analytics_dataframes(
                    connection,
                    unit_revisions,
                    fuel_revisions,
                    system_revisions,
                )
            )

        previous_time = pd.Timestamp(
            unit_revisions[
                "previousPublishTime"
            ].iloc[0]
        )

        latest_time = pd.Timestamp(
            unit_revisions[
                "latestPublishTime"
            ].iloc[0]
        )

        changed_rows = int(
            (
                unit_revisions["revisionMW"]
                != 0
            ).sum()
        )

        pair_results.append(
            {
                "previous_publish_time":
                    previous_time,
                "latest_publish_time":
                    latest_time,
                "changed_rows":
                    changed_rows,
                **analytics_result,
            }
        )

        print()
        print("REVISION PAIR")
        print("-------------")
        print(
            "Previous:",
            previous_time,
        )
        print(
            "Latest:  ",
            latest_time,
        )
        print(
            "Changed unit/date rows:",
            changed_rows,
        )
        print(
            "Analytics unit rows:",
            analytics_result["unit_rows"],
        )

    return {
        "publications":
            publication_results,
        "revision_pairs":
            pair_results,
    }


def main() -> None:
    """Run complete historical database replay."""

    result = backfill_database()

    print()
    print("BACKFILL COMPLETE")
    print("-----------------")
    print(
        "Publications processed:",
        len(result["publications"]),
    )
    print(
        "Revision pairs processed:",
        len(result["revision_pairs"]),
    )


if __name__ == "__main__":
    main()
