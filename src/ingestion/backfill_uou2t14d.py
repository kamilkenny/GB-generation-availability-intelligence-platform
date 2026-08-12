from __future__ import annotations

import argparse

import pandas as pd

from src.ingestion.collect_uou2t14d import (
    get_publication_time,
    save_snapshot,
    validate_dataframe,
)
from src.ingestion.elexon_client import ElexonClient


def split_publications(
    df: pd.DataFrame,
) -> list[pd.DataFrame]:
    """
    Split a historical UOU2T14D response into
    individual source publications.
    """

    if df.empty:
        return []

    if "publishTime" not in df.columns:
        raise ValueError(
            "Historical response does not contain publishTime."
        )

    valid_publish_times = (
        pd.to_datetime(
            df["publishTime"],
            utc=True,
            errors="coerce",
        )
        .dropna()
        .drop_duplicates()
        .sort_values()
    )

    publications = []

    for publish_time in valid_publish_times:
        publication = df[
            df["publishTime"] == publish_time
        ].copy()

        publication = (
            publication
            .sort_values(
                [
                    "forecastDate",
                    "nationalGridBmUnit",
                ]
            )
            .reset_index(drop=True)
        )

        publications.append(publication)

    return publications


def backfill_range(
    publish_datetime_from,
    publish_datetime_to,
) -> dict:
    """
    Retrieve and store genuine historical
    UOU2T14D publications.
    """

    client = ElexonClient()

    print()
    print("UOU2T14D HISTORICAL BACKFILL")
    print("----------------------------")
    print(
        "Requested from:",
        publish_datetime_from,
    )
    print(
        "Requested to:",
        publish_datetime_to,
    )

    df = (
        client
        .get_generation_availability_by_publish_time(
            publish_datetime_from,
            publish_datetime_to,
        )
    )

    print(
        "Rows returned:",
        f"{len(df):,}",
    )

    if df.empty:
        print("Status: NO DATA RETURNED")

        return {
            "rows_returned": 0,
            "publications_found": 0,
            "publications_created": 0,
            "publications_existing": 0,
        }

    publications = split_publications(df)

    created_count = 0
    existing_count = 0

    print(
        "Publications found:",
        len(publications),
    )

    print()
    print("PUBLICATION RESULTS")
    print("-------------------")

    for publication in publications:
        validation = validate_dataframe(
            publication
        )

        publish_time = get_publication_time(
            publication
        )

        (
            parquet_path,
            metadata_path,
            created,
        ) = save_snapshot(
            publication,
            validation,
        )

        if created:
            created_count += 1
            status = "SAVED"
        else:
            existing_count += 1
            status = "ALREADY STORED"

        print()
        print(
            "Publication:",
            publish_time.isoformat(),
        )
        print(
            "Rows:",
            f"{len(publication):,}",
        )
        print(
            "BM Units:",
            f"{publication['nationalGridBmUnit'].nunique():,}",
        )
        print(
            "Forecast dates:",
            f"{publication['forecastDate'].nunique():,}",
        )
        print(
            "Fuel types:",
            f"{publication['fuelType'].nunique():,}",
        )
        print(
            "Duplicate source keys:",
            validation["duplicate_key_rows"],
        )
        print(
            "Status:",
            status,
        )

        if created:
            print(
                "Parquet:",
                parquet_path,
            )
            print(
                "Metadata:",
                metadata_path,
            )

    print()
    print("BACKFILL COMPLETE")
    print("-----------------")
    print(
        "Rows returned:",
        f"{len(df):,}",
    )
    print(
        "Publications found:",
        len(publications),
    )
    print(
        "New publications saved:",
        created_count,
    )
    print(
        "Existing publications skipped:",
        existing_count,
    )

    return {
        "rows_returned": int(len(df)),
        "publications_found": int(
            len(publications)
        ),
        "publications_created": int(
            created_count
        ),
        "publications_existing": int(
            existing_count
        ),
    }


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Backfill historical Elexon "
            "UOU2T14D publications."
        )
    )

    parser.add_argument(
        "--from",
        dest="publish_datetime_from",
        required=True,
        help=(
            "Inclusive UTC publication start, "
            "for example "
            "2026-08-12T00:00:00Z"
        ),
    )

    parser.add_argument(
        "--to",
        dest="publish_datetime_to",
        required=True,
        help=(
            "Inclusive UTC publication end, "
            "for example "
            "2026-08-12T02:00:00Z"
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    backfill_range(
        publish_datetime_from=(
            args.publish_datetime_from
        ),
        publish_datetime_to=(
            args.publish_datetime_to
        ),
    )


if __name__ == "__main__":
    main()
