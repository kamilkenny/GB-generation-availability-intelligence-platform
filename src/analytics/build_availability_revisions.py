from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.settings import PROCESSED_DATA_DIR, RAW_DATA_DIR


RAW_DIRECTORY = RAW_DATA_DIR / "uou2t14d"

OUTPUT_DIRECTORY = (
    PROCESSED_DATA_DIR
    / "uou2t14d"
    / "revisions"
)


def get_publication_files() -> list[Path]:
    """Return canonical publication snapshots in chronological order."""

    return sorted(
        RAW_DIRECTORY.glob(
            "uou2t14d_publish_*.parquet"
        )
    )


def load_latest_two_publications():
    """Load the two most recent Elexon publications."""

    files = get_publication_files()

    if len(files) < 2:
        return None

    previous_file = files[-2]
    latest_file = files[-1]

    previous = pd.read_parquet(previous_file)
    latest = pd.read_parquet(latest_file)

    for df in (previous, latest):
        df["forecastDate"] = pd.to_datetime(
            df["forecastDate"],
            errors="coerce",
        )

        df["publishTime"] = pd.to_datetime(
            df["publishTime"],
            utc=True,
            errors="coerce",
        )

        df["outputUsable"] = pd.to_numeric(
            df["outputUsable"],
            errors="coerce",
        )

    return (
        previous_file,
        latest_file,
        previous,
        latest,
    )


def build_unit_revisions(
    previous: pd.DataFrame,
    latest: pd.DataFrame,
) -> pd.DataFrame:
    """Compare availability for matching units and forecast dates."""

    previous_dates = set(
        previous["forecastDate"].dropna()
    )

    latest_dates = set(
        latest["forecastDate"].dropna()
    )

    common_dates = sorted(
        previous_dates.intersection(
            latest_dates
        )
    )

    if not common_dates:
        raise ValueError(
            "The two publications have no overlapping "
            "forecast dates."
        )

    previous = previous[
        previous["forecastDate"].isin(
            common_dates
        )
    ].copy()

    latest = latest[
        latest["forecastDate"].isin(
            common_dates
        )
    ].copy()

    previous = previous[
        [
            "nationalGridBmUnit",
            "fuelType",
            "forecastDate",
            "publishTime",
            "outputUsable",
        ]
    ].rename(
        columns={
            "publishTime": "previousPublishTime",
            "outputUsable": "previousAvailableMW",
        }
    )

    latest = latest[
        [
            "nationalGridBmUnit",
            "fuelType",
            "forecastDate",
            "publishTime",
            "outputUsable",
        ]
    ].rename(
        columns={
            "publishTime": "latestPublishTime",
            "outputUsable": "latestAvailableMW",
        }
    )

    revisions = previous.merge(
        latest,
        on=[
            "nationalGridBmUnit",
            "fuelType",
            "forecastDate",
        ],
        how="inner",
        validate="one_to_one",
    )

    revisions["revisionMW"] = (
        revisions["latestAvailableMW"]
        - revisions["previousAvailableMW"]
    )

    revisions["absoluteRevisionMW"] = (
        revisions["revisionMW"].abs()
    )

    revisions["changeDirection"] = "UNCHANGED"

    revisions.loc[
        revisions["revisionMW"] > 0,
        "changeDirection",
    ] = "UP"

    revisions.loc[
        revisions["revisionMW"] < 0,
        "changeDirection",
    ] = "DOWN"

    revisions["becameUnavailable"] = (
        (revisions["previousAvailableMW"] > 0)
        & (revisions["latestAvailableMW"] == 0)
    )

    revisions["returnedAvailable"] = (
        (revisions["previousAvailableMW"] == 0)
        & (revisions["latestAvailableMW"] > 0)
    )

    return revisions.sort_values(
        [
            "forecastDate",
            "absoluteRevisionMW",
        ],
        ascending=[
            True,
            False,
        ],
    ).reset_index(drop=True)


