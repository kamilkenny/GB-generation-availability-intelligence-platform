from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.settings import PROCESSED_DATA_DIR, RAW_DATA_DIR


RAW_DIRECTORY = RAW_DATA_DIR / "uou2t14d"

PROCESSED_DIRECTORY = (
    PROCESSED_DATA_DIR / "uou2t14d"
)


def latest_publication_file() -> Path:
    """Locate the most recently stored canonical publication."""

    files = sorted(
        RAW_DIRECTORY.glob(
            "uou2t14d_publish_*.parquet"
        )
    )

    if not files:
        raise FileNotFoundError(
            "No canonical UOU2T14D publication "
            "was found."
        )

    return files[-1]


def load_publication_file(
    file_path: Path,
) -> pd.DataFrame:
    """Load one explicit canonical publication."""

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

    publish_times = (
        df["publishTime"]
        .dropna()
        .drop_duplicates()
    )

    if len(publish_times) != 1:
        raise ValueError(
            "Expected exactly one publishTime in "
            f"{file_path.name}, but found "
            f"{len(publish_times)}."
        )

    return df


def load_latest_publication() -> pd.DataFrame:
    """Load latest raw publication."""

    return load_publication_file(
        latest_publication_file()
    )


def build_fuel_availability(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Aggregate available generation by forecast date
    and fuel type.
    """

    result = (
        df.groupby(
            [
                "publishTime",
                "forecastDate",
                "fuelType",
            ],
            as_index=False,
        )
        .agg(
            available_mw=(
                "outputUsable",
                "sum",
            ),
            bm_units=(
                "nationalGridBmUnit",
                "nunique",
            ),
            zero_availability_units=(
                "outputUsable",
                lambda x: int((x == 0).sum()),
            ),
        )
        .sort_values(
            [
                "forecastDate",
                "available_mw",
            ],
            ascending=[
                True,
                False,
            ],
        )
        .reset_index(drop=True)
    )

    return result


def build_system_availability(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate total system availability by forecast date."""

    result = (
        df.groupby(
            [
                "publishTime",
                "forecastDate",
            ],
            as_index=False,
        )
        .agg(
            total_available_mw=(
                "outputUsable",
                "sum",
            ),
            bm_units=(
                "nationalGridBmUnit",
                "nunique",
            ),
            zero_availability_units=(
                "outputUsable",
                lambda x: int((x == 0).sum()),
            ),
        )
        .sort_values("forecastDate")
        .reset_index(drop=True)
    )

    return result


def save_processed_tables(
    fuel_availability: pd.DataFrame,
    system_availability: pd.DataFrame,
) -> None:
    """Persist processed analytical tables."""

    PROCESSED_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    fuel_path = (
        PROCESSED_DIRECTORY
        / "latest_fuel_availability.parquet"
    )

    system_path = (
        PROCESSED_DIRECTORY
        / "latest_system_availability.parquet"
    )

    fuel_availability.to_parquet(
        fuel_path,
        index=False,
    )

    system_availability.to_parquet(
        system_path,
        index=False,
    )

    print("Processed tables written:")
    print(f"  {fuel_path}")
    print(f"  {system_path}")


def transform_publication_file(
    file_path: Path,
):
    """Transform one explicit canonical publication."""

    file_path = Path(file_path)

    df = load_publication_file(
        file_path
    )

    fuel_availability = build_fuel_availability(
        df
    )

    system_availability = build_system_availability(
        df
    )

    save_processed_tables(
        fuel_availability,
        system_availability,
    )

    return (
        df,
        fuel_availability,
        system_availability,
    )


def main() -> None:
    """Transform latest UOU2T14D publication."""

    source_file = latest_publication_file()

    (
        df,
        fuel_availability,
        system_availability,
    ) = transform_publication_file(
        source_file
    )

    print()
    print("UOU2T14D TRANSFORMATION COMPLETE")
    print("--------------------------------")
    print("Source:", source_file)
    print("Raw rows:", f"{len(df):,}")
    print(
        "Fuel/date analytical rows:",
        f"{len(fuel_availability):,}",
    )
    print(
        "Forecast dates:",
        df["forecastDate"].nunique(),
    )

    print()
    print("SYSTEM AVAILABILITY BY FORECAST DATE")
    print("------------------------------------")
    print(
        system_availability.to_string(
            index=False
        )
    )

    print()
    print("FIRST 20 FUEL AVAILABILITY RECORDS")
    print("----------------------------------")
    print(
        fuel_availability.head(20).to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()
