import pandas as pd

from src.transformation.transform_uou2t14d import (
    build_fuel_availability,
    build_system_availability,
)


def sample_availability():
    publish_time = pd.Timestamp(
        "2026-08-12T01:00:00Z"
    )

    return pd.DataFrame(
        [
            {
                "publishTime": publish_time,
                "forecastDate": pd.Timestamp(
                    "2026-08-14"
                ),
                "fuelType": "CCGT",
                "nationalGridBmUnit": "CCGT-1",
                "outputUsable": 100,
            },
            {
                "publishTime": publish_time,
                "forecastDate": pd.Timestamp(
                    "2026-08-14"
                ),
                "fuelType": "CCGT",
                "nationalGridBmUnit": "CCGT-2",
                "outputUsable": 0,
            },
            {
                "publishTime": publish_time,
                "forecastDate": pd.Timestamp(
                    "2026-08-14"
                ),
                "fuelType": "WIND",
                "nationalGridBmUnit": "WIND-1",
                "outputUsable": 50,
            },
            {
                "publishTime": publish_time,
                "forecastDate": pd.Timestamp(
                    "2026-08-15"
                ),
                "fuelType": "CCGT",
                "nationalGridBmUnit": "CCGT-1",
                "outputUsable": 80,
            },
            {
                "publishTime": publish_time,
                "forecastDate": pd.Timestamp(
                    "2026-08-15"
                ),
                "fuelType": "WIND",
                "nationalGridBmUnit": "WIND-1",
                "outputUsable": 20,
            },
        ]
    )


def test_fuel_availability_aggregation():
    result = build_fuel_availability(
        sample_availability()
    )

    row = result[
        (
            result["forecastDate"]
            == pd.Timestamp("2026-08-14")
        )
        & (
            result["fuelType"]
            == "CCGT"
        )
    ].iloc[0]

    assert row["available_mw"] == 100
    assert row["bm_units"] == 2
    assert row["zero_availability_units"] == 1


def test_system_availability_aggregation():
    result = build_system_availability(
        sample_availability()
    )

    row = result[
        result["forecastDate"]
        == pd.Timestamp("2026-08-14")
    ].iloc[0]

    assert row["total_available_mw"] == 150
    assert row["bm_units"] == 3
    assert row["zero_availability_units"] == 1


def test_fuel_totals_reconcile_to_system_totals():
    df = sample_availability()

    fuel = build_fuel_availability(df)
    system = build_system_availability(df)

    fuel_totals = (
        fuel.groupby(
            [
                "publishTime",
                "forecastDate",
            ],
            as_index=False,
        )["available_mw"]
        .sum()
        .rename(
            columns={
                "available_mw":
                    "fuel_total_mw"
            }
        )
    )

    comparison = system.merge(
        fuel_totals,
        on=[
            "publishTime",
            "forecastDate",
        ],
        how="inner",
        validate="one_to_one",
    )

    assert (
        comparison["total_available_mw"]
        == comparison["fuel_total_mw"]
    ).all()


def test_zero_availability_counts_reconcile():
    df = sample_availability()

    fuel = build_fuel_availability(df)
    system = build_system_availability(df)

    fuel_zero_counts = (
        fuel.groupby(
            [
                "publishTime",
                "forecastDate",
            ],
            as_index=False,
        )["zero_availability_units"]
        .sum()
        .rename(
            columns={
                "zero_availability_units":
                    "fuel_zero_units"
            }
        )
    )

    comparison = system.merge(
        fuel_zero_counts,
        on=[
            "publishTime",
            "forecastDate",
        ],
        validate="one_to_one",
    )

    assert (
        comparison["zero_availability_units"]
        == comparison["fuel_zero_units"]
    ).all()