def build_fuel_revisions(
    unit_revisions: pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate revisions by forecast date and fuel type."""

    return (
        unit_revisions.groupby(
            [
                "previousPublishTime",
                "latestPublishTime",
                "forecastDate",
                "fuelType",
            ],
            as_index=False,
        )
        .agg(
            previousAvailableMW=(
                "previousAvailableMW",
                "sum",
            ),
            latestAvailableMW=(
                "latestAvailableMW",
                "sum",
            ),
            revisionMW=(
                "revisionMW",
                "sum",
            ),
            changedUnits=(
                "revisionMW",
                lambda x: int((x != 0).sum()),
            ),
            becameUnavailableUnits=(
                "becameUnavailable",
                "sum",
            ),
            returnedAvailableUnits=(
                "returnedAvailable",
                "sum",
            ),
        )
        .sort_values(
            [
                "forecastDate",
                "revisionMW",
            ]
        )
        .reset_index(drop=True)
    )


def build_system_revisions(
    unit_revisions: pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate revisions to GB system level."""

    return (
        unit_revisions.groupby(
            [
                "previousPublishTime",
                "latestPublishTime",
                "forecastDate",
            ],
            as_index=False,
        )
        .agg(
            previousAvailableMW=(
                "previousAvailableMW",
                "sum",
            ),
            latestAvailableMW=(
                "latestAvailableMW",
                "sum",
            ),
            revisionMW=(
                "revisionMW",
                "sum",
            ),
            changedUnits=(
                "revisionMW",
                lambda x: int((x != 0).sum()),
            ),
            becameUnavailableUnits=(
                "becameUnavailable",
                "sum",
            ),
            returnedAvailableUnits=(
                "returnedAvailable",
                "sum",
            ),
        )
        .sort_values(
            "forecastDate"
        )
        .reset_index(drop=True)
    )


def save_outputs(
    unit_revisions: pd.DataFrame,
    fuel_revisions: pd.DataFrame,
    system_revisions: pd.DataFrame,
) -> None:
    """Write revision-intelligence tables."""

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    unit_revisions.to_parquet(
        OUTPUT_DIRECTORY
        / "latest_unit_revisions.parquet",
        index=False,
    )

    fuel_revisions.to_parquet(
        OUTPUT_DIRECTORY
        / "latest_fuel_revisions.parquet",
        index=False,
    )

    system_revisions.to_parquet(
        OUTPUT_DIRECTORY
        / "latest_system_revisions.parquet",
        index=False,
    )


def main() -> None:
    """Build latest publication-to-publication revision intelligence."""

    loaded = load_latest_two_publications()

    if loaded is None:
        print()
        print("AVAILABILITY REVISION INTELLIGENCE")
        print("----------------------------------")
        print(
            "Status: WAITING FOR SECOND PUBLICATION"
        )
        print(
            "Only one canonical Elexon publication "
            "is currently stored."
        )
        print(
            "Run the collector again after Elexon "
            "publishes a new UOU2T14D snapshot."
        )
        return

    (
        previous_file,
        latest_file,
        previous,
        latest,
    ) = loaded

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

    previous_time = (
        unit_revisions[
            "previousPublishTime"
        ].iloc[0]
    )

    latest_time = (
        unit_revisions[
            "latestPublishTime"
        ].iloc[0]
    )

    print()
    print("AVAILABILITY REVISION INTELLIGENCE")
    print("----------------------------------")
    print("Previous publication:", previous_time)
    print("Latest publication:  ", latest_time)
    print(
        "Compared unit/date rows:",
        f"{len(unit_revisions):,}",
    )
    print(
        "Changed unit/date rows:",
        f"{(unit_revisions['revisionMW'] != 0).sum():,}",
    )

    print()
    print("SYSTEM REVISION BY FORECAST DATE")
    print("--------------------------------")
    print(
        system_revisions.to_string(
            index=False
        )
    )

    print()
    print("TOP 10 DOWNWARD UNIT REVISIONS")
    print("------------------------------")

    downward = (
        unit_revisions[
            unit_revisions["revisionMW"] < 0
        ]
        .sort_values("revisionMW")
        .head(10)
    )

    if downward.empty:
        print("No downward revisions detected.")
    else:
        print(
            downward[
                [
                    "forecastDate",
                    "nationalGridBmUnit",
                    "fuelType",
                    "previousAvailableMW",
                    "latestAvailableMW",
                    "revisionMW",
                ]
            ].to_string(index=False)
        )

    print()
    print("TOP 10 UPWARD UNIT REVISIONS")
    print("----------------------------")

    upward = (
        unit_revisions[
            unit_revisions["revisionMW"] > 0
        ]
        .sort_values(
            "revisionMW",
            ascending=False,
        )
        .head(10)
    )

    if upward.empty:
        print("No upward revisions detected.")
    else:
        print(
            upward[
                [
                    "forecastDate",
                    "nationalGridBmUnit",
                    "fuelType",
                    "previousAvailableMW",
                    "latestAvailableMW",
                    "revisionMW",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()
